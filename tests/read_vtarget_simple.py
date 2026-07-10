#!/usr/bin/env python3
"""Minimal VTarget read: detach/reattach USBIP, drain stale data, read voltage."""
import sys
import time
import subprocess
print("Starting...", flush=True)

VID = 0xC251
PID = 0xF00A
CMD_DAP_VENDOR1 = 0x81
TIMEOUT_MS = 3000
PACKET_SIZE = 64
USBIP_EXE = r"C:\Program Files\USBip\usbip.exe"
ESP32_IP   = "192.168.137.123"
ESP32_BUS  = "1-1"

import usb.core
import usb.backend.libusb1
print("pyusb imported", flush=True)

try:
    import libusb_package
    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    print(f"libusb backend: {backend}", flush=True)
except ImportError:
    backend = None
    print("No libusb_package, using default", flush=True)

# --- Fresh USBIP attach ---
print("\nDetaching USBIP port 01...", flush=True)
subprocess.run([USBIP_EXE, "detach", "-p", "01"], capture_output=True)
time.sleep(1)
print("Attaching USBIP...", flush=True)
r = subprocess.run([USBIP_EXE, "attach", "-r", ESP32_IP, "-b", ESP32_BUS],
                   capture_output=True, timeout=10)
if r.returncode != 0 and b"succesfully" not in r.stdout and b"already" not in r.stdout.lower():
    print(f"USBIP attach failed: {r.stdout} {r.stderr}", flush=True)
    sys.exit(1)
print(f"USBIP attached: {r.stdout.decode().strip()}", flush=True)
time.sleep(2)  # allow enumeration

dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
if dev is None:
    print("ERROR: Device not found after USBIP attach", flush=True)
    sys.exit(1)

print(f"Device found: {dev.idVendor:#06x}/{dev.idProduct:#06x}", flush=True)

# Get configuration and endpoints
cfg = dev.get_active_configuration()
intf = cfg[(0, 0)]
print(f"Interface class={intf.bInterfaceClass}, subclass={intf.bInterfaceSubClass}, num_ep={intf.bNumEndpoints}", flush=True)

ep_out = None
ep_in  = None
for ep in intf:
    import usb.util as uu
    ep_type = ep.bmAttributes & 0x3
    ep_dir  = uu.endpoint_direction(ep.bEndpointAddress)
    print(f"  EP {ep.bEndpointAddress:#04x}: type={ep_type} (2=bulk) dir={'IN' if ep_dir else 'OUT'} maxpkt={ep.wMaxPacketSize}", flush=True)
    if ep_dir == uu.ENDPOINT_OUT and ep_out is None:
        ep_out = ep
    elif ep_dir == uu.ENDPOINT_IN and ep_in is None:
        ep_in = ep   # first IN = EP 0x81 (CMSIS-DAP responses); second IN = EP 0x82 (SWO)

if not ep_out or not ep_in:
    print("ERROR: Could not find IN/OUT endpoints", flush=True)
    sys.exit(1)

# --- Drain stale data ---
# Each drain read triggers the firmware to respond:
#   dap_req_num==0 → firmware sends ZLP (0 bytes) immediately
#   stale buffered data from previous session → non-zero bytes
# Stop draining when we get 0 bytes (firmware is clean).
print(f"\nDraining stale data from ep {ep_in.bEndpointAddress:#04x}...", flush=True)
for i in range(50):
    try:
        stale = dev.read(ep_in.bEndpointAddress, PACKET_SIZE + 1, 500)
        if len(stale) == 0:
            print(f"  chunk {i+1}: 0 bytes — firmware clean, drain complete", flush=True)
            break
        print(f"  chunk {i+1}: {len(stale)} bytes (stale): {list(stale[:4])} ...", flush=True)
    except usb.core.USBTimeoutError:
        print(f"  timeout after {i} chunks — drain complete", flush=True)
        break
    except Exception as e:
        print(f"  drain stopped at chunk {i}: {e}", flush=True)
        sys.exit(1)

# --- Send DAP_Vendor1 command ---
pkt = bytearray(PACKET_SIZE)
pkt[0] = CMD_DAP_VENDOR1
print(f"\nWriting {len(pkt)} bytes to ep {ep_out.bEndpointAddress:#04x}...", flush=True)
try:
    n = dev.write(ep_out.bEndpointAddress, bytes(pkt), TIMEOUT_MS)
    print(f"  wrote {n} bytes", flush=True)
except Exception as e:
    print(f"  WRITE ERROR: {e}", flush=True)
    sys.exit(1)

print(f"Reading from ep {ep_in.bEndpointAddress:#04x} (timeout={TIMEOUT_MS}ms)...", flush=True)
try:
    resp = dev.read(ep_in.bEndpointAddress, PACKET_SIZE + 1, TIMEOUT_MS)
    print(f"  got {len(resp)} bytes: {list(resp[:8])} ...", flush=True)
except Exception as e:
    print(f"  READ ERROR: {e}", flush=True)
    sys.exit(1)

# --- Parse response ---
data = list(resp)
# Strip optional HID report-ID byte (0x00) if present
if data and data[0] == 0x00:
    data = data[1:]

voltage_mv = None
for offset in range(min(3, len(data))):
    if data[offset] == CMD_DAP_VENDOR1 and len(data) > offset + 2:
        voltage_mv = data[offset+1] | (data[offset+2] << 8)
        break

if voltage_mv is not None:
    print(f"\n=== VTarget = {voltage_mv} mV  ({voltage_mv/1000:.3f} V) ===", flush=True)
    sys.exit(0)
else:
    print(f"\nCould not parse VTarget. Response: {data[:8]}", flush=True)
    sys.exit(1)
