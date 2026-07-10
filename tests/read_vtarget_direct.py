#!/usr/bin/env python3
"""
Direct VTarget read via raw CMSIS-DAP USB, bypassing pyOCD's open() initialization.

Uses pyusb (libusb1/WinUSB) to send DAP_Vendor1 (0x81) directly to the device
and decode the 16-bit mV response.

Usage:
    python read_vtarget_direct.py

Requires WinUSB driver (installed via Zadig) for VID=0xC251 / PID=0xF00A.
"""

import sys
import time

VID = 0xC251
PID = 0xF00A
PACKET_SIZE = 64

# CMSIS-DAP command bytes
CMD_DAP_INFO       = 0x00
CMD_DAP_VENDOR0    = 0x80
CMD_DAP_VENDOR1    = 0x81   # ID_DAP_Vendor1 = Read VTarget
CMD_DAP_VENDOR2    = 0x82   # ID_DAP_Vendor2 = Set VTarget

# DAP_Info IDs
DAP_ID_PACKET_COUNT = 0xFE
DAP_ID_PACKET_SIZE  = 0xFF

TIMEOUT_MS = 2000


def try_pyusb():
    """Try to communicate via pyusb (requires WinUSB driver from Zadig)."""
    try:
        import usb.core
        import usb.util
        import usb.backend.libusb1
    except ImportError:
        print("pyusb not available")
        return False

    # Try to locate libusb-1.0.dll via libusb_package (ships with pyOCD)
    backend = None
    try:
        import libusb_package
        backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    except ImportError:
        pass  # Fall back to default search

    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
    if dev is None:
        print("pyusb: device not found")
        return False

    print(f"pyusb: found device  VID={dev.idVendor:#06x}  PID={dev.idProduct:#06x}")
    try:
        print(f"       manufacturer={dev.manufacturer}  product={dev.product}")
    except Exception:
        print("       (string descriptors unavailable over USBIP)")

    # Find the HID interface (class 3) and its interrupt endpoints
    cfg = dev.get_active_configuration()
    intf = None
    ep_out = None
    ep_in  = None

    for i in cfg:
        if i.bInterfaceClass == 3:  # HID
            intf = i
            break

    if intf is None:
        # Try any interface
        intf = cfg[(0, 0)]

    print(f"       interface {intf.bInterfaceNumber} (class {intf.bInterfaceClass})")

    for ep in intf:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep
        else:
            ep_in = ep

    if ep_out is None or ep_in is None:
        print("pyusb: could not find interrupt endpoints")
        return False

    print(f"       ep_out=0x{ep_out.bEndpointAddress:02x}  ep_in=0x{ep_in.bEndpointAddress:02x}")

    # Drain any stale responses left by a previous crashed session (e.g. pyOCD init failure)
    print("Draining stale USB buffer...")
    stale_count = 0
    while True:
        try:
            stale = dev.read(ep_in.bEndpointAddress, PACKET_SIZE, 300)
            stale_count += 1
            print(f"  drained {len(stale)} bytes: {list(stale[:4])} ...")
        except Exception:
            break  # timeout = buffer empty
    if stale_count == 0:
        print("  (buffer was already empty)")

    # Build CMSIS-DAP DAP_Vendor1 command (Read VTarget).
    # When using libusb on HID interrupt endpoints, there is NO report ID byte —
    # the first byte of the transfer IS the CMSIS-DAP command byte.
    cmd_packet = bytearray(PACKET_SIZE)
    cmd_packet[0] = CMD_DAP_VENDOR1  # 0x81

    print(f"\nSending DAP_Vendor1 (0x81) to read VTarget...")
    try:
        n = dev.write(ep_out.bEndpointAddress, bytes(cmd_packet), TIMEOUT_MS)
        print(f"  wrote {n} bytes")
    except Exception as e:
        print(f"  write error: {e}")
        return False

    try:
        resp = dev.read(ep_in.bEndpointAddress, PACKET_SIZE + 1, TIMEOUT_MS)
        print(f"  read {len(resp)} bytes: {list(resp[:8])} ...")
    except Exception as e:
        print(f"  read error: {e}")
        return False

    # Response format (no report ID): [0x81, LOW, HIGH, ...]
    # If device prepends report ID 0x00, strip it first
    data = list(resp)
    if data and data[0] == 0x00:
        data = data[1:]  # strip report ID

    if len(data) >= 3 and data[0] == CMD_DAP_VENDOR1:
        voltage_mv = data[1] | (data[2] << 8)
        print(f"\nVTarget = {voltage_mv} mV  ({voltage_mv / 1000:.3f} V)")
        return True
    else:
        print(f"  unexpected response[0]={data[0] if data else 'empty'}: {data[:8]}")
        # Try first few variants in case of framing offset
        for offset in [0, 1, 2]:
            if len(data) > offset + 2 and data[offset] == CMD_DAP_VENDOR1:
                voltage_mv = data[offset+1] | (data[offset+2] << 8)
                print(f"  (offset={offset}) VTarget = {voltage_mv} mV  ({voltage_mv/1000:.3f} V)")
                return True
        return False


