# wireless-esp8266-dap Codebase Guide

## CRITICAL: Code Change Policy
**ALWAYS discuss and get user approval before making ANY code changes.** Present proposed changes, explain rationale, and wait for user confirmation. The user will review and decide if changes are correct before implementation.

## CRITICAL: File Organization Policy
**KEEP THE ROOT DIRECTORY CLEAN.** All AI-generated scripts, analysis tools, and documentation files MUST be placed in the appropriate subdirectories:

- **Scripts and utilities:** `circuit_ESP32C3_Xiao/scripts/`
  - Python analysis scripts (e.g., `verify_lcsc.py`, `analyze_components.py`)
  - Automation tools and helpers
  - Include a README.md in the scripts folder documenting each script's purpose

- **Documentation and reports:** `circuit_ESP32C3_Xiao/documentations/`
  - Technical documentation (e.g., `VTARGET_PWM_IMPLEMENTATION.md`)
  - Verification reports (e.g., `COMPONENT_VERIFICATION_REPORT.md`)
  - Analysis outputs and reference documents
  - PCB schematics (PDF, PNG, SVG)

**DO NOT create files in the project root directory unless they are:**
- Core build system files (CMakeLists.txt, sdkconfig.*)
- Project configuration (wireless-esp8266-dap.code-workspace)
- Standard repository files (README.md, LICENSE, .gitignore)

This organization prevents clutter and maintains a clean project structure.

## CRITICAL: Documentation References Policy
For any **new or updated project documentation** (especially in `circuit_ESP32C3_Xiao/documentations/`), include a dedicated `## References` section.

Rules:
- Prefer primary/authoritative sources (official websites, EUR-Lex, FCC, manufacturer datasheets).
- It is OK to reference standards by number and link to the standards catalog page (do not copy standards text into the repo).
- Include links to supporting material used during engineering decisions (websites, PDFs, YouTube videos, books), when relevant.
- Keep references focused; avoid huge pasted URL dumps when the document already contains inline links.

Scope notes:
- This policy applies to **project documentation** (repo-authored docs).
- Do **not** edit environment artifacts like `.venv/**`.
- Avoid modifying third-party/vendor/upstream documentation unless explicitly requested.

Markdown link notes (important for this repo):
- Links written in this file live under `.github/`, so use `../` prefixes when linking to repo files (example: `../main/wifi_handle.c`).
- Avoid `#L...` line-fragment links in Markdown here; some VS Code link checkers treat fragments as part of the filename and will report false "file not found" errors.

## Project Overview
Wireless CMSIS-DAP debugger implementation using ESP8266/ESP32/ESP32-C3/ESP32-S3 chips. Enables wireless ARM Cortex-M debugging via USBIP protocol over WiFi, eliminating physical USB connections.

## Architecture

