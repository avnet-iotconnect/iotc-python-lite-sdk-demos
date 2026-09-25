# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# /IOTCONNECT drone simulator for the "tykho_drone" device template.
#
# Simulates a quadcopter flight controller and reports telemetry matching the
# attributes used by the "Witekio and Indeema Drone Platform" dashboard.
#
# Telemetry cadence:
#   * Normal mode: one message every NORMAL_INTERVAL seconds (default 90 s).
#   * Demo mode:   one message every DEMO_INTERVAL seconds (default 3 s).
#
# Demo mode is entered when the "demo" command arrives from the dashboard's
# Demo button (the dashboard sends "demo 5 60 1010"). The first argument is
# treated as the demo duration in minutes. When the demo expires, the
# simulator lands the drone and returns to the normal cadence.
#
# Supported cloud-to-device commands (all defined in the tykho_drone template):
#   demo [minutes] [...]    Start demo mode for N minutes (default 5). "demo 0" or
#                           "demo off" stops it. Pressing again restarts the timer.
#   on                      Start demo mode with no time limit.
#   off                     Stop demo mode.
#   pwm <1000-2000>         Set the commanded motor PWM (Throttle / Motor switches).
#   SetInterval <secs> [demo_secs]
#                           Change the normal (and optionally demo) interval.

import argparse
import math
import os
import random
import sys
import threading
import time

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite.client import ClientSettings
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

DEFAULT_NORMAL_INTERVAL_SECS = 90
DEFAULT_DEMO_INTERVAL_SECS = 3
DEFAULT_DEMO_DURATION_MINUTES = 5

PWM_MIN = 1000
PWM_MAX = 2000
PWM_FLIGHT_THRESHOLD = 1100  # commanded PWM at or above this spins up and hovers

CONTROLLER_INFO = {
    "name": "Betaflight",
    "variant": "BTFL",
    "version": "4.5.1",
    "board_info": "STM32H743 (SPRACINGH7EXTREME)",
    "api_version": "1.46",
}

BATTERY_CELL_COUNT = 6
BATTERY_CAPACITY_MAH = 5200
CELL_FULL_VOLTS = 4.18
CELL_EMPTY_VOLTS = 3.45
BATTERY_STATE_OK = 0
BATTERY_STATE_WARNING = 1
BATTERY_STATE_CRITICAL = 2


def clamp(value, low, high):
    return max(low, min(high, value))


