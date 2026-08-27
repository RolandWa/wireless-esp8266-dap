# VTarget Sensing and Control — ESP32-C3 / ESP32-S3 XIAO

The firmware can measure the target reference voltage (VTref) and, when the
hardware circuit is complete, set it via PWM.  Both functions are exposed as
CMSIS-DAP vendor commands and the read value is also logged on the serial port
every 5 seconds.

---

## Hardware

### Sensing (Vendor1 — working)

| Signal | GPIO | Notes |
| ------ | ---- | ----- |
| VTref sense | GPIO2 (ADC1_CH2) | Through a 1:2 resistive divider — firmware doubles the reading |
| ADC range | 0 – 3.1 V (11 dB attenuation) | Raw range after divider |
| VTref range | 0 – 6.2 V | After ×2 compensation |

ADC calibration uses `esp_adc_cal_characterize` (eFuse TP or Vref).
20 samples are averaged per reading; 0.5 ms delay between samples.

### Control (Vendor2 — calibrated operating range)

The circuit topology in `main/vtarget_pwm.c`:

| Component | Value | Role |
| --------- | ----- | ---- |
| GPIO3 | PWM output | Controls MOSFET gate |
| R4 | 100 Ω | Gate series resistor |
| R5 | 43 kΩ | Gate pull-down |
| C2 | 10 µF, 25 V | PWM filter |
| Q1 | YJL2304A | N-channel MOSFET in AP1117-ADJ feedback |
| U2 | AP1117-ADJ | Adjustable LDO regulator |
| R6, R7 | 100 kΩ each | Feedback voltage divider |
| C3 | 10 µF | Output capacitor |

PWM: 1 kHz, 10-bit resolution (0–1023). DMM characterization found the usable,
monotonic operating window to be PWM counts 358–982. The firmware maps its
supported request range, 1324–4204 mV, into this window.

The DMM measured 1.3249 V at the low endpoint and 4.2047 V at the high endpoint.
The endpoint calibration is valid, but the Q1/AP1117 feedback response remains
nonlinear between endpoints. Use a lookup table rather than assuming that every
intermediate request is accurate to within 5%.

At boot: `vtarget_pwm_init()` is called and the default is set to 3300 mV.

---

## CMSIS-DAP vendor commands

### Vendor1 (0x81) — Read VTarget

| Field | Detail |
| ----- | ------ |
| Command ID | `0x81` (`ID_DAP_Vendor1`) |
| Request | `[0x81]` + zero padding to `DAP_PACKET_SIZE` (512 bytes) |
| Response | `[0x81, voltage_low, voltage_high]` |
| Encoding | `voltage_mv = response[1] \| (response[2] << 8)` — little-endian mV |
| Error | `0xFFFF` (65535) if ADC is not initialised |

### Vendor2 (0x82) — Set VTarget

| Field | Detail |
| ----- | ------ |
| Command ID | `0x82` (`ID_DAP_Vendor2`) |
| Request | `[0x82, voltage_low, voltage_high]` + zero padding |
| Encoding | `voltage_mv` little-endian, valid range 1324–4204 mV |
| Response | `[0x82, status]` |
| Status 0x00 | OK — PWM duty updated |
| Status 0x01 | Invalid range (outside 1324–4204 mV) |
| Status 0xFF | Not supported on this target (non-C3/S3 build) |

### Serial debug commands (115200 baud, COM12)

Commands are line-based — type the command and press **Enter**.

| Command | Action |
| ------- | ------ |
| `v` | Read VTref voltage once |
| `s` | Print status: IP, RSSI, VTref, free heap |
| `h` / `?` | Print help |
| `reboot` | Reboot the device (full word required - prevents accidental trigger from stale bytes) |

### C API (internal)

```c
// components/DAP/source/DAP_vendor.c
uint16_t vtarget_read_mv_public(void);        // returns mV, 0xFFFF on error
void     vtarget_log_boot_reading(void);      // called once at startup

// main/vtarget_pwm.h
esp_err_t vtarget_pwm_init(void);             // call once at boot (main.c does this)
esp_err_t vtarget_set_voltage(uint16_t mV);  // 1324-4204 mV
esp_err_t vtarget_set_duty_raw(uint16_t d);  // 0-1023, for calibration
uint16_t  vtarget_get_duty_raw(void);
```

---

## Testing from Python (Windows)

### Correct method — USBIP over TCP (`tests/read_vtarget_tcp.py`)

```bat
# Read VTarget
python tests/read_vtarget_tcp.py [--ip <esp32-ip>]

# Set VTarget then read back
python tests/read_vtarget_tcp.py --set 3300
python tests/read_vtarget_tcp.py --set 1800
```

No extra dependencies (only Python standard library).  Default IP: `192.168.137.123`.

Expected output (read):

```text
Connecting to 192.168.137.123:3240 ...
  Attached (version=0x0111, status=OK)

Sending DAP_Vendor1 (0x81): read VTarget ...
  Received 3 bytes: ['0x81', '0x60', '0x14']

=== VTarget = 5216 mV  (5.216 V) ===
```

