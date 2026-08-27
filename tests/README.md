# XIAO ESP32-C3 Hardware Test Suite

Automated test scripts for validating XIAO ESP32-C3 wireless DAP hardware.

## Test Files

### 0. `pyocd_elaphurelink.py` — pyOCD Probe via elaphureLink TCP (WiFi)

Connects pyOCD directly to the wireless DAP over the elaphureLink TCP protocol.
**No USB cable, no USBIP kernel driver, no extra dependencies** — only Python stdlib + pyOCD.

**Features:**

- elaphureLink handshake over TCP port 3240
- Plugs into pyOCD's `DAPAccessCMSISDAP` as a drop-in bulk interface
- CMSIS-DAP v2 (512-byte packets)
- `make_probe(host)` API for use in other scripts / pyOCD sessions
- Standalone test mode: verifies connection and reads DPIDR

**Confirmed working (2026-07-10):**

```text
elaphureLink connected — device DAP 1.0.0 @ 192.168.137.123:3240
DAP opened  vendor='windowsair'  product='CMSIS-DAP v2 (elaphureLink)'
SWD port selected
```

"No ACK" on DPIDR is expected when no target MCU is wired to the DAP SWD pins.

**Usage:**

```bash
# Probe test (no target required)
python tests/pyocd_elaphurelink.py --ip 192.168.137.123

# With target
python tests/pyocd_elaphurelink.py --ip 192.168.137.123 --target max32672
```

**As a library:**

```python
from tests.pyocd_elaphurelink import make_probe
from pyocd.core.session import Session

probe = make_probe("192.168.137.123")
with Session(probe, target_override="max32672") as session:
    session.open()
    t = session.target
    t.halt()
    print(hex(t.read_core_register("pc")))
```

**Hardware Setup:**

```text
PC WiFi ←→ Router ←→ XIAO ESP32-C3 (192.168.137.123)
                            ↕ SWD/JTAG
                       Target MCU (e.g. MAX32672)
```

---

### 1. `uart_bridge.py` — UART TCP Bridge Terminal

Interactive serial terminal (and non-interactive send/receive) over the firmware's
UART TCP bridge.  The ESP32-C3 bridges **TCP port 1234 ↔ UART1 (GPIO21 TX / GPIO20 RX)**.

**Enable in firmware first** (`main/wifi_configuration.h`):

```c
#define USE_UART_BRIDGE      1
#define UART_BRIDGE_PORT     1234
#define UART_BRIDGE_BAUDRATE 115200
```

Rebuild and flash, then:

**Usage:**

```bash
# Interactive terminal (type → UART out, UART in → screen)
python tests/uart_bridge.py

# Explicit baud rate
python tests/uart_bridge.py --baud 9600

# Send one command, print response (non-interactive)
python tests/uart_bridge.py --send "AT" --timeout 1.0

# Log all received bytes to file
python tests/uart_bridge.py --log uart_log.txt

# Different device IP
python tests/uart_bridge.py --ip 192.168.137.123 --port 1234
```

**Firmware baud-rate negotiation:** the first packet sent over TCP is interpreted as
the baud rate if it is a plain ASCII number (e.g. `"115200"`).  The script handles
this automatically — just pass `--baud`.

**Alternative:** PuTTY → Connection type **Raw** → host `dap.local` → port `1234`.

---

### 2. `test_xiao_usb.py` - USB Interface Tests

Tests DAP functionality when connected via USB cable.

**Features:**

- USB device detection
- DAP information retrieval
- VTarget voltage reading (ADC sensing)
- VTarget voltage setting (PWM control)
- SWD connection verification
- IDCODE reading

**Hardware Setup:**

```text
PC USB ←→ XIAO ESP32-C3 USB-C port
```

**Optional Connections for Full Testing:**
```
VTarget ←→ VTref (loopback for voltage verification)
SWDIO/SWCLK ←→ Target MCU (for SWD testing)
```

### 2. `test_xiao_wifi.py` - WiFi Interface Tests
Tests DAP functionality over WiFi/USBIP connection.

**Features:**
- DNS resolution (mDNS)
- Network ping test
- TCP connection to USBIP server
- USBIP protocol handshake
- Network latency measurement
- WiFi signal quality (placeholder)
- UART loopback test instructions

