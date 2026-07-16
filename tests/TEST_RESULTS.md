# Wireless ESP32-C3 DAP — Test Results

**Board:** XIAO ESP32-C3 wireless DAP  
**Firmware:** `wireless_esp_dap` v1 — compiled 2026-07-12, IDF v4.4.2  
**Binary:** `wireless_esp_dap_full.bin` — 781,776 bytes (763.5 kB)  
**Device IP:** `192.168.137.123` (static)  
**USB IDs:** VID `0xC251` / PID `0xF00A` — `Wireless ESP CMSIS-DAP`  
**Test date:** 2026-07-13

---

## 1. Power-on & Boot

| Check | Result |
|---|---|
| Firmware flashed via `flash_eps.bat` (COM12, 460800 baud) | ✅ PASS |
| Hash verified by esptool after write | ✅ PASS |
| Board boots, WiFi connects, static IP assigned | ✅ PASS |
| Device reachable at `192.168.137.123` (ping) | ✅ PASS |

---

## 2. VTarget Voltage Read

**Script:** `tests/read_vtarget_tcp.py`  
**Connection:** TCP port 3240 (elaphureLink / USBIP stage-1)  
**Target connected:** MAX32672

| Reading | Expected | Actual | Result |
|---|---|---|---|
| VTarget voltage | 3.3 V | **3.296 V** | ✅ PASS |

---

## 3. UART TCP Bridge

**Script:** `tests/uart_bridge.py --loopback`  
**Wiring:** GPIO20 (D7/RX) shorted to GPIO21 (D6/TX)  
**TCP port:** 1234

### 3.1 Single baud rate test (115200)

| Test | Result |
|---|---|
| `DAP-UART-loopback-test!` echo | ✅ PASS |
| `0123456789` echo | ✅ PASS |
| Binary pattern `0xAA 0x55` echo | ✅ PASS |

### 3.2 All supported baud rates

| Baud rate | Tests | Result |
|---|---|---|
| 9600 | 3/3 | ✅ PASS |
| 14400 | 3/3 | ✅ PASS |
| 19200 | 3/3 | ✅ PASS |
| 28800 | 3/3 | ✅ PASS |
| 38400 | 3/3 | ✅ PASS |
| 56000 | 3/3 | ✅ PASS |
| 57600 | 3/3 | ✅ PASS |
| 115200 | 3/3 | ✅ PASS |

**Total: 24/24 passed**

> **Note:** Running `--all-bauds` without a device reboot between runs causes the UART to remain at the last switched baud rate. Always reboot the board before re-running `--all-bauds`.

---

## 4. SWD / Programming Mode — MAX32672

**Tool:** `C:\openocd\elaphurelink\bin\openocd.exe` (v0.12.0+dev-01812)  
**Config:** `openocd/elaphurelink.cfg` + `openocd/target_max32672.cfg`  
**Connection:** elaphureLink TCP port 3240

| Check | Expected | Actual | Result |
|---|---|---|---|
| elaphureLink TCP connect | Connected | Connected | ✅ PASS |
| SWD DPIDR | `0x2ba01477` | `0x2ba01477` | ✅ PASS |
| Core detected | Cortex-M4 | Cortex-M4 r0p1 | ✅ PASS |
| Designer ID | Maxim Integrated | Maxim Integrated (`0x0cb`) | ✅ PASS |
| Breakpoints available | ≥4 | 6 | ✅ PASS |
| Watchpoints available | ≥2 | 4 | ✅ PASS |
| Flash bank recognized | max32xxx driver | Recognized (warning: no free_driver_priv) | ✅ PASS |

**Config fix applied:** `swd newdap` requires `-irmask 0xf` in addition to `-irlen 4` — corrected in `target_max32672.cfg` and `flash_max32672.bat`.

---

## 5. Build System

| Check | Result |
|---|---|
| `build.bat` launches WSL build from Windows | ✅ PASS |
| `build_WSL.py --build` completes in WSL | ✅ PASS |
| Merged binary copied back to Windows repo | ✅ PASS |

---

## 6. MAX32672 SRAM Firmware Load & Verify

**Tool:** `C:\openocd\elaphurelink\bin\openocd.exe`  
**Firmware:** `mcucommander_800T.hex` (from `mcucommander` project)  
**Load address:** `0x20000000` (SRAM) — RAM-resident image, entry at `0x20002709`  
**Method:** `write_memory` in 1 kB chunks (bypasses work-area conflict at `0x20000000`)

