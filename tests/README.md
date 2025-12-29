# XIAO ESP32-C3 Hardware Test Suite

Automated test scripts for validating XIAO ESP32-C3 wireless DAP hardware.

## Test Files

### 1. `test_xiao_usb.py` - USB Interface Tests
Tests DAP functionality when connected via USB cable.

**Features:**
- USB device detection
- DAP information retrieval
- VTarget voltage reading (ADC sensing)
- VTarget voltage setting (PWM control)
- SWD connection verification
- IDCODE reading

**Hardware Setup:**
```
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

## Installation

### 1. Install Python Dependencies
```bash
cd tests
pip install -r requirements.txt
```

### 2. Install pyOCD
```bash
pip install pyocd
```

For Windows, you may also need:
```bash
pip install pywinusb
```

### 3. Install USB Drivers (Windows)
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

## Contributing

To add new tests:

1. Create test method in appropriate class
2. Use `self.log_test()` for result reporting
3. Follow naming convention: `test_<feature>()`
4. Update this README with test description

## License

Same as parent project (MIT)