**Hardware Setup:**
```
PC WiFi ←→ Router ←→ XIAO ESP32-C3 WiFi
```

**Optional Connections for Full Testing:**
```
GPIO20 (RX/D7) ←→ GPIO21 (TX/D6) (UART loopback)
```

### 3. `test_vtarget_linearity.py` - VTarget Linearity Calibration
Comprehensive linearity testing and calibration for VTarget voltage output and VTref measurement accuracy with optional DMM reference measurements.

**Features:**
- Full voltage range sweep (1.25V - 5.0V)
- Multi-sample measurements with statistical analysis
- **Optional Keysight 34460A/34461A/34465A/34470A DMM integration for precision reference**
- Dual measurement comparison (DAP vs DMM)
- Linear regression and R² calculation for both DAP and DMM
- DAP accuracy validation against calibrated DMM
- Integral Non-Linearity (INL) analysis
- Differential Non-Linearity (DNL) analysis
- CSV data export with DAP and DMM columns
- Visualization plots (voltage vs setpoint, error analysis, DAP vs DMM)
- Automated pass/fail criteria evaluation

**Hardware Setup (Basic - DAP Only):**
```
PC USB ←→ XIAO ESP32-C3 USB-C port (required for VTarget power)
```

**Hardware Setup (Advanced - With DMM Reference):**
```
┌─────────────┐
│     PC      │
│             │
├──USB───────┼──→ XIAO ESP32-C3 (DAP + VTarget Generator)
│             │         │
├──USB/LAN───┼──→ Keysight DMM (Precision Reference)
└─────────────┘         │
                        │
            VTarget ────┴──→ DMM HI Terminal
            GND     ────────→ DMM LO Terminal

Connection Diagram:
    XIAO ESP32-C3          Keysight 34460A/34461A DMM
    ┌───────────┐          ┌─────────────────────┐
    │           │          │                     │
    │  VTarget  ├──────────┤ HI (Front Input)    │
    │  (GPIO3)  │   Red    │                     │
    │           │          │                     │
    │    GND    ├──────────┤ LO (Front Input)    │
    │           │  Black   │                     │
    └───────────┘          └─────────────────────┘
                                    │
                           USB/LAN to PC (VISA)
```

**Statistical Metrics:**
- Mean error and standard deviation (DAP vs Setpoint)
- Maximum error (absolute and percentage)
- Linear regression (slope, intercept, R²) for DAP
- Linear regression (DAP vs DMM) for accuracy validation
- DMM measurement as calibrated reference
- Residual analysis for non-linearity
- Step size uniformity (DNL)

## Installation

### 1. Install Python Dependencies
```bash
cd tests
pip install -r requirements.txt
```

### 2. Install pyOCD and Analysis Libraries
```bash
pip install pyocd
```

For Windows, you may also need:
```bash
pip install pywinusb
```

### 3. Install Optional Analysis Libraries (for linearity tests)
```bash
pip install numpy scipy matplotlib
```

These are required for `test_vtarget_linearity.py` to perform advanced statistical analysis and plotting.

### 4. Install PyVISA for DMM Integration (optional)
```bash
pip install pyvisa pyvisa-py
```

Required only if using Keysight DMM for reference measurements. For USB DMM connection, you may also need:
```bash
pip install pyusb
```

### 5. Install USB Drivers (Windows)
- Install Zadig: https://zadig.akeo.ie/
- Connect XIAO via USB
- In Zadig, select "WinUSB" driver for the DAP device

## Running Tests

### USB Interface Test
```bash
python test_xiao_usb.py
```

**Expected Output:**
```
=== USB Connection Test ===
[✓ PASS] USB Device Detection
    Found 1 probe(s)
    Probe 0: CMSIS-DAP v2 - 1234567890ABCDEF
[✓ PASS] USB Probe Open
    Connected to CMSIS-DAP v2

=== DAP Information Test ===
[✓ PASS] Vendor Name
    Espressif
[✓ PASS] Product Name
    CMSIS-DAP v2
[✓ PASS] Serial Number
    1234567890ABCDEF

=== VTarget Reading Test ===
[✓ PASS] VTarget Read
    3300 mV (3.300 V)

...
```

