# VTarget Programmable Voltage Control - Implementation Summary

> **Status (2026-11-25):** component values below are taken from the KiCad
> schematic and are fitted on all PCBs (AP1117-ADJ everywhere). The original
> fabrication BOM (R1=12k, R3=27k, R4=39k, R5=10k, C2=10nF) left Q1 permanently
> off and was reworked; see
> [VTARGET_REWORK_INSTRUCTIONS.txt](VTARGET_REWORK_INSTRUCTIONS.txt) and
> [VTARGET_BATCH_ANALYSIS.md](VTARGET_BATCH_ANALYSIS.md). The firmware-calibrated
> output range is **1.326 V – 4.200 V**, not the theoretical 1.25 V – 5 V.

## Hardware Configuration

### Capacitors
✅ **C3**: 10µF (0805) - VTarget output capacitor on AP1117-ADJ
- Location: (153.67, 147.32)
- Purpose: Energy storage for VTarget output, provides stable output voltage
- Recommended minimum: 10µF for AP1117 stability

✅ **C2**: 10µF / 25V - PWM filter capacitor on the Q1 gate
- Purpose: Turns the 1 kHz PWM into a DC gate level for Q1
- Filter time constant: τ = (R4‖R5) × C2 ≈ 14.6kΩ × 10µF ≈ 145 ms
  (R4 × C2 = 22kΩ × 10µF = 220 ms when unloaded)
- The 0603 footprint is too small for a 10µF/25V part in many cases; check how
  it was fitted on each board (e.g. larger package with flying leads).

✅ **C1**: 10nF (0603) - Reference divider smoothing
- Purpose: Additional filtering for voltage reference

### Circuit Components
- **U2 (AP1117-ADJ)**: Adjustable LDO regulator at (119.38, 128.27)
  - Input: 5V supply
  - Output: VTarget (calibrated 1.326V to 4.200V)
  - Max current: 1A

- **Q1 (YJL2304A)**: N-channel MOSFET at (116.84, 170.18)
  - Package: SOT-23
  - Max current: 1.4A
  - Max voltage: 30V
  - Typical R_DS(on): ~55mΩ @ V_GS=4.5V

- **Resistors:**
  - R1: 1.2kΩ, R3: 2.7kΩ (AP1117-ADJ feedback divider, Q1 modulates it)
  - R4: 22kΩ (PWM gate series resistor)
  - R5: 43kΩ (MOSFET gate pull-down)
  - R6, R7: 100kΩ each (VTref sense divider to GPIO2)

- **Gate drive:** V_GS(max) = 3.3V × R5 / (R4 + R5) = 3.3V × 43k / 65k ≈ 2.18V

## PWM Implementation

### Configuration
- **Frequency**: 1 kHz (1000 Hz)
- **Resolution**: 10-bit (1024 steps: 0-1023)
- **GPIO**: GPIO3 on ESP32-C3
- **Timer**: LEDC_TIMER_0
- **Channel**: LEDC_CHANNEL_0

### PWM Characteristics
```
Frequency: 1 kHz
Period: 1 ms
Resolution: ~0.98 µs per step (1023 steps)
```

### Filter Design
```
RC Filter: R4 (22k) in series, C2 (10µF) on the gate, R5 (43k) pull-down as load
Time constant τ = (R4‖R5) × C2 ≈ 14.6kΩ × 10µF ≈ 145 ms   (R4 × C2 = 220 ms unloaded)
Cutoff frequency fc = 1/(2πτ) ≈ 1.1 Hz   (0.72 Hz unloaded)
```

At 1 kHz PWM:
- ~900× above cutoff → PWM ripple on the gate is negligible; Q1 sees a DC level
- Slow response: ~3τ ≈ 0.45 s to 95 %, ~5τ ≈ 0.7 s to 99 % settling
- Wait ≥ 0.5 s (≥ 1 s for best accuracy) after a setpoint change before reading VTarget

## Voltage Control Algorithm

### Inverse Relationship
```c
// Higher voltage → Lower PWM duty (Q1 more OFF)
// Lower voltage → Higher PWM duty (Q1 more ON)
```

