# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# PAC193x IIO sysfs Driver for SAMA7D65-Curiosity
# Reads voltage, current, and power from the kernel's IIO interface
# for the on-board PAC1934 power monitor.
#
# The PAC1934 kernel driver (pac1934.ko) claims the I2C device and
# exposes measurements via /sys/bus/iio/devices/iio:deviceN/.
# This module reads those sysfs files directly — no smbus2 needed.

import glob
import os

# Channel labels for SAMA7D65 Curiosity Board
CHANNEL_LABELS = {
    1: "VDD_3V3",
    2: "VDD_DDR_IO",
    3: "VDDCORE",
    4: "VDD_CPU"
}


def _read_sysfs(path):
    """Read a single sysfs file and return its stripped contents."""
    with open(path, 'r') as f:
        return f.read().strip()


def _read_sysfs_float(path):
    """Read a sysfs file as a float."""
    return float(_read_sysfs(path))


def _find_iio_device(name="pac1934"):
    """Find the IIO device path for the PAC1934.
    Returns the path like /sys/bus/iio/devices/iio:device1 or None."""
    for dev_path in sorted(glob.glob("/sys/bus/iio/devices/iio:device*")):
        name_path = os.path.join(dev_path, "name")
        if os.path.exists(name_path):
            if _read_sysfs(name_path) == name:
                return dev_path
    return None


class PAC193x:
    """Driver for PAC1934 power/energy monitor via kernel IIO sysfs."""

    def __init__(self, iio_device_path=None):
        if iio_device_path:
            self.iio_path = iio_device_path
        else:
            self.iio_path = _find_iio_device()
        if self.iio_path is None:
            raise RuntimeError(
                "PAC1934 IIO device not found. Check that:\n"
                "  - Jumpers J6 and J7 are set to pins 2-3 (MPU I2C)\n"
                "  - The pac1934 kernel module is loaded (lsmod | grep pac1934)\n"
                "  - The device appears in: ls /sys/bus/iio/devices/iio:device*/name"
            )
        self._scales = {}
        self._initialized = False

    def initialize(self):
        """Cache the scale factors (they don't change at runtime)."""
        for ch in range(1, 5):
            self._scales[ch] = {
                'voltage': _read_sysfs_float(os.path.join(self.iio_path, f"in_voltage{ch}_scale")),
                'current': _read_sysfs_float(os.path.join(self.iio_path, f"in_current{ch}_scale")),
                'power':   _read_sysfs_float(os.path.join(self.iio_path, f"in_power{ch}_scale")),
            }
        self._initialized = True

    def get_vbus_mv(self, channel):
        """Get bus voltage for a channel in millivolts."""
        raw = _read_sysfs_float(os.path.join(self.iio_path, f"in_voltage{channel}_raw"))
        return round(raw * self._scales[channel]['voltage'], 2)

    def get_isense_ma(self, channel):
        """Get sense current for a channel in milliamps."""
        raw = _read_sysfs_float(os.path.join(self.iio_path, f"in_current{channel}_raw"))
        return round(raw * self._scales[channel]['current'], 3)

    def get_power_mw(self, channel):
        """Get power for a channel in milliwatts.
        IIO power scale produces microwatts, so divide by 1000."""
        raw = _read_sysfs_float(os.path.join(self.iio_path, f"in_power{channel}_raw"))
        power_uw = raw * self._scales[channel]['power']
        return round(power_uw / 1000.0, 3)

    def get_channel(self, channel):
        """Read voltage, current, and power for a single channel."""
        if channel < 1 or channel > 4:
            raise ValueError("Channel must be 1-4")
        return {
            'label': CHANNEL_LABELS.get(channel, f"CH{channel}"),
            'vbus_mv': self.get_vbus_mv(channel),
            'isense_ma': self.get_isense_ma(channel),
            'power_mw': self.get_power_mw(channel),
        }

    def get_all_channels(self):
        """Read voltage, current, and power for all 4 channels.
        Returns a dict keyed by channel number (1-4)."""
        results = {}
        for ch in range(1, 5):
            results[ch] = self.get_channel(ch)
        return results

    def close(self):
        """No-op for sysfs interface (nothing to close)."""
        pass