### WiFi Interface Test
```bash
# Using default hostname (dap.local)
python test_xiao_wifi.py

# Using specific IP address
python test_xiao_wifi.py --host 192.168.1.100

# Using custom port
python test_xiao_wifi.py --host dap.local --port 3240
```

**Expected Output:**
```
=== DNS Resolution Test ===
[✓ PASS] DNS Resolution
    dap.local -> 192.168.1.100

=== Network Ping Test ===
[✓ PASS] Network Ping
    Device is reachable

=== Network Latency Test (10 samples) ===
    Sample 1/10: 12.45 ms
    Sample 2/10: 11.89 ms
    ...
[✓ PASS] Network Latency
    Avg: 12.15 ms, Min: 11.23 ms, Max: 15.67 ms

...
```

### VTarget Linearity Test
```bash
# Basic test with 20 points across full range (DAP only)
python test_vtarget_linearity.py

# With Keysight DMM reference (recommended for calibration)
python test_vtarget_linearity.py -d "USB0::0x2A8D::0x1301::MY********::INSTR"

# High-resolution test with 50 points and DMM
python test_vtarget_linearity.py -n 50 -d "USB0::0x2A8D::0x1301::MY********::INSTR"

# Test specific voltages with DMM
python test_vtarget_linearity.py --voltages "1250,2000,3000,4000,5000" -d "USB0::0x2A8D::0x1301::MY********::INSTR"

# More samples per point for higher accuracy
python test_vtarget_linearity.py -m 20 -d "USB0::0x2A8D::0x1301::MY********::INSTR"

# Specify probe by serial number
python test_vtarget_linearity.py -s 1234567890ABCDEF -d "USB0::0x2A8D::0x1301::MY********::INSTR"

# Skip plotting (faster execution)
python test_vtarget_linearity.py --no-plot

# Find DMM VISA resource string:
python -m pyvisa-shell
>>> list
```

**Expected Output (with DMM):**
```
============================================================
VTarget Full Range Linearity Test
============================================================
Range: 1250-5000 mV
Test points: 20
Samples per point: 10

Connected to DMM: Keysight Technologies,34461A,MY********,A.02.14-02.40-02.14-00.49-03-01
DMM configured for precision DC voltage measurement

Testing setpoint: 1250 mV
  DAP Mean: 1248.50 mV, StdDev: 3.24 mV
  DMM Mean: 1251.23 mV, StdDev: 0.12 mV
  DAP Error vs Setpoint: -1.50 mV (-0.12%)
  DAP Error vs DMM: -2.73 mV (-0.22%)

Testing setpoint: 1447 mV
  DAP Mean: 1445.20 mV, StdDev: 2.98 mV
  DMM Mean: 1447.89 mV, StdDev: 0.09 mV
  DAP Error vs Setpoint: -1.80 mV (-0.12%)
  DAP Error vs DMM: -2.69 mV (-0.19%)

...

============================================================
Linearity Statistics
============================================================

DAP vs Setpoint:
R² (coefficient of determination): 0.999876
Slope: 0.998234
Intercept: 2.45 mV
Max non-linearity: 8.34 mV
Max DNL: 0.56%

DAP vs DMM Reference:
R²: 0.999923
Slope: 0.998654 (ideal: 1.0)
Intercept: 1.23 mV (ideal: 0.0)

DMM vs Setpoint:
R²: 0.999995
Slope: 1.000124
Intercept: -0.15 mV

DAP Mean error vs Setpoint: -2.15 mV (-0.08%)
DAP Max error vs Setpoint: 12.34 mV (0.34%)
DAP Error std dev: 4.12 mV

DAP Mean error vs DMM: -2.43 mV (-0.10%)
DAP Max error vs DMM: 8.67 mV (0.26%)

============================================================
Test Summary
============================================================
Total test points: 20
DMM reference: YES
Results saved to: test_results/

DAP Pass/Fail Criteria (vs Setpoint):
  Max error < 2%: PASS (0.34%)
  R² > 0.99: PASS (0.999876)

DAP Accuracy (vs DMM Reference):
  Max error < 1%: PASS (0.26%)
  R² > 0.995: PASS (0.999923)

Test complete!
```