The response is **nonlinear**, so the firmware does not use a straight-line
duty formula. `vtarget_set_voltage()` interpolates piecewise-linearly through a
25-point DMM-measured table (`VTARGET_CAL_TABLE` in
[main/vtarget_pwm.c](../../main/vtarget_pwm.c)), which is the median response of
the PCB-04/08/09/10 cluster (see [VTARGET_BATCH_ANALYSIS.md](VTARGET_BATCH_ANALYSIS.md)).

### Voltage Range
- **Maximum**: 4.200V (PWM count 358, Q1 least on)
- **Minimum**: 1.326V (PWM count 982, Q1 most on)
- Requests outside 1326–4200 mV are rejected (`ESP_ERR_INVALID_ARG` / vendor status 0x01)
- The AP1117-ADJ cannot reach 5 V from the USB-fed ~4.3–4.4 V input (dropout), and
  the 1.25 V reference limit is not reached with the current R1/R3/Q1 network.

### AP1117-ADJ Formula
```
V_out = 1.25V × (1 + R3 / R1)      (+ adjust-pin current term)

With Q1 open (no gate drive):   1.25V × (1 + 2.7k / 1.2k) = 4.06V nominal
With Q1 conducting, its R_DS(on) loads the feedback node and lowers V_out.
```
Measured maximum output is ≈ 4.2 V (limited by regulator tolerance and input
headroom); measured minimum ≈ 1.32 V.

## API Usage

### Initialization
```c
#include "main/vtarget_pwm.h"

// Initialize PWM (done automatically in app_main)
esp_err_t ret = vtarget_pwm_init();
```

### Setting Voltage
```c
// Set target voltage to 3.3V
esp_err_t ret = vtarget_set_voltage(3300);  // millivolts

// Valid range: 1326 mV to 4200 mV (calibrated)
vtarget_set_voltage(1326);  // Minimum voltage
vtarget_set_voltage(4200);  // Maximum voltage
vtarget_set_voltage(3300);  // Common 3.3V
```

### Reading Voltage
```c
#include "components/DAP/source/DAP_vendor.c"  // For vtarget_read_mv()

// Read actual VTarget via ADC (requires GPIO2 connected)
uint16_t voltage_mv = vtarget_read_mv();  // Returns averaged reading
printf("VTarget: %u mV\n", voltage_mv);
```

### Raw Duty Cycle Control
```c
// For calibration/testing: set raw PWM duty
vtarget_set_duty_raw(358);   // → ~4.2V output (top of calibrated range)
vtarget_set_duty_raw(763);   // → ~2.9V output
vtarget_set_duty_raw(982);   // → ~1.33V output (bottom of calibrated range)

// Get current duty
uint16_t duty = vtarget_get_duty_raw();
```

## DAP Vendor Commands

### Command 0x81: Read VTarget Voltage
Read the target voltage via ADC (GPIO2 sensing).

**Request:**
```
Byte 0: 0x81 (Command ID)
```

**Response:**
```
Byte 0: 0x81 (Command ID echo)
Byte 1: Voltage low byte (mV)
Byte 2: Voltage high byte (mV)
```

**Example:**
- Reading 3300 mV (3.3V):
  - Response: `0x81 0xE4 0x0C` (3300 = 0x0CE4)
- Reading 1800 mV (1.8V):
  - Response: `0x81 0x08 0x07` (1800 = 0x0708)

### Command 0x82: Set VTarget Voltage
Set the target voltage output (calibrated range 1326-4200 mV).

**Request:**
```
Byte 0: 0x82 (Command ID)
Byte 1: Voltage low byte (mV)
Byte 2: Voltage high byte (mV)
```

**Response:**
```
Byte 0: 0x82 (Command ID echo)
Byte 1: Status
  - 0x00 = Success
  - 0x01 = Invalid voltage range (not 1326-4200 mV)
  - 0xFF = Not supported / other error
```

**Examples:**

Set 3.3V (3300 mV):
```
Request:  0x82 0xE4 0x0C
Response: 0x82 0x00  (success)
```