| Step | Result |
|---|---|
| SWD connect + reset halt | ✅ PASS |
| Write 72,928 bytes to SRAM via `write_memory` | ✅ PASS — 71.2 kB |
| Readback (`dump_image 0x20000000`) | ✅ PASS |
| Binary compare: original vs readback | ✅ **PASS — 0 differences** |
| Set PC to `0x20002709` + resume | ✅ PASS — firmware running |

> **Note:** `load_image` reports success but does not write correctly when the OpenOCD work-area is configured at the same address as the load target (`0x20000000`). Use `write_memory` chunks instead.

---

## 7. VTarget PWM Output Test

**Script:** `tests/test_vtarget_pwm.py`  
**Wiring:** VTref (GPIO2) shorted to VTarget output  
**Sweep:** 1250, 1800, 2500, 3000, 3300, 3600, 4096, 5000 mV  
**Pass criterion:** ±5% vs set-point

| Set (mV) | Actual (mV) | Error (mV) | Error (%) | Result |
|---|---|---|---|---|
| 1250 | 4239 | +2989 | +239% | ❌ FAIL |
| 1800 | 4238 | +2438 | +135% | ❌ FAIL |
| 2500 | 4239 | +1739 | +70% | ❌ FAIL |
| 3000 | 4238 | +1238 | +41% | ❌ FAIL |
| 3300 | 4239 | +939 | +28% | ❌ FAIL |
| 3600 | 4239 | +639 | +18% | ❌ FAIL |
| 4096 | 4238 | +142 | +3.5% | ✅ PASS |
| 5000 | 4238 | −762 | −15% | ❌ FAIL |

**Root cause: wrong AP1117 variant assembled.**

- Assembled: **AP1117-5** (fixed 5 V output, no ADJ pin)
- Required: **AP1117-ADJ** (adjustable 1.25–5 V via feedback divider)

The AP1117-5 has no ADJ pin, so the PWM-controlled MOSFET in the feedback network has no effect — output voltage is fixed regardless of duty cycle.  
Additionally, the AP1117-5 needs ≥ 6.3 V input to regulate to 5 V; running from USB 5 V it operates in **dropout** and outputs ≈ 4.2 V (`Vin − Vdropout ≈ 5.0 − 0.8 V`), which matches the constant 4238 mV ADC reading.

**Available alternative: AP1117-3.3** — fixed 3.3 V output, no PWM control, suitable only for 3.3 V targets. Voltage control requires the AP1117-ADJ.

---

## 8. VTarget PWM Waveform Characterization

**Script:** `tests/sweep_pwm_vb.py`  
**Instrument:** NI VB-8034 oscilloscope, channel `mso/1`, 1:10 probe on GPIO3 (A1)  
**Sweep:** 1%, 5%, 10%, 15%, …, 100% duty in 5% steps  
**Test date:** 2026-07-16

### 8.1 Results Table

| Target % | Set (mV) | Duty cnt | Meas % | Freq (Hz) | Vmax (V) | Vmin (V) | pp (V) | Error |
|---|---|---|---|---|---|---|---|---|
| 1 | 4963 | 10 | 1.0 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.0% |
| 5 | 4813 | 51 | 5.0 | 1000.1 | 3.416 | −0.041 | 3.457 | −0.0% |
| 10 | 4626 | 102 | 10.0 | 1000.1 | 3.333 | −0.082 | 3.416 | −0.0% |
| 15 | 4439 | 153 | 14.9 | 1000.1 | 3.374 | −0.123 | 3.498 | −0.1% |
| 20 | 4249 | 205 | 19.9 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.1% |
| 25 | 4062 | 256 | 24.9 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.1% |
| 30 | 3875 | 307 | 29.9 | 1000.1 | 3.621 | −0.041 | 3.663 | −0.1% |
| 35 | 3688 | 358 | 34.9 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.1% |
| 40 | 3501 | 409 | 39.8 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.2% |
| 45 | 3314 | 460 | 44.8 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.2% |
| 50 | 3123 | 512 | 50.0 | 1000.1 | 3.374 | −0.041 | 3.416 | +0.0% |
| 55 | 2936 | 563 | 55.0 | 1000.1 | 3.416 | −0.082 | 3.498 | −0.0% |
| 60 | 2749 | 614 | 60.0 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.0% |
| 65 | 2562 | 665 | 64.9 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.1% |
| 70 | 2375 | 716 | 69.9 | 1000.1 | 3.374 | −0.041 | 3.416 | −0.1% |
| 75 | 2188 | 767 | 74.9 | 1000.1 | 3.374 | 0.000 | 3.374 | −0.1% |
| 80 | 2001 | 818 | 79.9 | 1000.1 | 3.374 | −0.082 | 3.457 | −0.1% |
| 85 | 1811 | 870 | 84.9 | 1000.1 | 3.374 | 0.000 | 3.374 | −0.1% |
| 90 | 1624 | 921 | 89.8 | 1000.1 | 3.374 | 0.000 | 3.374 | −0.2% |
| 95 | 1437 | 972 | 94.8 | 1000.1 | 3.416 | 0.000 | 3.416 | −0.2% |
| 100 | 1250 | 1023 | 99.9 | 1000.1 | 3.416 | 0.000 | 3.416 | −0.1% |