Expected output (set + read):

```text
Connecting to 192.168.137.123:3240 ...
  Attached (version=0x0111, status=OK)

Sending DAP_Vendor2 (0x82): set VTarget = 3300 mV ...
  Status: 0x00 = OK

Sending DAP_Vendor1 (0x81): read VTarget ...
  Received 3 bytes: ['0x81', '0xe8', '0x0f']

=== VTarget = 4072 mV  (4.072 V) ===
```

The command response confirms that the PWM control update succeeded. Verify the
actual output with Vendor1 or the DMM curve test, because intermediate voltage
accuracy is limited by the nonlinear feedback response.

## References

- [ESP-IDF v4.4.2 LEDC API reference](https://docs.espressif.com/projects/esp-idf/en/v4.4.2/esp32/api-reference/peripherals/ledc.html)
- [AP1117 adjustable regulator datasheet](https://www.diodes.com/assets/Datasheets/AP1117.pdf)

### Why not pyusb / the Windows USBIP kernel driver?

Using `pyusb` (`dev.write()` / `dev.read()`) through the Windows USBIP kernel
driver appears to work but silently returns wrong data:

| Layer | Behaviour |
| ----- | --------- |
| OUT (write) | Forwarded correctly — firmware logs `[DAP] enqueue cmd=0x81` |
| IN (read) | **NOT forwarded** — driver returns its own enumeration cache |
| First reads | Return UTF-16-LE string descriptor bytes (residue from enumeration) |
| Later reads | Return 65 bytes of zeros |
| Firmware | Never sees `[URB] EP1 IN]` — processes commands but can't deliver responses |

**Root cause:** The Windows USBIP kernel driver does not submit Bulk-IN URBs over
the TCP connection to the device.

`read_vtarget_tcp.py` speaks the USBIP stage-2 wire protocol directly, bypassing
the kernel driver completely.

---

## How `read_vtarget_tcp.py` works

The USBIP protocol has two stages:

### Stage 1 — attach

```text
Client → Server: OP_REQ_IMPORT (version=0x0111, code=0x8003, busid="1-1")
Server → Client: OP_REP_IMPORT (status=0) + usbip_usb_device (312 bytes)
```

After attach the connection is in stage-2 URB mode.

### Stage 2 — URBs

Each URB submit is a 48-byte header followed by the data payload (for OUT):

```text
cmd=0x00000001  seqnum  devid  direction  ep  flags  buf_len
start_frame  npackets=0xFFFFFFFF  interval  setup[8]
[data bytes for OUT]
```

The firmware responds with a 48-byte header plus payload (for IN):

```text
cmd=0x00000003  seqnum  devid  direction  ep  status  actual_length
start_frame  npackets  error_count  setup[8]
[data bytes for IN, actual_length bytes]
```

Each DAP exchange = one OUT URB (command) + one IN URB (response).

---

## Debugging tips

### Monitor firmware serial while testing

```python
# pyserial — run alongside the test script
import serial
s = serial.Serial("COM12", 115200, timeout=0.2)
while True:
    line = s.readline()
    if line:
        print(line.decode(errors="replace").rstrip())
```

Look for:

```text
[DAP] enqueue cmd=0x81 [81 00 00 00]          ← Vendor1 received
[DAP] processed cmd=0x81 resp_len=3 resp=[81 60 14]  ← 0x1460 = 5216 mV

[DAP] enqueue cmd=0x82 [82 e4 0c 00]          ← Vendor2 received (3300 mV)
[DAP] processed cmd=0x82 resp_len=2 resp=[82 00 00]  ← status OK
I (xxx) vtarget_pwm: VTarget set to 3300 mV (duty cycle: 511 / 1023)
```

### `0xFFFF` response (65535 mV)

ADC not initialised — check `CONFIG_IDF_TARGET_ESP32C3`/`ESP32S3` in `sdkconfig`.

### VTarget reads as 0

GPIO2 is floating or target board not connected/powered.

### USBIP kernel driver attached — force detach before TCP test

```bat
"C:\Program Files\USBip\usbip.exe" detach -p 01
```

The firmware accepts one TCP connection at a time; an active kernel-driver
session will prevent the TCP script from connecting.  The firmware also closes
the old connection automatically when a new one arrives.

---

## Firmware implementation files

| File | Role |
| ---- | ---- |
| `components/DAP/source/DAP_vendor.c` | ADC init, `vtarget_read_mv()`, Vendor1 + Vendor2 handlers |
| `main/vtarget_pwm.c` | `vtarget_set_voltage()` — PWM control via LEDC (ESP32-C3/S3 only) |
| `main/vtarget_pwm.h` | Public API + convenience macros (`VTARGET_SET_3V3()` etc.) |
| `main/DAP_handle.c` | DAP thread, ringbuf, `fast_reply()` — routes processed commands back to host |
| `main/usbip_server.c` | TCP USBIP server — demultiplexes URBs to EP handlers |
| `tests/read_vtarget_tcp.py` | Standalone Python test — direct USBIP/TCP, Vendor1 + Vendor2 |
