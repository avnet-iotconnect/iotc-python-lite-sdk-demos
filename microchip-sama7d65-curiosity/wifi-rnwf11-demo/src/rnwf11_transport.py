# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""
Bridges the IoTConnect Python Lite SDK's MQTT transport (paho-mqtt) over the
EV12H55A/RNWF11 WiFi Add-on Board.

The RNWF11 only exposes AT commands over UART -- it does not present itself
to Linux as a network interface. Rather than reimplement TLS and MQTT on top
of the module's own AT+TLSC/AT+MQTTC command set, this module gives
paho-mqtt a real local socket (one end of a socket.socketpair()) and pumps
raw bytes between that socket and the RNWF11's raw-TCP AT+SOCKWR/AT+SOCKRD
commands. TLS and MQTT continue to run unmodified in Python, using the
device certificate/key exactly as the standard (Ethernet) quickstart does.
"""

import re
import select
import socket
import threading
import time
from collections import deque

import serial

DEFAULT_PORT = "/dev/ttyS1"
DEFAULT_BAUD = 230400

_WRITE_CHUNK_MAX = 512  # conservative chunk size for AT+SOCKWR


class Rnwf11Error(Exception):
    """Raised when the RNWF11 module reports an AT command error or an unexpected response."""


class Rnwf11Uart:
    """Low-level synchronous AT-command driver for the RNWF11 'UART to Cloud' WiFi module.

    This class is meant to be used by a single owner at a time. The caller is
    expected to finish WiFi join and socket open/connect sequentially before
    handing the (now-connected) socket id off to Rnwf11MqttTransport, which
    becomes the sole user of this object for the rest of the connection's life.
    """

    def __init__(self, port=DEFAULT_PORT, baud=DEFAULT_BAUD):
        self._ser = serial.Serial(port, baud, timeout=0.05)
        self._buf = bytearray()
        self._pending_events = deque()

    def close(self):
        self._ser.close()

    # ---- low level byte/line helpers ----

    def _read_more(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self._ser.read(4096)
            if chunk:
                self._buf.extend(chunk)
                return True
        return False

    def _read_line(self, timeout):
        """Read one non-empty line, stripping stray '>' idle-prompt bytes."""
        deadline = time.monotonic() + timeout
        while True:
            idx = self._buf.find(b"\r\n")
            if idx != -1:
                raw = bytes(self._buf[:idx])
                del self._buf[:idx + 2]
                line = raw.replace(b">", b"").strip()
                if line:
                    return line.decode(errors="replace")
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Rnwf11Error("Timeout waiting for a response line")
            self._read_more(min(remaining, 0.2))

    def _wait_for_marker(self, marker: bytes, timeout):
        """Consume buffered bytes up to and including a single marker byte (e.g. b'#')."""
        deadline = time.monotonic() + timeout
        while True:
            idx = self._buf.find(marker)
            if idx != -1:
                del self._buf[:idx + len(marker)]
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Rnwf11Error("Timeout waiting for %r prompt" % marker)
            self._read_more(min(remaining, 0.2))

    def _read_exact(self, n: int, timeout) -> bytes:
        deadline = time.monotonic() + timeout
        while len(self._buf) < n:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Rnwf11Error("Timeout reading %d raw bytes" % n)
            self._read_more(min(remaining, 0.2))
        data = bytes(self._buf[:n])
        del self._buf[:n]
        return data

    def _expect_ok(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0.1, deadline - time.monotonic())
            line = self._read_line(remaining)
            if line.startswith("AT+"):
                continue  # command echo
            if line == "OK":
                return
            if line.startswith("ERROR"):
                raise Rnwf11Error(line)
            if line.startswith("+"):
                self._pending_events.append(line)
                continue
            # unrecognized stray text; ignore it

    # ---- plain command/response (no raw payload involved) ----

    def command(self, cmd: str, timeout=5.0) -> list:
        """Send a plain AT command. Returns any non-event extra lines seen before OK."""
        self._ser.write((cmd + "\r\n").encode())
        lines = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0.1, deadline - time.monotonic())
            line = self._read_line(remaining)
            if line == cmd or line.startswith("AT+"):
                continue  # command echo
            if line == "OK":
                return lines
            if line.startswith("ERROR"):
                raise Rnwf11Error(line)
            if line.startswith("+"):
                self._pending_events.append(line)
            else:
                lines.append(line)

    def wait_for_event(self, prefixes, timeout=10.0) -> str:
        """Block until an unsolicited '+EVENT:...' line starting with one of `prefixes` arrives."""
        prefixes = tuple(prefixes)
        deadline = time.monotonic() + timeout
        while True:
            for line in list(self._pending_events):
                if line.startswith(prefixes):
                    self._pending_events.remove(line)
                    return line
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Rnwf11Error("Timeout waiting for one of %r" % (prefixes,))
            try:
                line = self._read_line(min(remaining, 0.5))
            except Rnwf11Error:
                continue
            if line.startswith(prefixes):
                return line
            if line.startswith("+"):
                self._pending_events.append(line)

    def poll_event(self, timeout=0.05):
        """Non-blocking-ish check for a single buffered unsolicited '+EVENT:...' line, or None."""
        if self._pending_events:
            return self._pending_events.popleft()
        try:
            line = self._read_line(timeout)
        except Rnwf11Error:
            return None
        if line.startswith("+"):
            return line
        return None

    # ---- raw socket payload write/read ----

    def socket_write(self, sock_id: int, payload: bytes, timeout=10.0):
        self._ser.write(("AT+SOCKWR=%d,%d\r\n" % (sock_id, len(payload))).encode())
        self._wait_for_marker(b"#", timeout)
        self._ser.write(payload)
        self._expect_ok(timeout)

    def socket_read(self, sock_id: int, n: int, timeout=10.0) -> bytes:
        self._ser.write(("AT+SOCKRD=%d,2,%d\r\n" % (sock_id, n)).encode())
        self._wait_for_marker(b"#", timeout)
        data = self._read_exact(n, timeout)
        self._expect_ok(timeout)
        return data

    # ---- WiFi join ----

    def wifi_is_associated(self) -> bool:
        try:
            self.command("AT+ASSOC?")
            return True
        except Rnwf11Error:
            return False

    def wifi_scan_security(self, ssid: str, timeout=8.0) -> int:
        """Scan for `ssid` and return its reported security type code."""
        self._ser.write(b"AT+WSCN=0\r\n")
        deadline = time.monotonic() + timeout
        security = None
        while True:
            remaining = max(0.1, deadline - time.monotonic())
            line = self._read_line(remaining)
            if line.startswith("AT+") or line == "OK":
                continue
            if line.startswith("+WSCNIND:"):
                m = re.match(r'\+WSCNIND:(-?\d+),(\d+),(\d+),"([^"]*)","?(.*?)"?$', line)
                if m and m.group(5) == ssid:
                    security = int(m.group(2))
                continue
            if line.startswith("+WSCNDONE:"):
                break
        if security is None:
            raise Rnwf11Error("SSID %r not found in scan results" % ssid)
        return security

    def wifi_connect(self, ssid: str, password: str, security=None, timeout=20.0) -> str:
        """Join a WiFi network. Returns the IPv4 address obtained, or raises Rnwf11Error."""
        if security is None:
            security = self.wifi_scan_security(ssid)
        self.command('AT+WSTAC=1,"%s"' % ssid)
        self.command("AT+WSTAC=2,%d" % security)
        self.command('AT+WSTAC=3,"%s"' % password)
        self.command("AT+WSTAC=4,0")
        self.command("AT+WSTA=1")
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Rnwf11Error("Timeout waiting for WiFi connection")
            event = self.wait_for_event(("+WSTAAIP:", "+WSTAERR:"), timeout=remaining)
            if event.startswith("+WSTAERR:"):
                raise Rnwf11Error("WiFi connection failed: %s" % event)
            # +WSTAAIP:<id>,"<ip>" -- skip the IPv6 link-local one, wait for IPv4
            m = re.match(r'\+WSTAAIP:\d+,"([^"]+)"', event)
            if m and "." in m.group(1):
                return m.group(1)

    def connect_wifi_if_needed(self, ssid: str, password: str, security=None, timeout=20.0) -> None:
        if not self.wifi_is_associated():
            self.wifi_connect(ssid, password, security=security, timeout=timeout)

    # ---- raw TCP socket lifecycle ----

    def socket_open_tcp(self) -> int:
        # AT+SOCKO's own reply line ("+SOCKO:<id>") starts with '+', so command()
        # files it into _pending_events alongside genuine async notifications --
        # check there too, not just the plain (non-'+') line list.
        lines = self.command("AT+SOCKO=2,4")
        candidates = lines + list(self._pending_events)
        for line in candidates:
            m = re.match(r"\+SOCKO:(\d+)", line)
            if m:
                if line in self._pending_events:
                    self._pending_events.remove(line)
                return int(m.group(1))
        raise Rnwf11Error("AT+SOCKO did not return a socket id: %r" % candidates)

    def socket_connect(self, sock_id: int, host: str, port: int, timeout=10.0):
        self.command('AT+SOCKBR=%d,"%s",%d' % (sock_id, host, port))
        event = self.wait_for_event(("+SOCKIND:", "+SOCKERR:"), timeout=timeout)
        if event.startswith("+SOCKERR:"):
            raise Rnwf11Error("Socket connect failed: %s" % event)

    def socket_close(self, sock_id: int):
        try:
            self.command("AT+SOCKCL=%d" % sock_id)
        except Rnwf11Error:
            pass


class Rnwf11MqttTransport:
    """Pumps bytes between a local socket.socketpair() end and an RNWF11 raw TCP socket.

    Give `local_socket` to paho-mqtt (see patch_paho_transport below) and call
    start(). From that point on, this object is the sole user of the
    Rnwf11Uart instance it was constructed with.
    """

    def __init__(self, uart: Rnwf11Uart, sock_id: int):
        self._uart = uart
        self._sock_id = sock_id
        self.local_socket, self._bridge_socket = socket.socketpair()
        self._bridge_socket.setblocking(False)
        self._thread = None
        self._running = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._uart.socket_close(self._sock_id)
        try:
            self.local_socket.close()
        except OSError:
            pass

    def _run(self):
        try:
            while self._running:
                self._pump_outgoing()
                if not self._drain_incoming_events():
                    break
        except Exception as exc:  # noqa: BLE001 - surface to console, then stop the bridge
            print("RNWF11 transport bridge stopped:", exc)
        finally:
            try:
                self._bridge_socket.close()
            except OSError:
                pass

    def _pump_outgoing(self):
        readable, _, _ = select.select([self._bridge_socket], [], [], 0.05)
        if not readable:
            return
        try:
            data = self._bridge_socket.recv(65536)
        except BlockingIOError:
            return
        if not data:
            # paho closed its end of the socketpair -- propagate as a clean stop
            self._running = False
            return
        for offset in range(0, len(data), _WRITE_CHUNK_MAX):
            self._uart.socket_write(self._sock_id, data[offset:offset + _WRITE_CHUNK_MAX])

    def _drain_incoming_events(self) -> bool:
        """Process buffered +SOCKRXT/+SOCKCL notifications. Returns False on remote close.

        +SOCKRXT:<id>,<n> reports the *cumulative* bytes available since the last
        AT+SOCKRD on this socket -- not new bytes since the previous notification.
        Several of these can arrive back-to-back as one TCP burst is received, each
        superseding the last with a larger total. Reading only the first (smallest)
        value seen would strand the rest, since no further notification is sent for
        data that's already been flagged once. So: collect everything currently
        queued, and read exactly the largest total reported, once.
        """
        max_n = None
        closed = False
        while True:
            event = self._uart.poll_event(timeout=0.05)
            if event is None:
                break
            m = re.match(r"\+SOCKRXT:(\d+),(\d+)", event)
            if m and int(m.group(1)) == self._sock_id:
                n = int(m.group(2))
                if max_n is None or n > max_n:
                    max_n = n
                continue
            if event.startswith("+SOCKCL:%d" % self._sock_id):
                closed = True
                continue
            # unrelated event (e.g. a different socket, or +ASSOC:/+WSTA*: noise); ignore
        if max_n:
            data = self._uart.socket_read(self._sock_id, max_n)
            if data:
                self._bridge_socket.sendall(data)
        return not closed


def patch_paho_transport(mqtt_client, transport: Rnwf11MqttTransport):
    """Make an existing paho-mqtt Client use the RNWF11 bridge instead of a real OS socket.

    Call this once, after constructing the iotconnect-sdk-lite Client (so
    `mqtt_client` is its `.mqtt` attribute) and before calling `.connect()`.
    Everything else about the SDK -- TLS, MQTT, telemetry, C2D, OTA -- is
    untouched.
    """
    mqtt_client._create_socket_connection = lambda: transport.local_socket
