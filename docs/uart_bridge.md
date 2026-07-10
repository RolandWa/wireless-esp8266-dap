# UART TCP Bridge — wireless-esp8266-dap

The firmware includes a bidirectional bridge between a TCP socket and a hardware
UART port.  This lets any PC application talk to a serial device wired to the
ESP32 as if it were a direct COM port connection — all over WiFi.

---

## Hardware connections (ESP32-C3 XIAO)

```
Target MCU / serial device
  ↕  GPIO21 (D6/TX)  →  UART RX on target
  ↕  GPIO20 (D7/RX)  ←  UART TX on target
  ↕  GND
ESP32-C3 XIAO (192.168.137.123)
  ↕  WiFi
PC — TCP client on port 1234
```

| Pin | GPIO | XIAO label | Direction |
| --- | ---- | ---------- | --------- |
| ESP TX → target RX | GPIO21 | D6 | OUT |
| ESP RX ← target TX | GPIO20 | D7 | IN  |

For ESP32-S3 XIAO: TX=GPIO43, RX=GPIO44.

---

## Enable in firmware

Edit [main/wifi_configuration.h](../main/wifi_configuration.h) and rebuild:

```c
#define USE_UART_BRIDGE      1       // 0 → 1
#define UART_BRIDGE_PORT     1234    // TCP port (default 1234)
#define UART_BRIDGE_BAUDRATE 115200  // initial baud rate
```

Then rebuild and flash:

```bash
python3 build_WSL.py --build   # in WSL
```

```bat
flash_eps.bat                  # Windows
```

---

## Baud rate negotiation protocol

When the TCP connection is accepted, the firmware reads the **first packet**.
If it is a pure ASCII decimal number between 1 and 2 000 000 (e.g. `"115200"`),
the UART is reconfigured to that baud rate before forwarding begins.

The Python client script handles this automatically via `--baud`.
To skip negotiation, send any non-numeric byte first.

---

## Client options

### Option A — Python script (recommended)

[tests/uart_bridge.py](../tests/uart_bridge.py) — interactive terminal or
scriptable send/receive.

```bash
# Interactive terminal
python tests/uart_bridge.py

# Set baud rate
python tests/uart_bridge.py --baud 9600

# Send command, capture response (1 second window)
python tests/uart_bridge.py --send "AT\r\n" --timeout 1.0

# Log everything received to a file
python tests/uart_bridge.py --log session.txt

# Explicit IP / port
python tests/uart_bridge.py --ip 192.168.137.123 --port 1234
```

Use as a library in other test scripts:

```python
from tests.uart_bridge import connect, send_and_receive

# One-shot
resp = send_and_receive(ip="192.168.137.123", baud=115200,
                        message="version\r\n", timeout=0.5)
print(resp)

# Keep-alive socket
sock = connect(ip="192.168.137.123", baud=115200)
sock.sendall(b"reset\r\n")
sock.close()
```

### Option B — PuTTY

1. Open **PuTTY**.
2. Set **Connection type** → **Raw** (not SSH, not Telnet).
3. **Host Name:** `dap.local` (or `192.168.137.123`)
4. **Port:** `1234`
5. *(Optional)* Go to **Terminal → Local echo → Force on** so you can see what you type.
6. *(Optional)* Go to **Terminal → Local line editing → Force off** so keystrokes are sent immediately, not buffered per line.
7. Click **Open**.
8. **Immediately type the baud rate** (e.g. `115200`) and press **Enter**.
   This is the baud-rate negotiation packet — it must be the very first data sent.
   The UART is reconfigured before any further bytes are forwarded.
9. Communicate normally. Type commands, read responses.

> **Save the session:** Enter a name under **Session → Saved Sessions** (e.g. `DAP-UART`)
> and click **Save**. Next time, just load it and click **Open** — host and port are
> pre-filled. You still need to type the baud rate after connecting.
>
> **Local echo off by default:** PuTTY in Raw mode echoes nothing locally unless you
> enable Force on. If you see doubled characters, switch it back to **Auto**.

### Option C — Netcat / ncat

```bat
ncat dap.local 1234
```

Type `115200` and Enter first to set baud rate, then communicate normally.

### Option D — Any TCP-capable serial terminal

Tools like **ExtraPuTTY**, **TeraTerm** (raw TCP mode), **RealTerm** (Winsock)
all work — connect to `dap.local:1234`, send the baud rate string first.

---

## Use cases

### SWO / ITM trace capture

Wire the target SWO pin to GPIO20 (D7/RX).  Set baud rate to match the
SWO clock configured in your debugger.  The bridge forwards raw SWO bytes
over TCP — feed them into a trace decoder.

### AT command modem / GSM / BLE module

Wire UART TX/RX, open the bridge at the module's baud rate, type AT commands.

### Target MCU console / shell

Wire the target's debug UART.  Use the interactive mode for a live shell session
over WiFi without a USB-serial adapter.

### Automated test scripts

Use `send_and_receive()` to script command/response sequences against the target's
UART interface from a PC test harness.

---

## Limitations

- One TCP client at a time.  A second connection is rejected while one is active.
- Buffer size is 512 bytes per direction.  Burst data larger than this may lose
  bytes at very high baud rates.
- The bridge and the DAP debug interface run concurrently — both can be active
  simultaneously (different TCP ports: DAP on 3240, UART on 1234).

---

## Firmware implementation

| File | Role |
| ---- | ---- |
| `main/uart_bridge.c` | TCP server + UART driver, baud-rate negotiation |
| `main/wifi_configuration.h` | `USE_UART_BRIDGE`, `UART_BRIDGE_PORT`, `UART_BRIDGE_BAUDRATE` |
| `main/main.c` | Starts `uart_bridge_task()` when `USE_UART_BRIDGE=1` |