### 8.2 Summary

| Parameter | Result | Spec | Status |
| --- | --- | --- | --- |
| Frequency | **1000.1 Hz** | 1000 Hz | ✅ PASS |
| Duty accuracy | **±0.2% max** across 1–100% | — | ✅ PASS |
| Signal amplitude (Vmax) | **3.33–3.62 V** | 3.3 V GPIO | ✅ PASS |
| Signal low (Vmin) | **−0.12–0.00 V** | 0 V | ✅ PASS |

**LEDC PWM peripheral confirmed functional.** Duty cycle linearity is excellent across the full range with sub-0.2% error. Signal amplitude matches 3.3 V GPIO logic level throughout.

> **Hardware note:** The PWM output on GPIO3 is correct. The VTarget voltage control does not respond because the assembled AP1117-5 (fixed 5 V, no ADJ pin) cannot be adjusted via the feedback network. Replacing with AP1117-ADJ will enable full VTarget control.

---

## TODO

- [x] **UART pins high-Z by default — activate only on TCP client connect** — implemented in `uart_bridge.c`: `uart_pins_highz()` called at task start (boot state); `uart_enable()` called on TCP `accept()` (installs driver, activates pins); `uart_disable()` called on TCP disconnect and WiFi disconnect (deletes driver, returns pins to `GPIO_MODE_INPUT`). Safe to connect to targets that hard-wire programmer TX to GND.

- [ ] **Implement CMSIS-DAP v2.1 UART commands in `DAP_handle.c`** — the firmware already advertises `UART via USB COM port supported` in `DAP_Info` capabilities but handles none of the standard UART commands. Implement the full set so any v2.1-compliant host tool can control the UART without a separate TCP connection:

  | Command | Code | Behaviour to implement |
  |---|---|---|
  | `DAP_UART_Transport` | `0x1F` | `0`=disable (pins → high-Z), `1`=USB CDC, `2`=USB Bulk (TCP bridge maps here) |
  | `DAP_UART_Configure` | `0x20` | Set baud rate, data bits, parity, stop bits |
  | `DAP_UART_Status` | `0x21` | Return TX/RX error and overflow flags |
  | `DAP_UART_Control` | `0x22` | Enable/disable TX and RX independently via bit flags |
  | `DAP_UART_Transfer` | `0x23` | Bulk UART data transfer |

  `DAP_UART_Transport(0)` must tri-state the pins (same as TCP-disconnect path above). `DAP_UART_Transport(2)` enables the TCP bridge path.
- [ ] **Flash a real MAX32672 binary** — test `flash_max32672.bat firmware.bin` end-to-end (erase + program + verify + reset); no flash binary currently available
- [ ] **COM port loopback (USB Serial)** — test COM11 (FTDI) UART loopback on MAX32672 side; requires UART loopback firmware on MAX32672 or external wiring
- [ ] **UART bridge baud-rate persistence fix** — after `--all-bauds` run, UART stays at last switched rate until reboot; firmware should reset baud to default on TCP disconnect
- [ ] **SWO trace** — `handle_swo_trace_response` currently stubbed out; implement and test SWO capture via USB/TCP
- [ ] **Flash verify after program** — confirm `verify` step in `flash_max32672.bat` passes on a real write

---

## Completed Tests

- [x] **Stress test UART bridge** — 10 min at 115200: 5,707 pkts / 182,624 bytes / 0 errors / 0 reconnects ✅ PASS
- [x] **pyOCD MAX32672 pack** — pack installed; DPIDR `0x2ba01477`, Cortex-M4 r0p1 detected, FPU confirmed ✅ PASS
- [x] **OpenOCD GDB debug session** — halt, `reg pc` (`0x20001bd0`), `step` (PC→`0x200023e8`), `mdw`, `resume`, `halt` all verified ✅ PASS
- [x] **TCP keepalive on VTarget** — 5 consecutive reads stable at **3.306 V**, 0 failures ✅ PASS
- [x] **WiFi AP fallback test** — AP turned off and back on; board reconnected to `192.168.137.123` within retry window (5 retries × STA list before AP fallback to SSID `DAP` / `192.168.4.1`) ✅ PASS (STA reconnect verified; AP fallback SSID=`DAP` confirmed in `wifi_handle.c:248`)
