# Debug Connector Pinout Comparison

## Overview
This document compares the **ESP32-C3 XIAO wireless DAP** connector pinouts against industry-standard debuggers and debug interfaces.

---

## 10-Pin Cortex Debug Connector (2×5, 1.27mm/2.54mm pitch)

### Standard ARM Cortex Debug 10-Pin (J1/J3 Reference)
**Used by:** J-Link, CMSIS-DAP, LPC-Link2, ULINK, PE Micro, SEGGER, Keil, most modern ARM debuggers

```
┌─────────────────────────────────────┐
│  Pin Layout (Top View, Key on Pin 7)│
│                                      │
│  1 VTref    ●●  2 SWDIO/TMS         │
│  3 GND      ●●  4 SWCLK/TCK         │
│  5 GND      ●●  6 SWO/TDO           │
│  7 KEY/NC   ●▯  8 TDI/NC            │
│  9 GND      ●●  10 nRESET           │
└─────────────────────────────────────┘
```

**Standard Pinout (ARM Cortex Debug Specification):**
| Pin | Signal     | Direction | Description                    | SWD Mode  | JTAG Mode |
|-----|------------|-----------|--------------------------------|-----------|-----------|
| 1   | VTref      | Input     | Target reference voltage       | Required  | Required  |
| 2   | SWDIO/TMS  | I/O       | Serial data / Test mode select | SWDIO     | TMS       |
| 3   | GND        | Power     | Ground                         | Required  | Required  |
| 4   | SWCLK/TCK  | Output    | Serial clock / Test clock      | SWCLK     | TCK       |
| 5   | GND        | Power     | Ground                         | Required  | Required  |
| 6   | SWO/TDO    | Input     | Serial wire output / Test data out | SWO   | TDO       |
| 7   | KEY        | -         | Not connected (keying pin)     | N/C       | N/C       |
| 8   | TDI        | Output    | Test data input (JTAG only)    | N/C       | TDI       |
| 9   | GND        | Power     | Ground                         | Required  | Required  |
| 10  | nRESET     | I/O       | Target reset (active low)      | Required  | Required  |

---

### ESP32-C3 XIAO Wireless DAP 10-Pin (J1/J3 Actual)
**NON-STANDARD - Custom Pinout**

```
┌─────────────────────────────────────┐
│  Pin Layout (Top View)               │
│                                      │
│  1 VTref    ●●  2 TMS/SWDIO         │
│  3 GND      ●●  4 TCK/SWCLK         │
│  5 UART_TX  ●●  6 TDO/SWO           │
│  7 UART_RX  ●●  8 TDI               │
│  9 VTarget  ●●  10 nRST             │
└─────────────────────────────────────┘
```

**Custom Pinout:**
| Pin | Signal     | Direction | Description                    | Standard Pin | Deviation |
|-----|------------|-----------|--------------------------------|--------------|-----------|
| 1   | VTref      | Input     | Target reference voltage sense | Same         | ✅ Standard |
| 2   | TMS/SWDIO  | I/O       | Test mode / Serial data        | Same         | ✅ Standard |
| 3   | GND        | Power     | Ground                         | Same         | ✅ Standard |
| 4   | TCK/SWCLK  | Output    | Test clock / Serial clock      | Same         | ✅ Standard |
| 5   | **UART_TX**| Output    | UART transmit for SWO bridge   | **GND**      | ⚠️ **CUSTOM** |
| 6   | TDO/SWO    | Input     | Test data out / Serial wire out| Same         | ✅ Standard |
| 7   | **UART_RX**| Input     | UART receive for RTT bridge    | **KEY/NC**   | ⚠️ **CUSTOM** |
| 8   | TDI        | Output    | Test data input                | Same         | ✅ Standard |
| 9   | **VTarget**| Output    | Programmable 1.25-5V supply    | **GND**      | ⚠️ **CUSTOM** |
| 10  | nRST       | I/O       | Target reset (active low)      | Same         | ✅ Standard |

**Critical Differences:**
- ⚠️ **Pin 5**: UART_TX instead of GND - **NOT compatible with standard debuggers**
- ⚠️ **Pin 7**: UART_RX instead of KEY - **Physically incompatible** (standard has plastic key)
- ⚠️ **Pin 9**: VTarget power supply instead of GND - **May damage standard debuggers if connected!**