### Core Components (`components/`)
- **DAP/**: CMSIS-DAP v1.0/v2.0 protocol implementation with SPI-accelerated SWD (up to 40MHz)
- **USBIP/**: USB-over-IP server implementing USB device emulation (HID/WinUSB descriptors)
- **corsacOTA/**: Over-the-air firmware updates via TCP (port 3241)
- **elaphureLink/**: Keil-native debugging without USBIP (WebSocket-based, disabled by default)
- **kcp/**: Experimental KCP protocol support (not for production use)

### Main Application (`main/`)
- **DAP_handle.c**: Bridges USBIP URB packets to DAP command processing
- **usbip_server.c**: TCP server (port 3240) handling USBIP protocol handshake and URB transactions
- **wifi_handle.c**: Multi-SSID WiFi connection with mDNS (`dap.local`)
- **uart_bridge.c**: Optional UART-to-TCP bridge for SWO/RTT trace (port 1234, disabled by default)
- **vtarget_pwm.c**: Programmable target voltage control (ESP32-C3 only, 1.25V-5.0V via PWM)

### Data Flow
```
Debugger (Keil/OpenOCD) → USBIP client → WiFi → ESP (port 3240) → USBIP server → DAP_handle → CMSIS-DAP → SWD/JTAG pins
```

## Multi-Chip Support

### Target Selection
Use ESP-IDF's `idf.py set-target <chip>` before building:
- `esp8266` (legacy, uses ESP8266_RTOS_SDK)
- `esp32` / `esp32c3` / `esp32s3` (modern ESP-IDF v4.4.2+)

### Conditional Compilation Pattern
Check chip-specific code with `CONFIG_IDF_TARGET_*` macros:
```c
#if defined(CONFIG_IDF_TARGET_ESP32C3)
    vtarget_pwm_init();  // Only ESP32-C3 supports VTarget
#elif defined(CONFIG_IDF_TARGET_ESP8266)
    // ESP8266-specific initialization
#endif
```
See [main/wifi_handle.c](../main/wifi_handle.c) for GPIO mapping examples per chip.

## Critical Build System Details

### ESP8266 vs ESP32 Build Path
- **ESP8266**: Uses bundled `ESP8266_RTOS_SDK/` and root `idf.py` wrapper
- **ESP32/C3/S3**: Requires separate ESP-IDF v4.4.2+ installation with system `idf.py`

### Build Commands
```bash
# ESP32-C3 example (most common for new designs)
idf.py set-target esp32c3
idf.py build
idf.py -p COM5 flash monitor

# ESP8266 (legacy)
python ./idf.py build
python ./idf.py -p COM5 flash
```

### Configuration Files
- **sdkconfig.defaults.{esp8266,esp32,esp32c3,esp32s3}**: Target-specific defaults merged on `set-target`
- **main/wifi_configuration.h**: Runtime WiFi credentials, feature toggles (OTA, UART bridge, mDNS)
- **main/dap_configuration.h**: USB mode (WinUSB vs HID), packet size, USB 3.0 support

## Important Conventions

### Feature Toggle Pattern
All optional features use `#define` flags in [wifi_configuration.h](../main/wifi_configuration.h):
```c
#define USE_OTA          0  // OTA disabled
#define USE_UART_BRIDGE  0  // UART bridge disabled
#define USE_MDNS         1  // mDNS enabled
```
These propagate to `main.c` initialization via `#if (USE_FEATURE == 1)` checks.

### GPIO Pin Assignments
**Each chip has different GPIO mappings** - see README.md tables:
- ESP8266: SWCLK=GPIO14, SWDIO=GPIO13
- ESP32-C3: SWCLK=GPIO6, SWDIO=GPIO7, VTarget Sense=GPIO2 (ADC), VTarget PWM=GPIO3
- ESP32-S3: SWCLK=GPIO12, SWDIO=GPIO11

**Never hardcode GPIO numbers** - use chip-conditional blocks or refer to documentation.

### Task Affinity (ESP32-S3)
Core 1 is reserved for DAP processing to avoid WiFi interference:
```c
#define DAP_TASK_AFFINITY 1  // ESP32-S3: Core 1
```

## Testing

### Hardware Test Suite (`tests/`)
Python scripts require `pyusb` (USB tests) and network connectivity (WiFi tests):
- **test_xiao_usb.py**: DAP USB functionality, VTarget control, SWD connection
- **test_xiao_wifi.py**: USBIP over WiFi, mDNS resolution, network latency
- **test_vtarget_linearity.py**: VTarget calibration with optional Keysight DMM integration

Run tests via `python tests/test_*.py` with hardware connected.

## Known Issues & Constraints

### Network Sensitivity
UDP broadcast storms (DropBox LAN Sync, Logitech Arx) can cause severe packet loss. Use wired AP connections when debugging is unstable.

### Speed Limitations
- Pure GPIO: ~2MHz max
- SPI acceleration: 40MHz (selected automatically when clock ≥10MHz)
- **TCP latency is the primary bottleneck**, not GPIO speed

### USBIP URB Size Limit
USB-HID limited to 255 bytes/URB. WinUSB mode uses 512 bytes (configured via `USE_WINUSB` in [dap_configuration.h](../main/dap_configuration.h)).

## Development Workflows

### Adding New Chip Support
1. Create `sdkconfig.defaults.{newchip}` with GPIO pin mappings
2. Add GPIO definitions in `main/wifi_handle.c` using `#elif defined CONFIG_IDF_TARGET_NEWCHIP`
3. Update README.md pin tables
4. Test with `idf.py set-target newchip`

### Debugging Build Issues
- Flash size mismatches: Check `CONFIG_ESPTOOLPY_FLASHSIZE` in sdkconfig
- OTA failures: Ensure partition table matches flash size (see `CONFIG_PARTITION_TABLE_FILENAME`)
- Link errors: Verify ESP-IDF version matches requirement (v4.4.2+ for ESP32 variants)

### Performance Optimization
Target 40MHz SPI mode by ensuring `DAP_DEFAULT_SWJ_CLOCK >= 10000000` in DAP configuration. Monitor network with Wireshark during debugging to identify broadcast storms.

## Hardware Integration Details

### VTarget Programmable Voltage (ESP32-C3 Only)

**Circuit Topology:**
- **AP1117-ADJ** LDO regulator with PWM-controlled feedback for 1.25V-5.0V output
- **YJL2304A** N-channel MOSFET in feedback divider (SOT-23, 1.4A max)
- **PWM filtering**: R4 (39kΩ) + C2 (10nF) = 390µs time constant, 408Hz cutoff
- **Voltage divider**: R6/R7 (100kΩ each) for AP1117 regulation
- **Output capacitance**: C3 (10µF) for load stability

**PWM Configuration:**
- GPIO3 @ 1kHz, 10-bit resolution (1024 steps)
- **Inverse relationship**: Higher duty = lower voltage (MOSFET ON pulls down feedback)
- Settling time: ~1.2ms (95%), ripple <10mV p-p typical
- Auto-initialized to 3.3V on ESP32-C3 startup in [main/main.c](../main/main.c)

**Software Control:**
```c
#include "main/vtarget_pwm.h"

// Set voltage (1250-5000 mV range)
vtarget_set_voltage(3300);  // 3.3V common target
vtarget_set_voltage(1800);  // 1.8V for low-power MCUs

// Read voltage via ADC (GPIO2 with 1/2 divider)
uint16_t voltage = vtarget_read_mv();  // 20-sample average
```

**DAP Vendor Commands:**
- **0x81** (Read VTarget): Returns 2 bytes little-endian millivolts, 0xFFFF = error
- **0x82** (Set VTarget): Accepts 2 bytes voltage (mV), returns 0x00=success, 0x01=range error

**ADC Sensing (GPIO2):**
- 1/2 voltage divider → 0-6.6V measurable range
- 12-bit ADC with 11dB attenuation, esp_adc_cal calibration
- Multi-sample averaging in [DAP_vendor.c](../components/DAP/source/DAP_vendor.c)

**Calibration Considerations:**
- MOSFET R_DS(on) varies with temperature (~0.3%/°C)
- Resistor tolerance ±1% affects accuracy
- Expected ±50mV before calibration, ±10mV achievable after
- Calibration points: 1.25V, 1.8V, 3.0V, 3.3V, 5.0V

**Thermal Limits:**
- <500mA recommended without heatsinking
- Worst case: (5V - 1.25V) × 1A = 3.75W requires thermal management

### ESP32-C3 XIAO Reference Design

**Debug Connector Options** ([circuit_ESP32C3_Xiao/](../circuit_ESP32C3_Xiao/)):
1. **J3**: 10-pin Cortex Debug (1.27mm SMD) - compact probe interface
2. **J1**: 10-pin Cortex Debug (2.54mm IDC) - standard through-hole
3. **J2**: 20-pin ARM JTAG (2.54mm IDC) - extended pinout with UART

**10-Pin Connector Pinout (J1/J3) - NON-STANDARD:**
```
Pin 1: VTref        Pin 2: TMS/SWDIO
Pin 3: GND          Pin 4: TCK/SWCLK
Pin 5: UART_TX      Pin 6: TDO/SWO
Pin 7: UART_RX      Pin 8: TDI
Pin 9: VTarget      Pin 10: nRST
```
**Note:** Pins 5/7 carry UART signals (VCOM_TX/VCOM_RX) instead of standard GND. Pin 9 is VTarget, not GND.

**20-Pin Connector Pinout (J2) - CUSTOM VARIANT:**
```
Odd pins:  1:VTref  3:nTRST  5:TDI     7:TMS     9:TCK    11:UART_TX  13:TDO    15:nRST  17:UART_RX  19:VTarget
Even pins: 2:VTref  4:GND    6:GND     8:GND    10:GND    12:GND      14:GND    16:GND   18:GND      20:VTref
```
**Note:** Pins 11/17 carry UART bridge signals. Pin 19 is VTarget output, pin 20 is VTref sense.

**Key Hardware Features:**
- Programmable VTarget power supply (1.25V-5.0V via PWM, ESP32-C3 only)
- Integrated UART bridge on debug connectors (pins 5/7 on 10-pin, pins 11/17 on 20-pin)
- UART bridge connects ESP GPIO20 (RX/D7) ↔ GPIO21 (TX/D6) for SWO/RTT trace
- LED status indicator: GPIO10 for WiFi connection

**Pin Mapping Critical Rules:**
- **NEVER hardcode GPIO numbers** - always use `#if defined(CONFIG_IDF_TARGET_*)`
- ESP8266: SWCLK=14, SWDIO=13
- ESP32-C3: SWCLK=6, SWDIO=7, VTarget_ADC=2, VTarget_PWM=3
- ESP32-S3: SWCLK=12, SWDIO=11
- See [main/wifi_handle.c](../main/wifi_handle.c) for chip-specific GPIO definitions

### Circuit Documentation
- [circuit_ESP32C3_Xiao/documentations/VTARGET_PWM_IMPLEMENTATION.md](../circuit_ESP32C3_Xiao/documentations/VTARGET_PWM_IMPLEMENTATION.md): Complete PWM voltage control design
- [circuit_ESP32C3_Xiao/documentations/](../circuit_ESP32C3_Xiao/documentations/): Schematic PDF/SVG, PCBA preview, verification reports
- [circuit_ESP32C3_Xiao/scripts/](../circuit_ESP32C3_Xiao/scripts/): Python analysis and verification scripts (verify_lcsc.py, analyze_components.py)
- [circuit_ESP32C3_Xiao/doc/](../circuit_ESP32C3_Xiao/doc/): ARM JTAG pinouts, component datasheets

## Key Files Reference
- [main/main.c](../main/main.c): Entry point, task initialization, chip-specific VTarget init
- [main/DAP_handle.c](../main/DAP_handle.c): USBIP-to-DAP packet translation
- [main/vtarget_pwm.c](../main/vtarget_pwm.c): ESP32-C3 PWM voltage control (1kHz LEDC)
- [components/DAP/source/DAP_vendor.c](../components/DAP/source/DAP_vendor.c): VTarget vendor commands 0x81/0x82
- [components/DAP/source/](../components/DAP/source/): CMSIS-DAP core logic, SWD/JTAG implementations
- [circuit_ESP32C3_Xiao/scripts/verify_lcsc.py](../circuit_ESP32C3_Xiao/scripts/verify_lcsc.py): LCSC part number verification utility
- [circuit_ESP32C3_Xiao/scripts/analyze_components.py](../circuit_ESP32C3_Xiao/scripts/analyze_components.py): Component analysis and BOM generation