Set 1.8V (1800 mV):
```
Request:  0x82 0x08 0x07
Response: 0x82 0x00  (success)
```

Set 4.2V (4200 mV, top of calibrated range):
```
Request:  0x82 0x68 0x10
Response: 0x82 0x00  (success)
```

Set 5.0V (5000 mV) — above the calibrated range:
```
Request:  0x82 0x88 0x13
Response: 0x82 0x01  (out of range)
```

**Platform Support:**
- **ESP32-C3**: Full support (sensing + control)
- **ESP32/ESP32-S3**: Sensing only (command 0x81)
- **ESP8266**: Returns 0x00 0x00 for command 0x81, 0xFF for command 0x82

### Using Commands from Python/PyOCD
```python
import pyocd

# Connect to probe
probe = pyocd.probe.aggregator.DebugProbeAggregator.get_all_connected_probes()[0]
probe.open()

# Read VTarget voltage
response = probe.vendor_command(0x81, [])
voltage_mv = response[0] | (response[1] << 8)
print(f"VTarget: {voltage_mv} mV")

# Set VTarget to 3.3V
voltage_mv = 3300
low_byte = voltage_mv & 0xFF
high_byte = (voltage_mv >> 8) & 0xFF
response = probe.vendor_command(0x82, [low_byte, high_byte])
if response[0] == 0x00:
    print("Voltage set successfully")
elif response[0] == 0x01:
    print("Invalid voltage range")
else:
    print("Command failed")
```

## Example Workflow
```c
// Set specific voltage (1326-4200 mV)
vtarget_set_voltage(3300);  // 3.3V
vtarget_set_voltage(1800);  // 1.8V
vtarget_set_voltage(4200);  // 4.2V (maximum)

// Or use convenience macros
VTARGET_SET_3V3();
VTARGET_SET_1V8();
VTARGET_SET_4V2();
```

### Raw Control (for calibration)
```c
// Set raw duty cycle (0-1023)
vtarget_set_duty_raw(512);  // ~50% duty

// Get current duty
uint16_t duty = vtarget_get_duty_raw();

// Disable PWM
vtarget_pwm_disable();
```

## Files Added

1. **main/vtarget_pwm.c** - PWM control implementation
2. **main/vtarget_pwm.h** - Public API header
3. **main/CMakeLists.txt** - Updated to include vtarget_pwm.c
4. **main/main.c** - Auto-initialization added for ESP32-C3

## Default Configuration

The system initializes with:
- PWM enabled at startup (ESP32-C3 only)
- Default voltage: **3.3V** (most common target voltage)
- Can be changed at runtime via API

## Calibration Notes

The duty-to-voltage response of the Q1/AP1117-ADJ network is **nonlinear**, so the
firmware uses a measured 25-point table (`VTARGET_CAL_TABLE`) instead of a formula.
The table is the median of the PCB-04/08/09/10 cluster; other boards may deviate
by more than ±5 % (see [VTARGET_BATCH_ANALYSIS.md](VTARGET_BATCH_ANALYSIS.md)).

### Factors Affecting Accuracy:
1. **Settling time** (τ ≈ 145 ms): measure only after ≥ 0.5–1 s, otherwise the
   curve depends on the previous setpoint
2. **MOSFET V_th / R_DS(on) variation** (temperature, V_GS dependent; V_GS(max) ≈ 2.18 V)
3. **Resistor tolerances** (R1, R3, R4, R5; 0603 parts, 1–5 %)
4. **C2 physical part** (10µF/25V tolerance and DC bias derating)
5. **Load current** (AP1117 dropout voltage)
6. **VTref jumper**: must be fitted for ADC readback, otherwise it reads ≈ 0 mV

### Calibration Procedure:
Run `tests/pwm_vtarget_dmm.py --board-id PCB-XX` with a DMM on VTarget; it writes
`tests/test_results/vtarget_PCB-XX_measurements.csv` (duty ↔ DMM voltage). Rebuild
`VTARGET_CAL_TABLE` from that data (and keep the `FW_CAL_TABLE` mirrors in
`tests/pwm_vtarget_dmm.py` and `tests/test_vtarget_pwm.py` in sync).

