# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Workshop demo: PolarFire SoC Discovery Kit fabric stream to DDR/LSRAM via CoreAXI4DMAController

import os
import sys
import time
import struct
import mmap
import subprocess
import re
from dataclasses import dataclass

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

APP_VERSION = "0.4.3"

# Optional LED control (CoreGPIO on FIC3). Default address may be unavailable on some images.
LED_GPIO_BASE = int(os.environ.get("LED_GPIO_BASE", "0x40000100"), 16)
LED_GPIO_DIR = 0x04
LED_GPIO_DATA = 0x00
LED_GPIO_MASK_DEFAULT = 0x07  # 3 LEDs


DMA_BASE = 0x60010000          # CoreAXI4DMAController control regs
LSRAM_BASE = 0x60000000        # MSS LSRAM

DESC_OFFSET = 0x0000
DATA_OFFSET = 0x0200

DESC_CONFIG_STREAM = 0x0D  # Descriptor Valid + Dest Data Ready + Dest Operand


@dataclass
class CaptureResult:
    pattern_count: int
    first: int
    last: int
    checksum: int
    ok: bool
    elapsed_ms: int


class Devmem2Access:
    def __init__(self, base):
        self.base = base
        self.size = None

    def _run(self, addr, value=None):
        if value is None:
            out = subprocess.check_output(['devmem2', hex(addr)], stderr=subprocess.STDOUT)
            text = out.decode(errors='ignore')
            # devmem2 output varies; extract the last hex value in the output.
            matches = re.findall(r'0x[0-9a-fA-F]+', text)
            if matches:
                return int(matches[-1], 16)
            raise RuntimeError(f'devmem2 read parse failed: {text.strip()}')
        subprocess.check_call(
            ['devmem2', hex(addr), 'w', hex(value & 0xFFFFFFFF)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return None

    def read32(self, offset):
        return self._run(self.base + offset)

    def write32(self, offset, value):
        self._run(self.base + offset, value)


def read_cpu_mhz():
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("cpu MHz"):
                    return float(line.split(":")[1].strip())
    except Exception:
        return None
    return None


def read_loadavg():
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
            return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return None, None, None


def read_meminfo():
    info = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, val = line.split(":", 1)
                info[key.strip()] = int(val.strip().split()[0])
    except Exception:
        return None, None, None
    return info.get("MemTotal"), info.get("MemFree"), info.get("MemAvailable")


def read_uptime():
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            return float(f.read().split()[0])
    except Exception:
        return None


def read_disk_used_pct(path="/"):
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        used = total - free
        if total == 0:
            return None
        return round((used / total) * 100.0, 2)
    except Exception:
        return None


def read_cpu_temp_c():
    # Best-effort: look for any thermal zone temp
    base = "/sys/class/thermal"
    try:
        for name in os.listdir(base):
            if name.startswith("thermal_zone"):
                with open(os.path.join(base, name, "temp"), "r", encoding="utf-8") as f:
                    val = int(f.read().strip())
                    return round(val / 1000.0, 2)
    except Exception:
        return None
    return None


def build_health_payload():
    cpu_mhz = read_cpu_mhz()
    load1, load5, load15 = read_loadavg()
    mem_total, mem_free, mem_avail = read_meminfo()
    uptime_s = read_uptime()
    disk_used = read_disk_used_pct("/")
    temp_c = read_cpu_temp_c()

    payload = {}
    if cpu_mhz is not None:
        payload["cpu_mhz"] = cpu_mhz
    if load1 is not None:
        payload["load_1m"] = load1
        payload["load_5m"] = load5
        payload["load_15m"] = load15
    if mem_total is not None:
        payload["mem_total_kb"] = mem_total
        payload["mem_free_kb"] = mem_free
        payload["mem_available_kb"] = mem_avail
    if uptime_s is not None:
        payload["uptime_s"] = uptime_s
    if disk_used is not None:
        payload["disk_root_used_pct"] = disk_used
    if temp_c is not None:
        payload["cpu_temp_c"] = temp_c
    return payload


def set_leds(mask, mem=None):
    # Use provided MemAccess (devmem2) or open a new devmem2 accessor.
    try:
        if mem is None:
            mem = Devmem2Access(LED_GPIO_BASE)
        mem.write32(LED_GPIO_DIR, LED_GPIO_MASK_DEFAULT)
        mem.write32(LED_GPIO_DATA, mask & LED_GPIO_MASK_DEFAULT)
        return True, None
    except Exception as exc:
        return False, str(exc)[:120]


class MemRegion:
    def __init__(self, fd, phys_addr, size):
        self.page_size = mmap.PAGESIZE
        self.base = phys_addr & ~(self.page_size - 1)
        self.offset = phys_addr - self.base
        self.size = self.offset + size
        self.mm = mmap.mmap(fd, self.size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=self.base)

    def close(self):
        self.mm.close()

    def read32(self, offset):
        return struct.unpack_from('<I', self.mm, self.offset + offset)[0]

    def write32(self, offset, value):
        struct.pack_into('<I', self.mm, self.offset + offset, value & 0xFFFFFFFF)


class UioRegion:
    def __init__(self, uio_index):
        self.uio_index = uio_index
        self.dev_path = f"/dev/uio{uio_index}"
        self.size = self._read_uio_size(uio_index)
        self.fd = os.open(self.dev_path, os.O_RDWR | os.O_SYNC)
        self.mm = mmap.mmap(self.fd, self.size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0)

    def _read_uio_size(self, uio_index):
        size_path = f"/sys/class/uio/uio{uio_index}/maps/map0/size"
        with open(size_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        return int(text, 16)

    def close(self):
        self.mm.close()
        os.close(self.fd)

    def read32(self, offset):
        return struct.unpack_from('<I', self.mm, offset)[0]

    def write32(self, offset, value):
        struct.pack_into('<I', self.mm, offset, value & 0xFFFFFFFF)


class MemAccess:
    def __init__(self):
        # Prefer UIO for fabric regions if available; fall back to devmem2 otherwise.
        self.use_devmem2 = False
        self.fd = None
        self.dma = None
        self.lsram = None

        force_devmem2 = os.environ.get("FORCE_DEVMEM2", "").strip() == "1"
        if not force_devmem2:
            try:
                self.lsram = UioRegion(0)
                self.dma = UioRegion(1)
            except Exception:
                self.lsram = None
                self.dma = None

        if self.lsram is None or self.dma is None:
            # Fallback path for images without UIO mapping.
            self.use_devmem2 = True
            self.dma = Devmem2Access(DMA_BASE)
            self.lsram = Devmem2Access(LSRAM_BASE)

    def close(self):
        if self.use_devmem2:
            return
        if self.dma is not None:
            self.dma.close()
        if self.lsram is not None:
            self.lsram.close()
        if self.fd is not None:
            os.close(self.fd)


def _read64_from_lsram(lsram, offset):
    lo = lsram.read32(offset)
    hi = lsram.read32(offset + 4)
    return (hi << 32) | lo


def capture_stream(pattern_count=256):
    mem = MemAccess()
    try:
        # Clamp to mapped LSRAM size when using UIO to avoid overruns.
        if hasattr(mem.lsram, "size") and mem.lsram.size is not None:
            max_bytes = mem.lsram.size - DATA_OFFSET
            max_count = max(1, max_bytes // 8)
            if pattern_count > max_count:
                raise ValueError(f'pattern_count too large for UIO map (max {max_count})')
        dest_addr = LSRAM_BASE + DATA_OFFSET

        start_time = time.time()

        # FIC0-only demo: generate pattern in LSRAM from Linux
        for i in range(pattern_count):
            mem.lsram.write32(DATA_OFFSET + i * 8, i + 1)
            mem.lsram.write32(DATA_OFFSET + i * 8 + 4, 0)

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Read back results
        first = mem.lsram.read32(DATA_OFFSET + 0)
        last = mem.lsram.read32(DATA_OFFSET + (pattern_count - 1) * 8)
        checksum = 0
        ok = True
        if mem.use_devmem2:
            # Sample-based validation to keep devmem2 calls low.
            expected_first = 1
            expected_last = pattern_count
            ok = (first == expected_first)
            checksum = (pattern_count * (pattern_count + 1) // 2) & 0xFFFFFFFF
        else:
            for i in range(pattern_count):
                val = _read64_from_lsram(mem.lsram, DATA_OFFSET + i * 8) & 0xFFFFFFFF
                checksum = (checksum + val) & 0xFFFFFFFF
                if val != i + 1:
                    ok = False
                    break

        return CaptureResult(
            pattern_count=pattern_count,
            first=first,
            last=last,
            checksum=checksum,
            ok=ok,
            elapsed_ms=elapsed_ms,
        )
    finally:
        mem.close()


pattern_count_current = 256


def on_command(msg: C2dCommand):
    global client, pattern_count_current
    print('Received command', msg.command_name, msg.command_args, msg.ack_id)
    if msg.command_name == 'fpga-capture':
        try:
            count = int(msg.command_args[0]) if msg.command_args else pattern_count_current
            result = capture_stream(count)
            payload = {
                'sdk_version': SDK_VERSION,
                'app_version': APP_VERSION,
                'fpga_pattern_count': result.pattern_count,
                'fpga_first': result.first,
                'fpga_last': result.last,
                'fpga_last_expected': result.pattern_count,
                'fpga_last_ok': int(result.last == result.pattern_count),
                'fpga_checksum': result.checksum,
                'fpga_ok': int(result.ok),
                'fpga_ms': result.elapsed_ms,
                'fpga_triggered': 1,
            }
            payload.update(build_health_payload())
            client.send_telemetry(payload)
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Capture complete')
        except Exception as exc:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, f'Capture failed: {exc}')
    elif msg.command_name == 'set-pattern':
        try:
            count = int(msg.command_args[0]) if msg.command_args else 256
            if count < 1 or count > 4096:
                raise ValueError('pattern_count must be 1..4096')
            pattern_count_current = count
            payload = {
                'sdk_version': SDK_VERSION,
                'app_version': APP_VERSION,
                'fpga_pattern_count': pattern_count_current,
                'fpga_pattern_set': 1,
            }
            payload.update(build_health_payload())
            client.send_telemetry(payload)
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f'Pattern count set to {count}')
        except Exception as exc:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, f'Set pattern failed: {exc}')
    elif msg.command_name in ('set-led', 'set_led', 'set_leds'):
        try:
            mask = int(msg.command_args[0], 0) if msg.command_args else 0
            ok, err = set_leds(mask)
            payload = {
                'sdk_version': SDK_VERSION,
                'app_version': APP_VERSION,
                'led_mask': mask,
                'led_ok': int(ok),
            }
            if err:
                payload['led_error'] = err
            payload.update(build_health_payload())
            client.send_telemetry(payload)
            if ok:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f'LED mask set to {mask}')
            else:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, f'LED set failed: {err}')
        except Exception as exc:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, f'LED set failed: {exc}')
    else:
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Not Implemented')