**Compatibility Assessment:**
- ❌ **NOT plug-compatible** with standard 10-pin Cortex Debug cables
- ❌ **Risk of damage** to standard debuggers (VTarget on pin 9)
- ⚠️ **Signal-level compatible** on pins 1-4, 6, 8, 10 (core debug signals)
- ✅ **SWD/JTAG protocols** are standard CMSIS-DAP compliant

---

## 20-Pin ARM JTAG Connector (2×10, 2.54mm pitch)

### Standard ARM JTAG 20-Pin (ARM IHI 0031 Specification)
**Used by:** J-Link (20-pin variant), ULINK, early ARM debuggers, legacy systems

```
┌───────────────────────────────────────────┐
│  Pin Layout (Top View, Pin 1 marked)      │
│                                            │
│  1 VTref    ●●  2 NC/VTref                │
│  3 nTRST    ●●  4 GND                     │
│  5 TDI      ●●  6 GND                     │
│  7 TMS      ●●  8 GND                     │
│  9 TCK      ●●  10 GND                    │
│  11 RTCK    ●●  12 GND                    │
│  13 TDO     ●●  14 GND                    │
│  15 nRESET  ●●  16 GND                    │
│  17 NC      ●●  18 GND                    │
│  19 NC/5V   ●●  20 GND                    │
└───────────────────────────────────────────┘
```

**Standard Pinout (ARM IHI 0031):**
| Pin | Signal     | Direction | Description                       | Notes               |
|-----|------------|-----------|-----------------------------------|---------------------|
| 1   | VTref      | Input     | Target reference voltage          | Required            |
| 2   | NC/VTref   | -         | Not connected or VTref duplicate  | Varies by vendor    |
| 3   | nTRST      | Output    | Test reset (JTAG, active low)     | Optional            |
| 4   | GND        | Power     | Ground                            | Required            |
| 5   | TDI        | Output    | Test data input                   | JTAG signal         |
| 6   | GND        | Power     | Ground                            | Required            |
| 7   | TMS        | Output    | Test mode select                  | JTAG signal         |
| 8   | GND        | Power     | Ground                            | Required            |
| 9   | TCK        | Output    | Test clock                        | JTAG signal         |
| 10  | GND        | Power     | Ground                            | Required            |
| 11  | RTCK       | Input     | Return test clock (adaptive)      | Optional, often GND |
| 12  | GND        | Power     | Ground                            | Required            |
| 13  | TDO        | Input     | Test data output                  | JTAG signal         |
| 14  | GND        | Power     | Ground                            | Required            |
| 15  | nRESET     | I/O       | Target reset (active low)         | Required            |
| 16  | GND        | Power     | Ground                            | Required            |
| 17  | NC         | -         | Not connected (reserved)          | Key pin on some     |
| 18  | GND        | Power     | Ground                            | Required            |
| 19  | NC/5V      | -         | Not connected or +5V supply       | Deprecated          |
| 20  | GND        | Power     | Ground                            | Required            |

---

### ESP32-C3 XIAO Wireless DAP 20-Pin (J2 Actual)
**CUSTOM VARIANT - Non-standard pinout**

```
┌───────────────────────────────────────────┐
│  Pin Layout (Top View, Pin 1 marked)      │
│                                            │
│  1 VTref    ●●  2 VTref                   │
│  3 nTRST    ●●  4 GND                     │
│  5 TDI      ●●  6 GND                     │
│  7 TMS      ●●  8 GND                     │
│  9 TCK      ●●  10 GND                    │
│  11 UART_TX ●●  12 GND                    │
│  13 TDO     ●●  14 GND                    │
│  15 nRST    ●●  16 GND                    │
│  17 UART_RX ●●  18 GND                    │
│  19 VTarget ●●  20 VTref                  │
└───────────────────────────────────────────┘
```