class DroneSimulator:
    """
    Holds the simulated drone state and the reporting schedule.

    All public methods are thread safe: the /IOTCONNECT SDK delivers commands on
    its MQTT network thread while the main thread drives the telemetry loop.
    """

    def __init__(self, normal_interval: float, demo_interval: float, demo_duration_minutes: float):
        self._lock = threading.Lock()
        self.wake = threading.Event()  # set whenever the schedule should be re-evaluated immediately

        self.normal_interval = float(normal_interval)
        self.demo_interval = float(demo_interval)
        self.default_demo_duration_secs = float(demo_duration_minutes) * 60.0

        self.demo_active = False
        self.demo_ends_at = None  # monotonic timestamp, or None for "until told to stop"

        # Operator inputs
        self.commanded_pwm = PWM_MIN

        # Flight state
        self.altitude_cm = 0.0
        self.target_altitude_cm = 0.0
        self.heading = random.uniform(0.0, 360.0)
        self.roll = 0.0
        self.pitch = 0.0
        self.throttle = 0.0  # 0..1 effective throttle actually being flown

        # Battery state
        self.mah_drawn = 0.0
        self.amperage = 0.18

        self._last_step = time.monotonic()
        self._mission_phase_started = self._last_step
        self._mission_phase = "ground"

    # ------------------------------------------------------------------ schedule

    def current_interval(self) -> float:
        with self._lock:
            return self.demo_interval if self.demo_active else self.normal_interval

    def start_demo(self, duration_secs=None):
        """Enter demo mode. duration_secs=None means run until stopped."""
        with self._lock:
            self.demo_active = True
            self.demo_ends_at = None if duration_secs is None else time.monotonic() + duration_secs
            self._set_mission_phase("takeoff")
        self.wake.set()

    def stop_demo(self):
        with self._lock:
            self.demo_active = False
            self.demo_ends_at = None
            self._set_mission_phase("landing")
        self.wake.set()

    def set_pwm(self, pwm: int):
        with self._lock:
            self.commanded_pwm = int(clamp(pwm, PWM_MIN, PWM_MAX))
        self.wake.set()

    def set_intervals(self, normal_secs=None, demo_secs=None):
        with self._lock:
            if normal_secs is not None:
                self.normal_interval = max(1.0, float(normal_secs))
            if demo_secs is not None:
                self.demo_interval = max(1.0, float(demo_secs))
        self.wake.set()

    def demo_seconds_remaining(self):
        with self._lock:
            if not self.demo_active:
                return 0
            if self.demo_ends_at is None:
                return None
            return max(0.0, self.demo_ends_at - time.monotonic())

    # ------------------------------------------------------------------ physics

    def _set_mission_phase(self, phase: str):
        self._mission_phase = phase
        self._mission_phase_started = time.monotonic()

    def _advance_mission(self, now: float):
        """
        Demo mode flies a repeating scripted mission:
        takeoff -> cruise (turning) -> hover -> landing -> ground -> takeoff ...
        Outside demo mode the commanded PWM decides whether the drone hovers.
        """
        elapsed = now - self._mission_phase_started

        if self.demo_active:
            if self._mission_phase in ("ground", "landing") and self.altitude_cm < 5.0:
                self._set_mission_phase("takeoff")
            elif self._mission_phase == "takeoff":
                self.throttle = 0.72
                self.target_altitude_cm = 2500.0
                if self.altitude_cm > 2000.0:
                    self._set_mission_phase("cruise")
            elif self._mission_phase == "cruise":
                self.throttle = 0.58
                self.target_altitude_cm = 2500.0 + 600.0 * math.sin(elapsed / 9.0)
                if elapsed > 75.0:
                    self._set_mission_phase("hover")
            elif self._mission_phase == "hover":
                self.throttle = 0.52
                self.target_altitude_cm = 1500.0
                if elapsed > 30.0:
                    self._set_mission_phase("landing")
            elif self._mission_phase == "landing":
                self.throttle = 0.40
                self.target_altitude_cm = 0.0
                if self.altitude_cm < 5.0:
                    self._set_mission_phase("ground")
            return

        # Manual mode: the Throttle / Motor switches drive the aircraft.
        if self.commanded_pwm >= PWM_FLIGHT_THRESHOLD:
            fraction = (self.commanded_pwm - PWM_MIN) / float(PWM_MAX - PWM_MIN)
            self.throttle = clamp(fraction, 0.3, 0.9)
            self.target_altitude_cm = 300.0 + 2700.0 * fraction
            if self._mission_phase != "hover":
                self._set_mission_phase("hover")
        else:
            self.throttle = 0.0
            self.target_altitude_cm = 0.0
            if self.altitude_cm < 5.0 and self._mission_phase != "ground":
                self._set_mission_phase("ground")
            elif self.altitude_cm >= 5.0 and self._mission_phase != "landing":
                self._set_mission_phase("landing")

    def step(self):
        """Advance the simulation by the wall-clock time since the last step."""
        with self._lock:
            now = time.monotonic()
            dt = clamp(now - self._last_step, 0.0, 120.0)
            self._last_step = now

            if self.demo_active and self.demo_ends_at is not None and now >= self.demo_ends_at:
                self.demo_active = False
                self.demo_ends_at = None
                print("Demo period finished. Returning to normal reporting interval.")

            self._advance_mission(now)

            # Altitude follows the target with a limited climb/descent rate.
            climb_rate = 180.0 if self.demo_active else 120.0  # cm/s
            delta = self.target_altitude_cm - self.altitude_cm
            self.altitude_cm += clamp(delta, -climb_rate * dt, climb_rate * dt)
            self.altitude_cm = max(0.0, self.altitude_cm)
            airborne = self.altitude_cm > 5.0

            if airborne:
                if self._mission_phase == "cruise":
                    self.heading = (self.heading + 12.0 * dt) % 360.0
                    self.roll = 18.0 * math.sin(now / 4.0) + random.uniform(-1.5, 1.5)
                    self.pitch = -8.0 + 4.0 * math.sin(now / 6.0) + random.uniform(-1.0, 1.0)
                else:
                    self.heading = (self.heading + random.uniform(-0.8, 0.8) * dt) % 360.0
                    self.roll = 2.5 * math.sin(now / 3.0) + random.uniform(-1.0, 1.0)
                    self.pitch = 2.0 * math.cos(now / 3.5) + random.uniform(-1.0, 1.0)
                self.amperage = 4.0 + 40.0 * self.throttle + random.uniform(-1.5, 1.5)
            else:
                self.roll = random.uniform(-0.4, 0.4)
                self.pitch = random.uniform(-0.4, 0.4)
                self.amperage = 0.18 + random.uniform(-0.03, 0.03)

            # Battery drain, with an automatic "battery swap" when it runs low on the ground.
            self.mah_drawn += self.amperage * dt / 3.6  # A * s -> mAh
            if self.mah_drawn > BATTERY_CAPACITY_MAH * 0.85 and not airborne:
                print("Simulated battery swap: resetting mAh drawn.")
                self.mah_drawn = 0.0

    # ---------------------------------------------------------------- telemetry

    def _battery_voltage(self) -> float:
        remaining = 1.0 - clamp(self.mah_drawn / BATTERY_CAPACITY_MAH, 0.0, 1.0)
        cell = CELL_EMPTY_VOLTS + (CELL_FULL_VOLTS - CELL_EMPTY_VOLTS) * remaining
        cell -= 0.012 * self.amperage / BATTERY_CELL_COUNT  # voltage sag under load
        return cell * BATTERY_CELL_COUNT

    def _motor_pwm(self):
        with self._lock:
            if self.altitude_cm > 5.0 or self.throttle > 0.0:
                base = PWM_MIN + self.throttle * (PWM_MAX - PWM_MIN)
                # Attitude corrections: roll differentiates left/right, pitch front/back.
                roll_mix = self.roll * 2.5
                pitch_mix = self.pitch * 2.5
                motors = [
                    base + roll_mix - pitch_mix,   # front-left
                    base - roll_mix - pitch_mix,   # front-right
                    base - roll_mix + pitch_mix,   # rear-right
                    base + roll_mix + pitch_mix,   # rear-left
                ]
                return [int(clamp(m + random.uniform(-8, 8), PWM_MIN, PWM_MAX)) for m in motors]
            return [int(clamp(self.commanded_pwm, PWM_MIN, PWM_MAX))] * 4

    def build_telemetry(self) -> dict:
        motors = self._motor_pwm()
        with self._lock:
            airborne = self.altitude_cm > 5.0
            voltage = self._battery_voltage()
            cell_volts = voltage / BATTERY_CELL_COUNT
            if cell_volts < 3.55:
                battery_state = BATTERY_STATE_CRITICAL
            elif cell_volts < 3.70:
                battery_state = BATTERY_STATE_WARNING
            else:
                battery_state = BATTERY_STATE_OK

            if airborne:
                gyro = [random.gauss(0.0, 6.0), random.gauss(0.0, 6.0), random.gauss(0.0, 3.0)]
                accel = [
                    int(random.gauss(-self.pitch * 8.0, 20.0)),
                    int(random.gauss(self.roll * 8.0, 20.0)),
                    int(random.gauss(512.0 * (1.0 + 0.3 * self.throttle), 25.0)),
                ]
            else:
                gyro = [random.gauss(0.0, 0.3), random.gauss(0.0, 0.3), random.gauss(0.0, 0.2)]
                accel = [int(random.gauss(0.0, 3.0)), int(random.gauss(0.0, 3.0)), int(random.gauss(512.0, 3.0))]

            return {
                "Attitude": {
                    "heading": round(self.heading, 1) + 0.0,
                    "angX": round(self.roll, 1) + 0.0,
                    "angY": round(self.pitch, 1) + 0.0,
                },
                "Battery": {
                    "State": battery_state,
                    "Voltage": round(voltage, 2),
                    "Amperage": round(self.amperage, 2),
                    "Capacity": BATTERY_CAPACITY_MAH,
                    "CellCount": BATTERY_CELL_COUNT,
                    "mAhDrawn": int(self.mah_drawn),
                },
                "Motor": {
                    "PWM1": motors[0],
                    "PWM2": motors[1],
                    "PWM3": motors[2],
                    "PWM4": motors[3],
                },
                "Gyroscope": {
                    "x": round(gyro[0], 2),
                    "y": round(gyro[1], 2),
                    "z": round(gyro[2], 2),
                },
                "Accelerometer": {
                    "x": accel[0],
                    "y": accel[1],
                    "z": accel[2],
                },
                "Altitude": int(self.altitude_cm),
                "ControllerInfo": dict(CONTROLLER_INFO),
                "DemoOn": 1 if self.demo_active else 0,
            }


