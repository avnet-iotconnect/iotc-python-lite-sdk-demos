"""List all USB devices to find XArm VID/PID."""
import usb.core
import usb.util


def main():
    print("USB Devices:")
    devices = usb.core.find(find_all=True)
    for device in devices:
        try:
            print(f"VID: 0x{device.idVendor:04x}, PID: 0x{device.idProduct:04x}")
            print(f"  Manufacturer: {usb.util.get_string(device, device.iManufacturer)}")
            print(f"  Product: {usb.util.get_string(device, device.iProduct)}")
            print(f"  Serial: {usb.util.get_string(device, device.iSerialNumber)}")
            print()
        except:
            print(f"VID: 0x{device.idVendor:04x}, PID: 0x{device.idProduct:04x}")
            print("  (Could not read strings)")
            print()


if __name__ == "__main__":
    main()