**Custom Pinout:**
| Pin | Signal      | Direction | Description                    | Standard Pin | Deviation |
|-----|-------------|-----------|--------------------------------|--------------|-----------|
| 1   | VTref       | Input     | Target reference voltage       | Same         | ✅ Standard |
| 2   | VTref       | Input     | VTref duplicate (sense)        | NC/VTref     | ✅ Acceptable |
| 3   | nTRST       | Output    | Test reset                     | Same         | ✅ Standard |
| 4   | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 5   | TDI         | Output    | Test data input                | Same         | ✅ Standard |
| 6   | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 7   | TMS         | Output    | Test mode select               | Same         | ✅ Standard |
| 8   | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 9   | TCK         | Output    | Test clock                     | Same         | ✅ Standard |
| 10  | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 11  | **UART_TX** | Output    | UART transmit (SWO bridge)     | **RTCK/GND** | ⚠️ **CUSTOM** |
| 12  | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 13  | TDO         | Input     | Test data output               | Same         | ✅ Standard |
| 14  | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 15  | nRST        | I/O       | Target reset                   | Same         | ✅ Standard |
| 16  | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 17  | **UART_RX** | Input     | UART receive (RTT bridge)      | **NC/KEY**   | ⚠️ **CUSTOM** |
| 18  | GND         | Power     | Ground                         | Same         | ✅ Standard |
| 19  | **VTarget** | Output    | Programmable 1.25-5V supply    | **NC/5V**    | ⚠️ **CUSTOM** |
| 20  | **VTref**   | Input     | VTref sense                    | **GND**      | ⚠️ **CUSTOM** |

**Critical Differences:**
- ⚠️ **Pin 11**: UART_TX instead of RTCK - **RTCK not supported** (adaptive clocking disabled)
- ⚠️ **Pin 17**: UART_RX instead of NC - **May conflict** if standard cable uses pin 17
- ⚠️ **Pin 19**: VTarget power supply instead of NC/5V - **Power conflict risk!**
- ⚠️ **Pin 20**: VTref instead of GND - **Ground missing** on last pin

**Compatibility Assessment:**
- ⚠️ **Partially compatible** with standard 20-pin JTAG cables for basic JTAG operation
- ❌ **NOT safe for standard debuggers** - VTarget on pin 19 may cause damage
- ❌ **RTCK not available** - no adaptive clock support (pin 11 repurposed)
- ✅ **Core JTAG signals** (pins 3-9, 13, 15) match standard
- ⚠️ **Missing final ground** (pin 20) - may cause signal integrity issues

---

## Debugger-Specific Compatibility Matrix

### SEGGER J-Link
**10-pin Cortex Debug (J-Link Compact):**
- ❌ **Incompatible** - VTarget on pin 9 will short to J-Link's GND driver
- ❌ **Mechanical keying conflict** - Pin 7 has physical key on J-Link cables
- ⚠️ **Electrical damage risk** - Do not connect directly

**20-pin ARM JTAG (J-Link Standard):**
- ⚠️ **Limited compatibility** - Core JTAG/SWD signals compatible (pins 1-16)
- ❌ **VTarget conflict** - Pin 19 may conflict with J-Link's 5V sense
- ❌ **No RTCK support** - Adaptive clocking unavailable
- ⚠️ **Custom adapter required** for safe connection

### ARM/Keil ULINK
**10-pin Cortex Debug:**
- ❌ **Incompatible** - Same issues as J-Link 10-pin
- ❌ **VTarget conflict** - ULINK expects GND on pin 9

**20-pin ARM JTAG:**
- ⚠️ **Basic JTAG/SWD functional** - With adapter for pins 11, 17, 19, 20
- ❌ **No RTCK** - High-speed JTAG may be unstable

### CMSIS-DAP Standard Probes
**10-pin:**
- ❌ **Incompatible** - CMSIS-DAP spec requires GND on pins 5, 9
- ⚠️ **Protocol compatible** - Wireless DAP implements CMSIS-DAP protocol correctly

**20-pin:**
- ⚠️ **Depends on implementation** - Standard CMSIS-DAP probes vary widely

### OpenOCD / Other Software
- ✅ **Protocol compatible** - CMSIS-DAP protocol is standard
- ❌ **Physical incompatibility** - Cable adapters required
- ⚠️ **UART bridge not supported** by standard tools (custom firmware feature)

---

## Additional Standard Connector Types (Not Used in This Design)

### 14-Pin Cortex Debug + ETM (1.27mm)
Used for high-speed trace (ETM) in addition to standard debug.
**Not implemented** in ESP32-C3 XIAO design.