### Calibration Points (current table range):
- 1.326V (min, PWM 982)
- 1.8V
- 3.0V
- 3.3V (default at boot)
- 4.2V (max, PWM 358)

## Expected Performance

### Settling Time
- Gate RC time constant: τ ≈ 145 ms
- 95% settling: ~3τ ≈ 0.45 s
- 99% settling: ~5τ ≈ 0.7 s (use ≥ 1 s per step in tests)

### Ripple Voltage
- The 1 kHz PWM is attenuated ~900× by the gate filter (fc ≈ 1 Hz); VTarget ripple
  is limited by the AP1117-ADJ loop and C3 (10µF), not by the PWM.

### Accuracy
- Measured on the cluster boards with the shared table: mean 0.5 %, worst 1.9 %
  against the requested voltage (see VTARGET_BATCH_ANALYSIS.md)
- Other boards need a per-board table for ±5 %

## Safety Features

1. **Default to safe voltage**: Initializes to 3.3V
2. **Range checking**: Rejects voltages outside 1.326-4.200V
3. **Pull-down resistor**: R5 ensures MOSFET OFF if GPIO fails
4. **Overcurrent protection**: AP1117 has built-in current limiting

## Monitoring

Combine with existing VTarget sensing (GPIO2):
```c
extern uint32_t vtarget_read_mv(void);  // From DAP_vendor.c

// Set voltage
vtarget_set_voltage(3300);
vTaskDelay(pdMS_TO_TICKS(1000));  // Wait for settling (gate filter tau ~145 ms)

// Verify actual output
uint32_t actual_mv = vtarget_read_mv();
printf("Target: 3300 mV, Actual: %lu mV\n", actual_mv);
```

## Power Considerations

### Current Budget
- AP1117-ADJ quiescent: ~5 mA
- MOSFET gate: ~0 µA (DC, capacitive charging only)
- Gate network R4 + R5: up to 3.3V / (22k + 43k) ≈ 51 µA at 100 % duty
- Total control circuit: ~5 mA (dominated by AP1117-ADJ quiescent current)

### Heat Dissipation
```
P_dissipation = (V_in - V_out) × I_load
V_in ≈ 4.3–4.4V (USB 5V after the XIAO Schottky diode)

Example at 3.3V, 100 mA load:
P = (4.4V - 3.3V) × 0.1A = 110 mW (acceptable)

Worst case at 1.33V, 1A load:
P = (4.4V - 1.33V) × 1A ≈ 3.1W (requires heatsinking!)
```

**Recommendation**: Keep load current <500 mA for reliable operation without heatsinking.

## Testing Checklist

- [ ] Verify C3 (10µF) installed on VTarget output
- [ ] Verify C2 (10µF/25V) fitted at the Q1 gate and R4 = 22k, R5 = 43k, R1 = 1.2k, R3 = 2.7k
- [ ] Verify the VTref jumper is fitted
- [ ] Test voltage sweep: 1.326V → 4.2V (≥ 1 s per step)
- [ ] Measure ripple voltage with oscilloscope
- [ ] Verify ADC readback matches set voltage
- [ ] Test load regulation (no load → 100 mA)
- [ ] Test line regulation (4.5V → 5.5V input)
- [ ] Measure settling time with scope
- [ ] Verify thermal performance at high current
- [ ] Check PWM frequency with scope (should be 1 kHz)

## Debug Connector Integration

### 10-Pin Cortex Debug Connectors (J1/J3)
**NON-STANDARD Pinout:**
```
Pin 1: VTref        Pin 2: TMS/SWDIO
Pin 3: GND          Pin 4: TCK/SWCLK
Pin 5: UART_TX      Pin 6: TDO/SWO
Pin 7: UART_RX      Pin 8: TDI
Pin 9: VTarget      Pin 10: nRST
```

**Important Deviations:**
- **Pin 5**: UART_TX (VCOM_TX) - typically GND in standard pinout
- **Pin 7**: UART_RX (VCOM_RX) - typically KEY (not connected) in standard pinout
- **Pin 9**: VTarget output - typically GND in standard pinout

