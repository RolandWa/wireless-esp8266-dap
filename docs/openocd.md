# OpenOCD / pyOCD — wireless-esp8266-dap

The device exposes a full CMSIS-DAP v2 interface (SWD + JTAG + SWO) over WiFi.
OpenOCD connects to it directly via TCP — **no USB cable, no kernel driver,
no USBIP** required.

---

## Architecture overview

```
Target MCU
  ↕  SWD/JTAG (GPIO)
ESP32-C3 XIAO (192.168.137.123)
  ↕  TCP port 3240  — elaphureLink protocol
Windows PC
  ↕  TCP pipe (no USB, no kernel driver)
c:\openocd\elaphurelink\bin\openocd.exe
  ↕  TCL RPC port 6666 / GDB port 3333
pyOCD / GDB / your tool
```

The firmware on port 3240 accepts three protocol variants on the same socket
(distinguished by the first 4 bytes of the TCP stream):

| First bytes | Protocol | Caller |
| ----------- | -------- | ------ |
| `0x8a656c70` | **elaphureLink** — lightweight binary, direct DAP | elaphureLink OpenOCD |
| `0x8005` / `0x8003` low 16 bits | USBIP stage-1 | Windows USBIP kernel driver *(broken for IN)* |
| `0x47455420` ("GET ") | WebSocket DAP | browser / WebSocket client |

---

## Path 1 — elaphureLink OpenOCD (recommended, confirmed working)

Uses the elaphureLink-patched OpenOCD already installed at
`c:\openocd\elaphurelink\`.

### What is elaphureLink?

A minimal binary TCP protocol designed for this firmware:

1. **Handshake** (12 bytes each way):
   ```
   Client → Device: magic(4BE) + cmd=0(4BE) + client_version(4BE)
   Device → Client: magic(4BE) + cmd=0(4BE) + dap_version(4BE)
   ```
2. **Data loop**: raw CMSIS-DAP commands/responses with no additional framing.
   No USBIP headers, no USB descriptors, no kernel driver.

DAP info reported by the firmware: Vendor=`windowsair`, Product=`CMSIS-DAP v2`,
FW Version=`2.1.0`, SWD+JTAG+SWO Manchester, packet size 512 bytes.

### Quick test (no target needed)

```bat
c:\openocd\elaphurelink\bin\openocd.exe ^
  -s c:\openocd\elaphurelink\share\openocd\scripts ^
  -f openocd/elaphurelink.cfg ^
  --command "init; dap info; exit"
```

Expected output:
```
Info : CMSIS-DAP: SWD supported
Info : CMSIS-DAP: JTAG supported
Info : CMSIS-DAP: FW Version = 2.1.0
Info : CMSIS-DAP: Serial# = 1234
Info : CMSIS-DAP: Interface ready
Info : clock speed 1000 kHz
```

### Debug a real target (e.g. STM32F4)

```bat
c:\openocd\elaphurelink\bin\openocd.exe ^
  -s c:\openocd\elaphurelink\share\openocd\scripts ^
  -f openocd/elaphurelink.cfg ^
  -f target/stm32f4x.cfg
```

OpenOCD then listens on:
- `localhost:3333` — GDB server
- `localhost:4444` — OpenOCD TCL console
- `localhost:6666` — TCL RPC (for pyOCD/pyOpenOCD)

### mDNS vs. IP address

The config uses `dap.local` (mDNS).  On this machine `dap.local` resolves to
`192.168.137.123`.  If mDNS is unavailable, edit `openocd/elaphurelink.cfg`:

```tcl
# Replace:
cmsis-dap elaphurelink addr dap.local
# With:
cmsis-dap elaphurelink addr 192.168.137.123
```

---

## Path 2 — elaphureLink directly from Python

No OpenOCD needed for simple DAP operations.

The elaphureLink protocol is trivial to implement (12-byte handshake, then raw
CMSIS-DAP packets).  This is verified working:

```python
import socket, struct

ESP32_IP, PORT = "192.168.137.123", 3240

with socket.create_connection((ESP32_IP, PORT), timeout=10) as s:
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    # Handshake
    s.sendall(struct.pack("!III", 0x8a656c70, 0, 0x10000))
    ident, cmd, ver = struct.unpack("!III", s.recv(12))
    # assert ident == 0x8a656c70

    # Send any CMSIS-DAP command (e.g. DAP_Info: 0x00, id: 0xF0 = capabilities)
    s.sendall(bytes([0x00, 0xF0]))
    resp = s.recv(512)
    caps = resp[2]   # capabilities byte
    print(f"SWD: {bool(caps & 0x01)}, JTAG: {bool(caps & 0x02)}")
```

See `tests/read_vtarget_tcp.py` for a complete example using the related USBIP
protocol to read VTarget via the CMSIS-DAP vendor command.

---

## Path 3 — CMSIS-DAP TCP bridge (xPack OpenOCD 0.12, experimental)

The main xPack OpenOCD at `c:\openocd\bin\openocd.exe` (v0.12) supports
`cmsis-dap backend tcp`, which expects a server speaking a framed CMSIS-DAP
packet protocol on port 4441.

The bridge in `openocd/cmsis_dap_tcp_bridge.py` connects elaphureLink to this
backend, but the packet framing for xPack's cmsis-dap-tcp (uses non-blocking
`MSG_PEEK` with a specific 4-byte header) needs to be matched exactly.
**This path is a work-in-progress** — use Path 1 instead.

---

## pyOCD

pyOCD is a Python debugger library that speaks CMSIS-DAP directly.  It normally
discovers USB HID/Bulk CMSIS-DAP adapters.  It does not natively support
elaphureLink or USBIP.

Two options to use pyOCD with this device:

### Option A — pyOCD via OpenOCD GDB stub

```
pyOCD → localhost:3333 (GDB) → OpenOCD (elaphureLink) → device
```

OpenOCD (Path 1) exposes a GDB server.  pyOCD can attach to GDB servers.

### Option B — pyOCD custom elaphureLink probe plugin

pyOCD supports custom `Probe` implementations via its plugin system.  A plugin
that wraps the elaphureLink TCP connection as a CMSIS-DAP probe would allow
pyOCD to talk to this device natively.  Not yet implemented — the Python
elaphureLink client code above is the foundation.

---

## File summary

| File | Description |
| ---- | ----------- |
| `openocd/elaphurelink.cfg` | Interface config for the elaphureLink OpenOCD |
| `openocd/cmsis-dap-tcp.cfg` | Interface config for xPack OpenOCD + bridge (WIP) |
| `openocd/cmsis_dap_tcp_bridge.py` | Python bridge: xPack OpenOCD ↔ elaphureLink device |

---

## Troubleshooting

### "elaphurelink addr — connection refused"

The device's TCP server only accepts one connection at a time.  If a previous
session (USBIP kernel driver or another OpenOCD) is still connected:

```bat
"C:\Program Files\USBip\usbip.exe" detach -p 01
```

Or power-cycle the ESP32.  The firmware closes old connections automatically
when a new one arrives, so retrying once is usually enough.

### "no transport selected"

Normal when running without a `-f target/....cfg`.  Add the target file:

```bat
-f c:\openocd\elaphurelink\share\openocd\scripts\target\stm32f4x.cfg
```

### Slow SWD clock

WiFi round-trip adds latency.  Lower the adapter speed if you see errors:

```tcl
adapter speed 500    # 500 kHz instead of 1000 kHz
```