# ---------------------------------------------------------------------- commands

def parse_demo_args(args, default_duration_secs):
    """
    Returns (start: bool, duration_secs or None).
    The dashboard Demo button sends "demo 5 60 1010"; the first value is minutes.
    """
    if len(args) == 0:
        return True, default_duration_secs
    first = args[0].strip().lower()
    if first in ("off", "stop", "0", "false"):
        return False, None
    if first in ("on", "start", "true"):
        return True, default_duration_secs
    try:
        minutes = float(first)
    except ValueError:
        return True, default_duration_secs
    if minutes <= 0:
        return False, None
    return True, minutes * 60.0


def make_command_handler(client_ref: dict, sim: DroneSimulator):
    def ack(msg: C2dCommand, ok: bool, text: str):
        print(text)
        client = client_ref.get("client")
        # Commands in the tykho_drone template do not require an ack, so ack_id is normally None.
        if client is not None and msg.ack_id:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, text)

    def on_command(msg: C2dCommand):
        name = (msg.command_name or "").strip()
        args = list(msg.command_args or [])
        print("Received command: %s %s" % (name, " ".join(args)))
        lname = name.lower()

        if lname == "demo":
            start, duration = parse_demo_args(args, sim.default_demo_duration_secs)
            if start:
                sim.start_demo(duration)
                ack(msg, True, "Demo started for %.0f minutes. Reporting every %.0f s." % (duration / 60.0, sim.demo_interval))
            else:
                sim.stop_demo()
                ack(msg, True, "Demo stopped. Reporting every %.0f s." % sim.normal_interval)

        elif lname == "on":
            sim.start_demo(None)
            ack(msg, True, "Demo started (no time limit). Reporting every %.0f s." % sim.demo_interval)

        elif lname == "off":
            sim.stop_demo()
            ack(msg, True, "Demo stopped. Reporting every %.0f s." % sim.normal_interval)

        elif lname == "pwm":
            try:
                pwm = int(float(args[0]))
            except (IndexError, ValueError):
                ack(msg, False, "pwm command expects one integer argument between %d and %d" % (PWM_MIN, PWM_MAX))
                return
            sim.set_pwm(pwm)
            ack(msg, True, "Motor PWM set to %d" % pwm)

        elif lname == "setinterval":
            try:
                normal = float(args[0])
                demo = float(args[1]) if len(args) > 1 else None
            except (IndexError, ValueError):
                ack(msg, False, "SetInterval expects <normal_seconds> [demo_seconds]")
                return
            sim.set_intervals(normal, demo)
            ack(msg, True, "Intervals: normal=%.0f s, demo=%.0f s" % (sim.normal_interval, sim.demo_interval))

        else:
            ack(msg, False, "Command '%s' is not implemented by the simulator" % name)

    return on_command


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))