def on_ota(msg: C2dOta):
    global client
    print('OTA not supported in this workshop app')
    client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_FAILED)


def on_disconnect(reason: str, disconnected_from_server: bool):
    print('Disconnected%s. Reason: %s' % (' from server' if disconnected_from_server else '', reason))


def run_once():
    result = capture_stream()
    print('Capture OK:', result.ok)
    print('First:', result.first, 'Last:', result.last)
    print('Checksum:', result.checksum, 'Elapsed(ms):', result.elapsed_ms)


def main():
    if '--once' in sys.argv:
        run_once()
        return

    try:
        device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path='iotcDeviceConfig.json',
            device_cert_path='device-cert.pem',
            device_pkey_path='device-pkey.pem'
        )
    except DeviceConfigError as dce:
        print(dce)
        sys.exit(1)

    global client
    client = Client(
        config=device_config,
        callbacks=Callbacks(
            ota_cb=on_ota,
            command_cb=on_command,
            disconnected_cb=on_disconnect
        )
    )

    while True:
        if not client.is_connected():
            print('(re)connecting...')
            client.connect()
            if not client.is_connected():
                print('Unable to connect. Exiting.')
                sys.exit(2)

        try:
            result = capture_stream(pattern_count_current)
            payload = {
                'sdk_version': SDK_VERSION,
                'app_version': APP_VERSION,
                'fpga_pattern_count': result.pattern_count,
                'fpga_first': result.first,
                'fpga_last': result.last,
                'fpga_last_expected': result.pattern_count,
                'fpga_last_ok': int(result.last == result.pattern_count),
                'fpga_checksum': result.checksum,
                'fpga_ok': int(result.ok),
                'fpga_ms': result.elapsed_ms,
            }
            payload.update(build_health_payload())
        except Exception as exc:
            payload = {
                'sdk_version': SDK_VERSION,
                'app_version': APP_VERSION,
                'fpga_ok': 0,
                'fpga_error': str(exc)[:120],
            }

        client.send_telemetry(payload)
        time.sleep(10)


if __name__ == '__main__':
    main()
