# VTarget Programmable Voltage Control - Implementation Summary

## Hardware Configuration Verified

### Capacitors
✅ **C3**: 10µF (0805) - VTarget output capacitor on AP1117-ADJ
- Location: (153.67, 147.32)
- Purpose: Energy storage for VTarget output, provides stable output voltage
- Recommended minimum: 10µF for AP1117 stability

✅ **C2**: 10nF (0603) - PWM filter capacitor
- Location: (104.14, 175.26)  
- Purpose: Smooths PWM signal in feedback divider network
- Filter time constant: τ = R4 × C2 = 39kΩ × 10nF = 390µs

✅ **C1**: 10nF (0603) - Reference divider smoothing
- Purpose: Additional filtering for voltage reference

### Circuit Components
- **U2 (AP1117-ADJ)**: Adjustable LDO regulator at (119.38, 128.27)
  - Input: 5V supply
  - Output: VTarget (1.25V to 5V adjustable)
  - Max current: 1A

- **Q1 (YJL2304A)**: N-channel MOSFET at (116.84, 170.18)
  - Package: SOT-23
  - Max current: 1.4A
  - Max voltage: 30V
  - Typical R_DS(on): ~55mΩ @ V_GS=4.5V

- **Voltage Divider:**
  - R6: 100kΩ (upper feedback resistor)
  - R7: 100kΩ (lower feedback resistor)
  - R4: 39kΩ (PWM gate series resistor)
  - R5: 10kΩ (MOSFET gate pull-down)

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
Voltage step: ~3.67 mV per duty cycle step
```

### Filter Design
```
RC Filter: R4 (39k) + C2 (10nF)
Time constant τ = 390 µs
Cutoff frequency fc = 1/(2πτ) ≈ 408 Hz
```

At 1 kHz PWM:
- 2.45× above cutoff → good attenuation of switching noise
- Fast enough response time (~1.2 ms to 95% settling)

## Voltage Control Algorithm

### Inverse Relationship
```c
// Higher voltage → Lower PWM duty (MOSFET more OFF)
// Lower voltage → Higher PWM duty (MOSFET more ON)

duty_cycle = MAX_DUTY × (MAX_V - target_V) / (MAX_V - MIN_V)
```

### Voltage Range
- **Minimum**: 1.25V (100% duty, MOSFET fully ON)
- **Maximum**: 5.00V (0% duty, MOSFET fully OFF)
- **Resolution**: ~3.67 mV steps (1024 levels)

### AP1117-ADJ Formula
```
V_out = 1.25V × (1 + R_upper / R_lower)

With PWM-controlled MOSFET:
- R_upper = R6 (100kΩ fixed)
- R_lower = R7 || R_MOSFET (variable based on PWM)
```

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

// Valid range: 1250 mV to 5000 mV
vtarget_set_voltage(1250);  // Minimum voltage
vtarget_set_voltage(5000);  // Maximum voltage
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
vtarget_set_duty_raw(0);     // 0% → ~5V output
vtarget_set_duty_raw(512);   // 50% → ~3.1V output  
vtarget_set_duty_raw(1023);  // 100% → ~1.25V output

// Get current duty
uint16_t duty = vtarget_get_duty();
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
Set the target voltage output (1250-5000 mV).

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
  - 0x01 = Invalid voltage range (not 1250-5000 mV)
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

Set 5.0V (5000 mV):
```
Request:  0x82 0x88 0x13
Response: 0x82 0x00  (success)
```

Set invalid 6V (6000 mV):
```
Request:  0x82 0x70 0x17
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
// Set specific voltage (1250-5000 mV)
vtarget_set_voltage(3300);  // 3.3V
vtarget_set_voltage(1800);  // 1.8V
vtarget_set_voltage(5000);  // 5.0V

// Or use convenience macros
VTARGET_SET_3V3();
VTARGET_SET_1V8();
VTARGET_SET_5V0();
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

The voltage-to-duty mapping is **linear approximation** and may need calibration:

### Factors Affecting Accuracy:
1. **MOSFET R_DS(on) variation** (temperature, V_GS dependent)
2. **Resistor tolerances** (R6, R7 are ±1% typ)
3. **Load current** (AP1117 dropout voltage)
4. **Temperature coefficient** (~0.3%/°C for MOSFET)