**VTarget Connection:**
- Pin 9 provides programmable 1.326V-4.200V (calibrated) output from AP1117-ADJ circuit
- Maximum current: 500mA recommended (1A absolute maximum with cooling)
- Protects target device from over-voltage when set correctly
- Can be monitored via Pin 1 (VTref sense)

### 20-Pin ARM JTAG Connector (J2)
**CUSTOM Pinout:**
```
Odd pins:  1:VTref  3:nTRST  5:TDI     7:TMS     9:TCK    11:UART_TX  13:TDO    15:nRST  17:UART_RX  19:VTarget
Even pins: 2:VTref  4:GND    6:GND     8:GND    10:GND    12:GND      14:GND    16:GND   18:GND      20:VTref
```

**Important Deviations:**
- **Pin 11**: UART_TX (VCOM_TX) - typically RTCK in standard ARM-20 pinout
- **Pin 17**: UART_RX (VCOM_RX) - typically KEY (not connected) in standard pinout
- **Pin 19**: VTarget output - typically nTRST in standard ARM-20 pinout
- **Pin 20**: VTref sense - typically GND in standard ARM-20 pinout

**UART Bridge Integration:**
- UART signals on pins 5/7 (10-pin) and 11/17 (20-pin) connect to ESP32-C3:
  - GPIO20 (D7): UART RX (receives data from target SWO/RTT)
  - GPIO21 (D6): UART TX (sends data to target)
- Enables SWO trace and RTT debugging without additional cables
- Configure via `USE_UART_BRIDGE` in [main/wifi_configuration.h](../../main/wifi_configuration.h)

### VTarget Power Supply Capability
```
Input:  5V from USB (≈ 4.3–4.4V at the AP1117 after the XIAO Schottky diode)
Output: 1.326V to 4.200V programmable (calibrated)
Load:   Up to 500 mA typical, 1A max (with thermal management)
```

**Use Cases:**
1. **Power target device** directly from debugger (no external supply needed)
2. **Match target voltage** automatically for level shifting (prevents damage)
3. **Test voltage sensitivity** by sweeping range during development

## Troubleshooting

### Voltage Won't Change
- Check GPIO3 PWM output with scope/logic analyzer
- Verify MOSFET Q1 is installed correctly
- Check R1, R3, R4, R5 and C2 against the schematic (a board with the original
  fabrication values R4 = 39k / R5 = 10k leaves Q1 off and VTarget stuck near 4.2 V)
- Allow ≥ 1 s after a change (gate filter τ ≈ 145 ms)
- Verify AP1117-ADJ is genuine part (not counterfeit)

### Voltage Unstable/Oscillating
- Add more output capacitance (try 22µF or 47µF for C3)
- Check PCB layout: minimize trace length between AP1117 and C3
- Verify ESR of C3 is <1Ω
- Add 100nF ceramic cap in parallel with C3

### Voltage Too High/Low
- Verify R6, R7 values (should be 100kΩ each) and that the VTref jumper is fitted
  (otherwise the ADC reads ≈ 0 mV while a DMM shows the real voltage)
- Check MOSFET R_DS(on) spec
- Perform calibration procedure (board-specific table if the board is outside the cluster)
- Verify input voltage (USB 5V minus the Schottky drop, ≈ 4.3–4.4V at the AP1117)

### PWM Noise on Output
- The gate filter (fc ≈ 1 Hz) already removes PWM ripple; look at the AP1117 loop,
  C3 ESR and layout instead
- Add RC filter on VTarget output
- Use lower ESR output capacitor

---

**Implementation Status**: ✅ Complete and ready for testing
**Next Steps**: Build firmware, test on hardware, calibrate if needed

## References
- ESP-IDF LEDC (PWM) API reference: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/ledc.html
- ESP-IDF ADC API reference: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/adc.html
- Seeed Studio XIAO ESP32-C3 (module info/datasheet source): https://www.seeedstudio.com/
- AP1117 / 1117-family regulator datasheets (example host): https://www.diodes.com/