def try_hidapi():
    """Try to communicate via hidapi (requires native HID driver)."""
    try:
        import hid
    except ImportError:
        print("hidapi not available")
        return False

    # Enumerate all HID devices
    devices = hid.enumerate(VID, PID)
    if not devices:
        print("hidapi: device not found (WinUSB driver may be active instead of HID)")
        return False

    for d in devices:
        print(f"hidapi: found  path={d['path']}  usage_page={d['usage_page']:#06x}")

    try:
        dev = hid.device()
        dev.open(VID, PID)
        print(f"hidapi: opened  manufacturer={dev.get_manufacturer_string()}  product={dev.get_product_string()}")
    except Exception as e:
        print(f"hidapi: open error: {e}")
        return False

    # Build DAP_Vendor1 command
    # HID write: first byte is report ID (0x00), then CMSIS-DAP command
    cmd_packet = [0x00] + [CMD_DAP_VENDOR1] + [0x00] * (PACKET_SIZE - 1)

    print(f"\nSending DAP_Vendor1 (0x81) via HID to read VTarget...")
    try:
        n = dev.write(cmd_packet)
        print(f"  wrote {n} bytes")
    except Exception as e:
        print(f"  write error: {e}")
        dev.close()
        return False

    try:
        resp = dev.read(PACKET_SIZE, TIMEOUT_MS)
        print(f"  read {len(resp)} bytes: {list(resp[:8])} ...")
    except Exception as e:
        print(f"  read error: {e}")
        dev.close()
        return False

    dev.close()

    # HID response: [CMD_BYTE, LOW, HIGH, ...]  (no report ID prefix)
    if len(resp) >= 3 and resp[0] == CMD_DAP_VENDOR1:
        voltage_mv = resp[1] | (resp[2] << 8)
        print(f"\nVTarget = {voltage_mv} mV  ({voltage_mv / 1000:.3f} V)")
        return True
    else:
        print(f"  unexpected response: {list(resp[:8])}")
        return False


def try_pyocd_patched():
    """Try pyOCD with cmsis_dap.limit_packets=True to skip MAX_PACKET_COUNT query,
    then manually fix the remaining init to tolerate empty dap_info responses."""
    try:
        from pyocd.probe.pydapaccess import DAPAccess
        from pyocd.probe.pydapaccess.cmsis_dap_core import CmsisDapCore
    except ImportError:
        print("pyOCD not available")
        return False

    probes = DAPAccess.get_connected_devices()
    if not probes:
        print("pyOCD: no probes found")
        return False

    probe = probes[0]
    print(f"pyOCD: found probe  uid={probe.unique_id}  name={probe.product_name}")

    # Monkey-patch dap_info to tolerate empty responses
    original_dap_info = CmsisDapCore.dap_info

    def safe_dap_info(self, id_):
        try:
            return original_dap_info(self, id_)
        except (IndexError, Exception) as e:
            print(f"  dap_info({id_}) failed ({e}), returning None")
            return None

    CmsisDapCore.dap_info = safe_dap_info

    try:
        import pyocd.core.session as session_mod
        # Create a minimal session context so options work
        import pyocd.core.options as opts_mod

        probe._link.open()
        print(f"pyOCD: probe opened successfully!")
    except Exception as e:
        print(f"pyOCD: open error: {e}")
        return False
    finally:
        CmsisDapCore.dap_info = original_dap_info

    # Send vendor command
    try:
        response = probe.vendor(1, [])
        print(f"  vendor(1, []) response: {list(response)}")
        if len(response) >= 2:
            voltage_mv = response[0] | (response[1] << 8)
            print(f"\nVTarget = {voltage_mv} mV  ({voltage_mv / 1000:.3f} V)")
            return True
    except Exception as e:
        print(f"  vendor error: {e}")

    try:
        probe.close()
    except Exception:
        pass
    return False


if __name__ == "__main__":
    print("=" * 60)
    print("VTarget Direct Read Test")
    print(f"Target: VID={VID:#06x} PID={PID:#06x}")
    print("=" * 60)

    # Try methods in order
    print("\n--- Method 1: pyusb (WinUSB) ---")
    if try_pyusb():
        sys.exit(0)

    print("\n--- Method 2: hidapi (native HID) ---")
    if try_hidapi():
        sys.exit(0)

    print("\n--- Method 3: pyOCD with patched dap_info ---")
    if try_pyocd_patched():
        sys.exit(0)

    print("\nAll methods failed. Is the USBIP device attached?")
    print("  usbip.exe attach -r 192.168.137.123 -b 1-1")
    sys.exit(1)