# -------------------------------------------------------------------------- main

def parse_cli():
    p = argparse.ArgumentParser(description="/IOTCONNECT tykho_drone device simulator")
    p.add_argument("--config", default=os.environ.get("IOTC_DEVICE_CONFIG", "iotcDeviceConfig.json"),
                   help="Path to iotcDeviceConfig.json (env IOTC_DEVICE_CONFIG)")
    p.add_argument("--cert", default=os.environ.get("IOTC_DEVICE_CERT", "device-cert.pem"),
                   help="Path to the device certificate (env IOTC_DEVICE_CERT)")
    p.add_argument("--key", default=os.environ.get("IOTC_DEVICE_KEY", "device-pkey.pem"),
                   help="Path to the device private key (env IOTC_DEVICE_KEY)")
    p.add_argument("--normal-interval", type=float, default=float(os.environ.get("NORMAL_INTERVAL_SECS", DEFAULT_NORMAL_INTERVAL_SECS)),
                   help="Seconds between telemetry messages outside demo mode (default %d)" % DEFAULT_NORMAL_INTERVAL_SECS)
    p.add_argument("--demo-interval", type=float, default=float(os.environ.get("DEMO_INTERVAL_SECS", DEFAULT_DEMO_INTERVAL_SECS)),
                   help="Seconds between telemetry messages in demo mode (default %d)" % DEFAULT_DEMO_INTERVAL_SECS)
    p.add_argument("--demo-duration", type=float, default=float(os.environ.get("DEMO_DURATION_MINUTES", DEFAULT_DEMO_DURATION_MINUTES)),
                   help="Default demo duration in minutes when the demo command has no argument (default %d)" % DEFAULT_DEMO_DURATION_MINUTES)
    p.add_argument("--quiet", action="store_true", help="Reduce SDK logging")
    p.add_argument("--dry-run", action="store_true",
                   help="Do not connect to /IOTCONNECT; print telemetry locally. Useful for testing the simulation.")
    p.add_argument("--dry-run-demo", action="store_true", help="With --dry-run, start in demo mode")
    return p.parse_args()