### VTarget Waveform Measurement with VirtualBench

Use `measure_vtarget_vb.py` to measure the VTarget output directly with a
VirtualBench oscilloscope. Connect VTarget to Channel 1 (`mso/1`) and use the
configured probe attenuation. The script sweeps PWM from 0% to 100% in 1%
increments and uses the internal `niVB_MSO_ReadAnalog()` API to calculate
average voltage, RMS voltage, and peak-to-peak ripple.

```bash
# Run the default 101-point sweep
python measure_vtarget_vb.py

# Faster 5% sweep with a longer settling time
python measure_vtarget_vb.py --step 5 --settle 0.5

# Specify the DAP, VirtualBench, and probe settings
python measure_vtarget_vb.py --ip 192.168.137.123 --vb VB8034-314E194 --probe 10
```

The script restores VTarget to 3300 mV after the sweep and writes these files
to `test_results/`:

- `vtarget_pwm_vb_measurements.csv` - measurement data for every duty point
- `vtarget_pwm_vb_curve.png` - average, RMS, and peak-to-peak plots

**Output Files** (in `test_results/` directory):
- `vtarget_linearity_YYYYMMDD_HHMMSS.csv` - Statistical summary (DAP and DMM columns)
- `vtarget_linearity_YYYYMMDD_HHMMSS_raw.csv` - All raw measurements (DAP and DMM samples)
- `vtarget_statistics_YYYYMMDD_HHMMSS.csv` - Linearity metrics (DAP vs DMM analysis)
- `vtarget_linearity_YYYYMMDD_HHMMSS.png` - Visualization plots (3-panel with DMM comparison)

## Test Scenarios

### Scenario 1: Basic USB Functionality
**Objective:** Verify USB communication and VTarget control

1. Connect XIAO to PC via USB
2. Run `test_xiao_usb.py`
3. Verify all tests pass

**Required Hardware:**
- XIAO ESP32-C3 module
- USB-C cable

### Scenario 2: VTarget Voltage Control
**Objective:** Test programmable voltage output

1. Connect VTarget to VTref (loopback)
2. Run `test_xiao_usb.py`
3. Observe voltage changes: 3.3V → 1.8V → 5.0V
4. Verify readback matches setpoint (within 5%)

**Required Hardware:**
- XIAO ESP32-C3 module
- Wire to connect VTarget to VTref (GPIO2)

### Scenario 3: WiFi Communication
**Objective:** Verify wireless DAP functionality

1. Power XIAO via USB or external supply
2. Ensure XIAO is connected to WiFi (check LED)
3. Run `test_xiao_wifi.py`
4. Verify DNS resolution and TCP connection

**Required Hardware:**
- XIAO ESP32-C3 module
- WiFi router with DHCP
- PC on same network

### Scenario 4: UART Loopback
**Objective:** Test UART bridge functionality

1. Connect GPIO20 (RX/D7) to GPIO21 (TX/D6)
2. Open serial terminal (115200 baud)
3. Type characters - should echo back
4. Verify in test output

**Required Hardware:**
- XIAO ESP32-C3 module
- Jumper wire for loopback
- Serial terminal software

### Scenario 5: SWD Target Connection
**Objective:** Verify debug interface works

1. Connect target MCU to debug header
2. Connect VTarget to target's VDD
3. Run `test_xiao_usb.py`
4. Allow SWD connection test to proceed
5. Verify IDCODE is read correctly

**Required Hardware:**
- XIAO ESP32-C3 module
- Target ARM Cortex-M MCU
- Connection wires (SWDIO, SWCLK, GND, VTarget)

### Scenario 6: VTarget Linearity Calibration
**Objective:** Characterize and verify VTarget output linearity across full voltage range with precision DMM reference

1. Connect XIAO to PC via USB (required for VTarget power)
2. Connect Keysight DMM to VTarget output:
   - DMM HI (red) → VTarget (GPIO3 output)
   - DMM LO (black) → GND