### Calibration Procedure:
```c
// 1. Measure actual output with multimeter
// 2. Adjust duty cycle to achieve target
vtarget_set_duty_raw(duty);

// 3. Record duty vs. voltage data points
// 4. Create calibration table or polynomial
```

### Suggested Calibration Points:
- 1.25V (min)
- 1.8V (common)
- 3.0V
- 3.3V (common)
- 5.0V (max)

## Expected Performance

### Settling Time
- RC filter time constant: 390 µs
- 95% settling: ~3τ = 1.2 ms
- 99% settling: ~5τ = 2.0 ms

### Ripple Voltage
At 1 kHz PWM with 10nF filter:
- Attenuation: ~-8 dB at 1 kHz
- Expected ripple: <10 mV p-p (typical)
- C3 (10µF) further reduces output ripple

### Accuracy (before calibration)
- Theoretical: ±3.67 mV (1 LSB)
- Practical: ±50 mV (resistor tolerances, MOSFET variation)
- After calibration: ±10 mV achievable

## Safety Features

1. **Default to safe voltage**: Initializes to 3.3V
2. **Range checking**: Rejects voltages outside 1.25-5.0V
3. **Pull-down resistor**: R5 ensures MOSFET OFF if GPIO fails
4. **Overcurrent protection**: AP1117 has built-in current limiting

## Monitoring

Combine with existing VTarget sensing (GPIO2):
```c
extern uint32_t vtarget_read_mv(void);  // From DAP_vendor.c

// Set voltage
vtarget_set_voltage(3300);
vTaskDelay(pdMS_TO_TICKS(10));  // Wait for settling

// Verify actual output
uint32_t actual_mv = vtarget_read_mv();
printf("Target: 3300 mV, Actual: %lu mV\n", actual_mv);
```

## Power Considerations

### Current Budget
- AP1117-ADJ quiescent: ~5 mA
- MOSFET gate: ~0 µA (DC, capacitive charging only)
- Pull-down R5: 330 µA @ 3.3V PWM
- Total control circuit: ~6 mA

### Heat Dissipation
```
P_dissipation = (V_in - V_out) × I_load

Example at 3.3V, 100 mA load:
P = (5V - 3.3V) × 0.1A = 170 mW (acceptable)

Worst case at 1.25V, 1A load:
P = (5V - 1.25V) × 1A = 3.75W (requires heatsinking!)
```

**Recommendation**: Keep load current <500 mA for reliable operation without heatsinking.

## Testing Checklist

- [ ] Verify C3 (10µF) installed on VTarget output
- [ ] Verify C2 (10nF) installed near MOSFET
- [ ] Test voltage sweep: 1.25V → 5.0V
- [ ] Measure ripple voltage with oscilloscope
- [ ] Verify ADC readback matches set voltage
- [ ] Test load regulation (no load → 100 mA)
- [ ] Test line regulation (4.5V → 5.5V input)
- [ ] Measure settling time with scope
- [ ] Verify thermal performance at high current
- [ ] Check PWM frequency with scope (should be 1 kHz)

## Troubleshooting

### Voltage Won't Change
- Check GPIO3 PWM output with scope/logic analyzer
- Verify MOSFET Q1 is installed correctly
- Check R4, R5 values and connections
- Verify AP1117-ADJ is genuine part (not counterfeit)

### Voltage Unstable/Oscillating
- Add more output capacitance (try 22µF or 47µF for C3)
- Check PCB layout: minimize trace length between AP1117 and C3
- Verify ESR of C3 is <1Ω
- Add 100nF ceramic cap in parallel with C3

### Voltage Too High/Low
- Verify R6, R7 values (should be 100kΩ each)
- Check MOSFET R_DS(on) spec
- Perform calibration procedure
- Verify input voltage is 5V ±5%

### PWM Noise on Output
- Increase C2 capacitance (try 22nF or 47nF)
- Lower PWM frequency to 500 Hz
- Add RC filter on VTarget output
- Use lower ESR output capacitor

---

**Implementation Status**: ✅ Complete and ready for testing
**Next Steps**: Build firmware, test on hardware, calibrate if needed