def run_dry(sim: DroneSimulator, start_in_demo: bool):
    import json
    if start_in_demo:
        sim.start_demo(sim.default_demo_duration_secs)
    print("Dry run. Press Ctrl+C to stop.")
    while True:
        sim.step()
        print(json.dumps(sim.build_telemetry()))
        interval = sim.current_interval()
        sim.wake.clear()
        sim.wake.wait(timeout=interval)


def run(sim: DroneSimulator, args):
    client_ref = {}
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path=args.config,
        device_cert_path=args.cert,
        device_pkey_path=args.key,
    )
    client = Client(
        config=device_config,
        callbacks=Callbacks(
            command_cb=make_command_handler(client_ref, sim),
            disconnected_cb=on_disconnect,
        ),
        settings=ClientSettings(verbose=not args.quiet),
    )
    client_ref["client"] = client

    print("Drone simulator for device '%s'. Normal interval %.0f s, demo interval %.0f s, default demo duration %.0f min."
          % (device_config.duid, sim.normal_interval, sim.demo_interval, sim.default_demo_duration_secs / 60.0))

    while True:
        if not client.is_connected():
            print("(re)connecting...")
            client.connect()
            if not client.is_connected():
                print("Unable to connect. Exiting.")
                sys.exit(2)

        sim.step()
        telemetry = sim.build_telemetry()
        remaining = sim.demo_seconds_remaining()
        mode = "DEMO" if telemetry["DemoOn"] else "normal"
        if remaining is not None and telemetry["DemoOn"]:
            mode += " (%ds left)" % int(remaining)
        print("[%s] alt=%dcm hdg=%.0f pwm=%s batt=%.2fV %.1fA"
              % (mode, telemetry["Altitude"], telemetry["Attitude"]["heading"],
                 telemetry["Motor"]["PWM1"], telemetry["Battery"]["Voltage"], telemetry["Battery"]["Amperage"]))
        client.send_telemetry(telemetry)

        # Sleep for the current interval, but wake up early if a command changed the schedule.
        sim.wake.clear()
        interval = sim.current_interval()
        remaining = sim.demo_seconds_remaining()
        if remaining is not None and telemetry["DemoOn"]:
            # Make sure we notice the demo ending promptly (at most one extra fast tick).
            interval = min(interval, max(0.5, remaining))
        sim.wake.wait(timeout=interval)


def main():
    args = parse_cli()
    sim = DroneSimulator(args.normal_interval, args.demo_interval, args.demo_duration)
    try:
        if args.dry_run:
            run_dry(sim, args.dry_run_demo)
        else:
            run(sim, args)
    except DeviceConfigError as dce:
        print(dce)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