3. Connect DMM to PC via USB or LAN
4. Find DMM VISA resource: `python -m pyvisa-shell` then `list`
5. Run test: `python test_vtarget_linearity.py -n 30 -m 15 -d "USB0::0x2A8D::0x1301::MY********::INSTR"`
6. Verify R² > 0.99 (DAP vs Setpoint) and R² > 0.995 (DAP vs DMM)
7. Review CSV data for calibration coefficients
8. Examine plot for visual confirmation

**Required Hardware:**
- XIAO ESP32-C3 module
- USB-C cable (must provide sufficient current for VTarget)
- Keysight 34460A/34461A/34465A/34470A DMM
- BNC or banana plug cables (2x)
- USB cable for DMM or Ethernet connection

**Optional Hardware:**
- DMM test leads with fine probes
- Kelvin clips for improved connection
- Shielded cables to reduce noise

**Best Practices:**
- **Allow 5-minute warmup before testing** (both DAP and DMM)
- Keep ambient temperature stable (±2°C)
- Use quality USB cable with good power delivery
- Run DMM auto-calibration before testing (*CAL?)
- Use DMM 10 NPLC setting for lowest noise
- Shield cables from switching power supplies
- Ground DMM and DAP to same reference
- Run multiple test cycles and compare results
- Store CSV files for batch comparison across units
- Verify DMM calibration certificate is current

**DMM Configuration Details:**
- The script automatically configures the DMM:
  - Reset to known state (*RST)
  - DC Voltage mode, 10V range
  - 100µV resolution (0.0001V)
  - 10 NPLC integration (low noise, ~167ms @ 60Hz)
  - Auto-zero disabled for speed
- DMM provides traceable reference for DAP calibration
- Typical DMM accuracy: ±(0.0035% + 0.0005%) of reading
- DAP accuracy evaluated against DMM reference

**Interpreting DMM Results:**
- **DAP vs Setpoint**: Overall system performance
- **DAP vs DMM**: True DAP accuracy (removes setpoint errors)
- **DMM vs Setpoint**: PWM generator accuracy
- **Target**: DAP vs DMM error < 1% across full range

## Troubleshooting

### USB Test Issues

**Problem:** "No USB DAP probes found"
- **Solution:** Check USB cable is connected
- **Solution:** Install WinUSB driver using Zadig (Windows)
- **Solution:** Try different USB port

**Problem:** "VTarget read returns 0V"
- **Solution:** Check GPIO2 connection to voltage divider
- **Solution:** Verify VTarget or VTref is powered
- **Solution:** Check solder joints on PCB

**Problem:** "SWD connection failed"
- **Solution:** Ensure target MCU is powered
- **Solution:** Check SWDIO and SWCLK connections
- **Solution:** Verify target supports SWD (not JTAG-only)

### WiFi Test Issues

**Problem:** "Cannot resolve dap.local"
- **Solution:** Check XIAO is powered on
- **Solution:** Verify WiFi credentials in firmware
- **Solution:** Try using IP address instead: `--host 192.168.1.X`
- **Solution:** Check router supports mDNS/Bonjour

**Problem:** "Connection refused on port 3240"
- **Solution:** Verify USBIP server is enabled in firmware
- **Solution:** Check firewall settings
- **Solution:** Try different port if customized

**Problem:** "High latency (>50ms)"
- **Solution:** Move closer to WiFi router
- **Solution:** Reduce WiFi congestion (change channel)
- **Solution:** Check for interference

### Linearity Test Issues

**Problem:** "No DAP probes found"
- **Solution:** Ensure USB connection is established
- **Solution:** Install WinUSB driver using Zadig (Windows)
- **Solution:** Verify USB cable supports data transfer (not charge-only)

**Problem:** "Poor linearity (R² < 0.99)"
- **Solution:** Allow adequate warmup time (5+ minutes)
- **Solution:** Check USB power supply quality
- **Solution:** Verify VTarget PWM output is not loaded
- **Solution:** Test with external precision power supply
- **Solution:** Check for noise on ADC input (GPIO2)

**Problem:** "High measurement noise (StdDev > 10mV)"
- **Solution:** Reduce electromagnetic interference sources
- **Solution:** Improve grounding connections
- **Solution:** Increase samples per point: `-m 20` or higher
- **Solution:** Use shielded cables for measurements

