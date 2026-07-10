#!/usr/bin/env python3
"""
Minimal VTarget read test: send ONE CMSIS-DAP vendor command immediately after
USBIP attach, with no initialization overhead that stresses the WiFi link.

Uses pyusb (libusb_package) to talk directly to the bulk endpoint.

Usage:
    python read_vtarget_minimal.py

The script re-attaches USBIP itself so it starts with a clean device state.
"""
import sys
import time
import subprocess
import os

VID = 0xC251
PID = 0xF00A
USBIP_EXE = r"C:\Program Files\USBip\usbip.exe"
ESP32_IP  = "192.168.137.123"
ESP32_BUS = "1-1"
PACKET_SIZE = 64
TIMEOUT_MS  = 3000

CMD_DAP_VENDOR1 = 0x81   # Read VTarget


def attach_usbip():
    """Detach + reattach USBIP to start with a clean device state."""
    subprocess.run([USBIP_EXE, "detach", "-p", "01"], capture_output=True)
    time.sleep(1)
    r = subprocess.run([USBIP_EXE, "attach", "-r", ESP32_IP, "-b", ESP32_BUS],
                       capture_output=True, timeout=10)
    ok = r.returncode == 0 or b"succesfully" in r.stdout or b"already" in r.stdout.lower()
    if ok:
        print(f"USBIP attached: {ESP32_IP}/{ESP32_BUS}")
    else:
        print(f"USBIP attach failed: {r.stdout} {r.stderr}")
    time.sleep(2)  # let the virtual device enumerate
    return ok


def find_device(backend):
    import usb.core
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
    return dev


def get_endpoints(dev):
    """Return (ep_out, ep_in) for the first interface."""
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = None
    ep_in  = None
    for ep in intf:
        import usb.util
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep
        else:
            ep_in = ep
    return ep_out, ep_in


def send_vendor_read(dev, ep_out, ep_in):
    """Send DAP_Vendor1 (0x81) and read the mV response."""
    pkt = bytearray(PACKET_SIZE)
    pkt[0] = CMD_DAP_VENDOR1
    print(f"  -> write {len(pkt)} bytes: {list(pkt[:4])} ...")
    dev.write(ep_out.bEndpointAddress, bytes(pkt), TIMEOUT_MS)

    print(f"  <- reading response ...")
    resp = dev.read(ep_in.bEndpointAddress, PACKET_SIZE + 1, TIMEOUT_MS)
    print(f"  <- {len(resp)} bytes: {list(resp[:8])} ...")

    data = list(resp)
    # Strip optional report-ID byte (0x00) if present
    if data and data[0] == 0x00:
        data = data[1:]

    # Look for 0x81 echo in response
    for offset in range(min(3, len(data))):
        if data[offset] == CMD_DAP_VENDOR1 and len(data) > offset + 2:
            voltage_mv = data[offset+1] | (data[offset+2] << 8)
            return voltage_mv

    return None


def main():
    print("=" * 60)
    print("VTarget Minimal Read Test")
    print("=" * 60)

    import usb.core
    import usb.backend.libusb1
    try:
        import libusb_package
        backend = usb.backend.libusb1.get_backend(
            find_library=libusb_package.find_library)
        print("Using libusb_package backend")
    except ImportError:
        backend = None
        print("Using default libusb backend")

    for attempt in range(3):
        print(f"\n--- Attempt {attempt + 1} ---")

        # Fresh USBIP attach on first attempt; reattach on retry
        if attempt > 0:
            print("Reconnecting USBIP...")
            attach_usbip()
        else:
            # First attempt: just check if already attached; reattach anyway for clean state
            print("Attaching USBIP (clean state)...")
            attach_usbip()

        dev = find_device(backend)
        if dev is None:
            print("Device not found after attach")
            time.sleep(2)
            continue

        print(f"Device found: VID={dev.idVendor:#06x} PID={dev.idProduct:#06x}")

        try:
            ep_out, ep_in = get_endpoints(dev)
            if not ep_out or not ep_in:
                print("Endpoints not found")
                continue
            print(f"ep_out={ep_out.bEndpointAddress:#04x}  ep_in={ep_in.bEndpointAddress:#04x}")
            print(f"ep_out type={ep_out.bmAttributes & 0x3}  ep_in type={ep_in.bmAttributes & 0x3}  (3=interrupt, 2=bulk)")

            voltage_mv = send_vendor_read(dev, ep_out, ep_in)
            if voltage_mv is not None:
                print(f"\n{'='*40}")
                print(f"  VTarget = {voltage_mv} mV  ({voltage_mv/1000:.3f} V)")
                print(f"{'='*40}")
                return True
            else:
                print("Could not parse VTarget from response")
                # Try once more immediately (response might be stale data from prev session)
                print("Sending command again (in case first response was stale)...")
                try:
                    voltage_mv = send_vendor_read(dev, ep_out, ep_in)
                    if voltage_mv is not None:
                        print(f"\n{'='*40}")
                        print(f"  VTarget = {voltage_mv} mV  ({voltage_mv/1000:.3f} V)")
                        print(f"{'='*40}")
                        return True
                except Exception as e2:
                    print(f"  retry failed: {e2}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(1)

    print("\nFailed to read VTarget after all attempts.")
    return False


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