### 20-Pin Cortex Debug + ETM (1.27mm)
Full-featured trace connector with SWD/JTAG + 4-bit ETM.
**Not available** - ESP32-C3 lacks ETM capability.

### Tag-Connect TC2030/TC2050
Pogo-pin connectors for production programming (no installed connector).
**Not implemented** - through-hole connectors used instead.

---

## Custom Features Justification

### Why Deviate from Standards?

#### 1. **VTarget on Pin 9/19 (10-pin/20-pin)**
**Purpose:** Provides programmable target power (1.25V-5.0V) directly from debugger
**Benefit:** 
- No external power supply needed for target device
- Automatic voltage level matching for safe debugging
- Simplifies bench setup for prototyping

**Trade-off:** Incompatible with standard debugger cables (they expect GND)

#### 2. **UART Bridge on Pins 5/7 (10-pin) and 11/17 (20-pin)**
**Purpose:** Integrated SWO/RTT trace capture via UART
**Benefit:**
- No additional USB-to-Serial adapter required
- Direct WiFi streaming of trace data
- Simplified cable management

**Trade-off:** Conflicts with standard pin assignments (GND, KEY, RTCK)

#### 3. **VTref on Pin 20 (20-pin)**
**Purpose:** Dedicated VTref sense line for voltage monitoring
**Benefit:**
- Accurate target voltage measurement
- Redundant sensing with pin 1

**Trade-off:** Missing final ground pin (pin 20 normally GND)

---

## Recommended Usage

### ✅ **Safe Configurations:**
1. **Use wireless DAP as standalone unit** - No cable adapters needed
2. **Connect to target using standard SWD/JTAG signals only** - Avoid VTarget pins
3. **Custom target boards** designed specifically for this pinout

### ⚠️ **Requires Caution:**
1. **Adapting to standard 20-pin JTAG** - Isolate pins 11, 17, 19, 20
2. **Using VTarget feature** - Ensure target device compatible with voltage range

### ❌ **DO NOT:**
1. **Connect standard 10-pin Cortex Debug cable directly** - Risk of electrical damage
2. **Use with commercial debuggers (J-Link, ULINK)** - Pinout mismatch will cause faults
3. **Assume plug-and-play compatibility** - This is a **custom debug interface**

---

## Adapter Design Recommendations

If interfacing with standard debuggers is required, design a **pinout adapter PCB** with:

### 10-Pin to Standard Cortex Debug:
```
ESP32-C3 Pin → Standard Pin   Action
Pin 5 (TX)   → (Disconnect)   Leave floating
Pin 7 (RX)   → (Disconnect)   Leave floating  
Pin 9 (VT)   → (Disconnect)   **CRITICAL - isolate!**
All others   → Same pin        Direct connection
```

### 20-Pin to Standard ARM JTAG:
```
ESP32-C3 Pin → Standard Pin   Action
Pin 11 (TX)  → Pin 11 (GND)   Pull to GND with 10kΩ
Pin 17 (RX)  → Pin 17 (GND)   Pull to GND with 10kΩ
Pin 19 (VT)  → (Disconnect)   **CRITICAL - isolate!**
Pin 20 (VTr) → Pin 20 (GND)   Connect to GND
```

---

## Conclusion

The **ESP32-C3 XIAO wireless DAP** implements a **custom debug connector pinout** that:
- ✅ Maintains CMSIS-DAP protocol compatibility
- ✅ Provides unique features (programmable VTarget, UART bridge)
- ❌ **NOT physically compatible** with standard debug cables
- ⚠️ **Requires custom cabling or adapter PCBs** for standard debugger interfacing

**Key Takeaway:** This is a **purpose-built wireless debug probe** with proprietary connector pinouts. It is **not intended as a drop-in replacement** for standard J-Link/ULINK/CMSIS-DAP hardware.

**For production use:** Design target boards with matching custom connector pinouts, or use adapter PCBs to interface with standard equipment.

---

## References
- ARM IHI 0031C: CoreSight Connectors Specification
- SEGGER J-Link User Guide (UM08001)
- ARM Cortex Debug Connector Specification
- CMSIS-DAP Documentation (ARM)
- Keil ULINK Debug Adapters Guide