**Problem:** "Voltage setpoint rejected"
- **Solution:** Verify voltage is within 1250-5000mV range
- **Solution:** Check VTarget power supply can provide required current
- **Solution:** Ensure USB port provides adequate power (500mA+)

**Problem:** "numpy/scipy not available"
- **Solution:** Install analysis libraries: `pip install numpy scipy matplotlib`
- **Solution:** Script will run with basic statistics if scipy unavailable
- **Solution:** Advanced metrics (R², DNL, INL) require scipy

**Problem:** "Cannot connect to DMM" or "DMM not found"
- **Solution:** Install PyVISA: `pip install pyvisa pyvisa-py`
- **Solution:** Find DMM resource string: `python -m pyvisa-shell` then type `list`
- **Solution:** For USB DMM, install libusb: `pip install pyusb`
- **Solution:** Check DMM is powered on and USB/LAN cable connected
- **Solution:** Try NI-VISA instead of pyvisa-py for better compatibility
- **Solution:** Verify DMM is in local mode (not remote locked)

**Problem:** "DMM measurements have high noise"
- **Solution:** Increase integration time (script uses 10 NPLC by default)
- **Solution:** Run DMM auto-calibration: Send `*CAL?` command
- **Solution:** Use shielded cables for DMM connections
- **Solution:** Verify DMM and DAP share common ground
- **Solution:** Move away from switching power supplies
- **Solution:** Allow longer settling time between voltage changes

**Problem:** "DAP vs DMM error > 1%"
- **Solution:** Check voltage divider resistor values (should be 1% tolerance)
- **Solution:** Verify ADC calibration in firmware
- **Solution:** Check for voltage drop in VTarget output path
- **Solution:** Ensure adequate USB power supply current
- **Solution:** Calibrate DAP using DMM measurements as reference

## Interpreting Results

### Test Status Codes
- `✓ PASS` - Test passed successfully
- `✗ FAIL` - Test failed, check message for details

### Pass Criteria

**VTarget Accuracy:**
- Readback error < 5% of setpoint
- Example: 3.3V ±165mV is acceptable

**Network Latency:**
- < 20ms average: Excellent
- 20-50ms: Good
- 50-100ms: Acceptable for debugging
- > 100ms: May experience slow performance

**USB Connection:**
- Device must be detected within 5 seconds
- Vendor commands must respond within 1 second

**VTarget Linearity:**
- R² (coefficient of determination) > 0.99
- Maximum error < 2% across full range
- Standard deviation < 10mV per measurement point
- DNL (Differential Non-Linearity) < 1%
- INL (Integral Non-Linearity) < 15mV

**Statistical Metrics Interpretation:**
- **R² = 1.0**: Perfect linear relationship
- **R² > 0.999**: Excellent linearity, production-ready
- **R² > 0.99**: Good linearity, acceptable for most applications
- **R² < 0.99**: Poor linearity, investigate hardware issues
- **Slope ≈ 1.0**: Accurate voltage transfer (ideal: 1.0)
- **Intercept ≈ 0**: Minimal offset error (ideal: 0mV)
- **DNL**: Step-to-step uniformity (< 0.5% is excellent)
- **INL**: Maximum deviation from ideal line (< 10mV is excellent)

## Advanced Usage

### Custom Voltage Test Sequence
```python
from test_xiao_usb import XiaoUSBTest

test = XiaoUSBTest()
test.connect_usb()

# Test custom voltage range
voltages = [1250, 1500, 1800, 2500, 3300, 5000]
for v in voltages:
    test.test_vtarget_set(v)
    time.sleep(0.5)

test.disconnect()
```

### Network Performance Monitoring
```python
from test_xiao_wifi import XiaoWiFiTest

test = XiaoWiFiTest(host="192.168.1.100")
ip = test.test_dns_resolution()

# Monitor latency continuously
while True:
    test.test_latency(ip, samples=5)
    time.sleep(5)
```

### Automated Linearity Calibration
```python
from test_vtarget_linearity import VTargetLinearityTest

# Create test instance
test = VTargetLinearityTest()

# Connect to probe
if test.connect():
    # Run comprehensive 50-point test with 20 samples each
    test.test_full_range(num_points=50)
    test.MEASUREMENT_SAMPLES = 20
    
    # Calculate statistics
    stats = test.calculate_linearity_statistics()
    
    # Save results
    test.save_results_csv()
    test.save_statistics_csv(stats)
    test.plot_results()
    
    # Disconnect
    test.disconnect()
    
    # Check pass/fail
    if stats['r_squared'] > 0.99 and abs(stats['max_error_percent']) < 2.0:
        print("✓ CALIBRATION PASSED")
    else:
        print("✗ CALIBRATION FAILED")
```

### Batch Testing Multiple Units
```python
from test_vtarget_linearity import VTargetLinearityTest
import time

# List of probe serial numbers
probes = ["SN001", "SN002", "SN003"]

results_summary = []

for serial in probes:
    print(f"\nTesting probe: {serial}")
    test = VTargetLinearityTest(serial_number=serial)
    
    if test.connect():
        test.test_full_range(num_points=30)
        stats = test.calculate_linearity_statistics()
        
        # Save with unit-specific filename
        test.save_results_csv(f"linearity_{serial}.csv")
        test.save_statistics_csv(stats, f"stats_{serial}.csv")
        
        results_summary.append({
            'serial': serial,
            'r_squared': stats['r_squared'],
            'max_error_percent': stats['max_error_percent']
        })
        
        test.disconnect()
        time.sleep(2)

# Print batch summary
print("\n" + "="*60)
print("Batch Test Summary")
print("="*60)
for result in results_summary:
    status = "PASS" if result['r_squared'] > 0.99 and abs(result['max_error_percent']) < 2.0 else "FAIL"
    print(f"{result['serial']}: R²={result['r_squared']:.6f}, MaxErr={result['max_error_percent']:.2f}% [{status}]")
```

## Contributing

To add new tests:

1. Create test method in appropriate class
2. Use `self.log_test()` for result reporting
3. Follow naming convention: `test_<feature>()`
4. Update this README with test description

## License

Same as parent project (MIT)

## pyOCD Vendor Command Protocol

The VTarget commands use CMSIS-DAP Vendor Commands via `probe.vendor(index, data)`.

> **Critical:** `index` is an **offset** (0–31) from `DAP_VENDOR0` (`0x80`), not the raw command ID.
> pyOCD computes `cmd_id = 0x80 + index` internally and **strips the echoed command byte** from the response.

|Command|index|cmd_id|Request data|Response|
|-------|-----|------|------------|--------|
|Read VTarget|`1`|`0x81`|`[]`|`[LOW, HIGH]` — mV little-endian. `0xFFFF` = ADC error|
|Set VTarget|`2`|`0x82`|`[LOW, HIGH]` — mV little-endian (1250–5000)|`[0x00]` ok · `[0x01]` range err · `[0xFF]` error|

**Minimal example:**

```python
# Read
response = probe.vendor(1, [])
voltage_mv = response[0] | (response[1] << 8)

# Set 3.3V
mv = 3300
probe.vendor(2, [mv & 0xFF, (mv >> 8) & 0xFF])
```

**Common mistake:** passing the full command ID (`0x81`) as the index causes pyOCD to send `0x80 + 0x81 = 0x101`, which the firmware never handles.

## Measured VTref Accuracy

Results from hardware validation (ESP32-C3 XIAO, eFuse Vref calibration, 20-sample average, 1/2 voltage divider on GPIO2):

|Supply (mV)|Measured (mV)|Error (mV)|Error (%)|
|-----------|-------------|----------|---------|
|606|614|+8|+1.3%|
|846|858|+12|+1.4%|
|1649|1662|+13|+0.8%|
|2604|2628|+24|+0.9%|
|2984|2994|+10|+0.3%|
|3460|3490|+30|+0.9%|
|3975|3997|+22|+0.6%|
|5054|5067|+13|+0.3%|

Max error: **+30 mV** at 3.46 V. Consistent positive bias (~10–30 mV) across 0.6–5.0 V range. All readings within ±1.5% of true value.

## References
- Zadig (Windows USB driver tool): https://zadig.akeo.ie/
- pyOCD: https://pyocd.io/
- PyVISA: https://pyvisa.readthedocs.io/
