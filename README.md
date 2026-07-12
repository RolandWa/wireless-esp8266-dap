<p align="center"><img src="https://user-images.githubusercontent.com/17078589/120061980-49274280-c092-11eb-9916-4965f6c48388.png"/></p>

![image](https://user-images.githubusercontent.com/17078589/107857220-05ecef00-6e68-11eb-9fa0-506b32052dba.png)


[![Build Status](https://github.com/windowsair/wireless-esp8266-dap/actions/workflows/main.yml/badge.svg?branch=master)](https://github.com/windowsair/wireless-esp8266-dap/actions/workflows/main.yml) master　
[![Build Status](https://github.com/windowsair/wireless-esp8266-dap/actions/workflows/main.yml/badge.svg?branch=develop)](https://github.com/windowsair/wireless-esp8266-dap/actions/workflows/main.yml) develop

[![](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](https://github.com/windowsair/wireless-esp8266-dap/LICENSE)　[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-blue.svg?style=flat-square)](https://github.com/windowsair/wireless-esp8266-dap/pulls)　[![%e2%9d%a4](https://img.shields.io/badge/made%20with-%e2%9d%a4-ff69b4.svg?style=flat-square)](https://github.com/windowsair/wireless-esp8266-dap)

[中文](README_CN.md)

## Project Link (QR)

Scan to open the project repository:

![Project repository QR code](circuit_ESP32C3_Xiao/documentations/assets/github_repo_qr.png)

## Introduce

Wireless debugging with ***only one ESP Chip*** !

Realized by USBIP and CMSIS-DAP protocol stack.

> 👉 5m range, 100kb size firmware(Hex) earse and download test:

<p align="center"><img src="https://user-images.githubusercontent.com/17078589/120925694-4bca0d80-c70c-11eb-91b7-ffa54770faea.gif"/></p>

----

For Keil users, we now also support [elaphureLink](https://github.com/windowsair/elaphureLink). No need for usbip to start your wireless debugging!

## Feature

1. SoC Compatibility
    - [x] ESP8266/8285
    - [x] ESP32
    - [x] ESP32C3
    - [x] ESP32S3

2. Debug Communication Mode
    - [x] SWD
    - [x] JTAG

3. USB Communication Mode
    - [x] USB-HID
    - [x] WCID & WinUSB (Default)

4. Debug Trace (Uart)
    - [x] Uart TCP Bridge

5. More..
    - [x] SWD protocol based on SPI acceleration (Up to 40MHz)
    - [x] Support for [elaphureLink](https://github.com/windowsair/elaphureLink), fast Keil debug without drivers
    - [x] Support for [elaphure-dap.js](https://github.com/windowsair/elaphure-dap.js), online ARM Cortex-M firmware flash
    - [x] Support for [OpenOCD-elaphureLink](https://github.com/windowsair/openocd-elaphurelink), Get rid of USBIP!
    - [x] Support for OpenOCD/pyOCD
    - [x] ...



## Link your board

### WIFI

The default connected WIFI SSID is `DAP` or `OTA` , password `12345678`

Support for specifying multiple possible WAP. It can be added here: [wifi_configuration.h](main/wifi_configuration.h)

You can also specify your IP in the above file (We recommend using the static address binding feature of the router).

![WIFI](https://user-images.githubusercontent.com/17078589/118365659-517e7880-b5d0-11eb-9a5b-afe43348c2ba.png)


There is built-in ipv4 only mDNS server. You can access the device using `dap.local`.

> The mDNS in ESP8266 only supports ipv4.

![mDNS](https://user-images.githubusercontent.com/17078589/149659052-7b29533f-9660-4811-8125-f8f50490d762.png)

#### Static IP assignment (ESP32-C3 / ESP32-S3)

When `USE_STATIC_IP 1` is set in [main/wifi_configuration.h](main/wifi_configuration.h), the
device does **not** use a fixed static IP directly. Instead it uses a two-phase approach:

1. **Connect via DHCP** — the WiFi stack gets any IP from the router so the network is reachable.
2. **Probe for a free address** — starting from the configured `DAP_IP_ADDRESS` (default
   `192.168.137.123`), the firmware sends an ICMP ping and waits 400 ms.
   - No reply → address is free → DHCP is stopped and that address is assigned statically.
   - Reply received → address is taken → last octet is incremented and the next candidate is probed.
   - This repeats up to `.255`; if no free address is found, DHCP is kept.

**Default configuration** (`wifi_configuration.h`):

```
DAP_IP_ADDRESS  192.168.137.123   ← starting candidate
DAP_IP_GATEWAY  192.168.137.1
DAP_IP_NETMASK  255.255.255.0
```

**Behaviour with multiple devices (same firmware binary):**

```
Device A boots  →  pings .123  →  free  →  takes 192.168.137.123
Device B boots  →  pings .123  →  taken →  pings .124  →  free  →  takes 192.168.137.124
Device C boots  →  pings .123  →  taken →  .124 taken  →  .125  →  takes 192.168.137.125
```

Each device claims the next free address in the range automatically — no configuration change needed
per device. The address a device gets depends on **boot order**, not on a fixed assignment.

> **Note:** If two devices reboot simultaneously they may both ping `.123` before either has
> claimed it, and both attempt to take the same address. For a lab with multiple devices where
> stable, predictable IPs are required across reboots, use the NVS provisioning approach
> described in the [TODO / Future Work](#todo--future-work) section.

#### AP fallback mode

If all configured SSIDs fail (after 5 attempts each), the device switches to **Access Point mode**
using the second entry in `wifi_list` (`DAP` / `12345678` by default). The AP IP is always
`192.168.4.1`. The LED stays on to indicate AP mode is active.

### Debugger


<details>
<summary>ESP8266</summary>

| SWD            |        |
|----------------|--------|
| SWCLK          | GPIO14 |
| SWDIO          | GPIO13 |
| TVCC           | 3V3    |
| GND            | GND    |


--------------


| JTAG               |         |
|--------------------|---------|
| TCK                | GPIO14  |
| TMS                | GPIO13  |
| TDI                | GPIO4   |
| TDO                | GPIO16  |
| nTRST \(optional\) | GPIO0\* |
| nRESET             | GPIO5   |
| TVCC               | 3V3     |
| GND                | GND     |

--------------

| Other              |               |
|--------------------|---------------|
| LED\_WIFI\_STATUS  | GPIO15        |
| Tx                 | GPIO2         |
| Rx                 | GPIO3 (U0RXD) |

> Rx and Tx is used for uart bridge, not enabled by default.

</details>


<details>
<summary>ESP32</summary>

| SWD            |        |
|----------------|--------|
| SWCLK          | GPIO14 |
| SWDIO          | GPIO13 |
| TVCC           | 3V3    |
| GND            | GND    |


--------------


| JTAG               |         |
|--------------------|---------|
| TCK                | GPIO14  |
| TMS                | GPIO13  |
| TDI                | GPIO18  |
| TDO                | GPIO19  |
| nTRST \(optional\) | GPIO25  |
| nRESET             | GPIO26  |
| TVCC               | 3V3     |
| GND                | GND     |

--------------

| Other              |               |
|--------------------|---------------|
| LED\_WIFI\_STATUS  | GPIO27        |
| Tx                 | GPIO23        |
| Rx                 | GPIO22        |


> Rx and Tx is used for uart bridge, not enabled by default.


</details>


<details>
<summary>ESP32C3</summary>

| SWD            |        |
|----------------|--------|
| SWCLK          | GPIO6  |
| SWDIO          | GPIO7  |
| TVCC           | 3V3    |
| GND            | GND    |


--------------


| JTAG               |         |
|--------------------|---------|
| TCK                | GPIO6   |
| TMS                | GPIO7   |
| TDI                | GPIO9   |
| TDO                | GPIO8   |
| nTRST \(optional\) | GPIO4   |
| nRESET             | GPIO5   |
| TVCC               | 3V3     |
| GND                | GND     |

--------------

| Other              |               |
|--------------------|---------------|
| LED\_WIFI\_STATUS      | GPIO10        |
| VTarget Sense          | GPIO2 (ADC0)  |
| VTarget Control (PWM)  | GPIO3         |
| Tx                     | GPIO21        |
| Rx                     | GPIO20        |


> Rx and Tx is used for uart bridge, not enabled by default.
>
> **Note for XIAO-ESP32-C3:** UART pins are GPIO21 (D6/TX) and GPIO20 (D7/RX).

#### VTarget Vendor Commands (ESP32-C3 / ESP32-S3 only)

VTarget sensing and control use CMSIS-DAP Vendor Commands via the pyOCD API.

> **pyOCD API note:** `probe.vendor(index, data)` takes an **index** (0–31), not the raw command ID.
> pyOCD computes `cmd_id = 0x80 + index` internally and strips the echoed byte from the response.

|Function|pyOCD call|Command ID|Request|Response|
|--------|----------|----------|-------|--------|
|Read VTarget|`probe.vendor(1, [])`|`0x81`|—|`[LOW, HIGH]` voltage in mV, little-endian. `0xFFFF` = error|
|Set VTarget|`probe.vendor(2, [LOW, HIGH])`|`0x82`|voltage in mV (1250–5000), little-endian|`[0x00]` success · `[0x01]` out of range · `[0xFF]` error|

**Python example:**

```python
# Read VTarget voltage (mV)
response = probe.vendor(1, [])          # index=1 → command 0x81
voltage_mv = response[0] | (response[1] << 8)
print(f"VTarget: {voltage_mv} mV ({voltage_mv/1000:.3f} V)")

# Set VTarget to 3.3V
mv = 3300
probe.vendor(2, [mv & 0xFF, (mv >> 8) & 0xFF])  # index=2 → command 0x82
```

**Measured accuracy (ESP32-C3 XIAO, eFuse Vref calibration, 20-sample average):**

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

Max error: **+30 mV** at 3.46 V. Consistent positive offset bias (~10–30 mV) typical of ESP32-C3 ADC with 11 dB attenuation. All readings within ±1.5%.


</details>


<details>
<summary>ESP32S3</summary>

| SWD            |        |
|----------------|--------|
| SWCLK          | GPIO12 |
| SWDIO          | GPIO11 |
| TVCC           | 3V3    |
| GND            | GND    |


--------------


| JTAG               |        |
|--------------------|--------|
| TCK                | GPIO12 |
| TMS                | GPIO11 |
| TDI                | GPIO10 |
| TDO                | GPIO9  |
| nTRST \(optional\) | GPIO14 |
| nRESET             | GPIO13 |
| TVCC               | 3V3    |
| GND                | GND    |


</details>

----

## Hardware Reference

### ESP8266 Reference Design

Here we provide a simple example for reference:

![sch](https://user-images.githubusercontent.com/17078589/150284806-e6dff0fa-4fe1-4d86-ac45-3b657fbea6b7.png)

### ESP32-C3 XIAO Reference Design

A complete hardware design for the Seeed Studio XIAO ESP32-C3 module is available with the following features:

- **Multiple Debug Connector Options:**
  - **J3:** 10-pin Cortex Debug (1.27mm pitch, SMD) - Compact SMD connector
  - **J1:** 10-pin Cortex Debug (2.54mm pitch, IDC) - Standard through-hole
  - **J2:** 20-pin ARM Standard JTAG (2.54mm pitch, IDC) - Compatible with J-Link and other standard debuggers
- **VTarget Voltage Sensing** via 1/2 voltage divider on GPIO2 (supports 0-6.6V range)
- **UART Bridge** on GPIO20 (RX/D7) and GPIO21 (TX/D6)
- **3.3V Target Power Supply** option with MOSFET switch
- Full schematic and PCB layout in KiCAD format

**Schematic:** [circuit_ESP32C3_Xiao/ESP32C3_Xiao_wireless_DAP.kicad_sch](circuit_ESP32C3_Xiao/ESP32C3_Xiao_wireless_DAP.kicad_sch)

**Schematic PDF:** [circuit_ESP32C3_Xiao/documentations/ESP32C3_Xiao_wireless_DAP.pdf](circuit_ESP32C3_Xiao/documentations/ESP32C3_Xiao_wireless_DAP.pdf)

**Schematic Diagram:**

![ESP32C3 XIAO Schematic](circuit_ESP32C3_Xiao/documentations/ESP32C3_Xiao_wireless_DAP.svg)

**Additional Documentation:** [circuit_ESP32C3_Xiao/doc/](circuit_ESP32C3_Xiao/doc/) includes ARM JTAG connector pinouts and component datasheets

**PCBA Preview:**

![ESP32C3 XIAO PCBA ](circuit_ESP32C3_Xiao/documentations/ESP32C3_Xiao_wireless_DAP.png)

**Key Features:**
- Seeed Studio XIAO ESP32-C3 module
- Three connector options for maximum compatibility:
  - 1.27mm pitch for space-constrained applications
  - 2.54mm pitch 10-pin for standard probe compatibility
  - 2.54mm pitch 20-pin for J-Link and ARM standard debuggers
- Target voltage monitoring via DAP Vendor Command (0x81)
- Bi-directional UART bridge for SWO/RTT trace capture
- Level shifter compatible design (3.3V target support)
- Compatible with OpenOCD, pyOCD, Keil, and other standard ARM debugging tools

**Programmable VTarget Implementation:**

For ESP32-C3 XIAO designs, a programmable target voltage feature (1.25V-5V) is available using PWM-controlled voltage regulation. See the detailed implementation guide: [VTARGET_PWM_IMPLEMENTATION.md](circuit_ESP32C3_Xiao/documentations/VTARGET_PWM_IMPLEMENTATION.md)

***Alternatively, you can connect directly with wires as we gave at the beginning, without additional circuits.***

Additional hardware reference designs are available from contributors in the [circuit](circuit) folder.

------


## Build And Flash

You can build locally (WSL) or use GitHub Actions to build online and download the firmware.

### Build with GitHub Actions (Online)

Push to the branch — CI runs automatically and uploads firmware as build artifacts.
See [.github/workflows/main.yml](.github/workflows/main.yml).

### Build Locally — WSL / Windows (Recommended)

> Full details, troubleshooting, and environment notes: **[docs/build_wsl.md](docs/build_wsl.md)**

**Requirements:** WSL2 Ubuntu, Python 3.10 (installed automatically), ESP-IDF **v4.4.2**.

```bash
# Run inside the Ubuntu WSL terminal — first-time setup + build:
python3 build_WSL.py

# Subsequent builds (setup already done):
python3 build_WSL.py --build

# Clean rebuild:
python3 build_WSL.py --build --clean
```

The script installs all dependencies, clones ESP-IDF v4.4.2, builds the firmware, and
merges everything into `~/build_wireless_dap/wireless_esp_dap_full.bin`.

**Flash to device (Windows, COM12):**

```bat
flash_eps.bat
```

> **Always use ESP-IDF v4.4.2 exactly.** This codebase targets v4.4 APIs.
> Building with IDF v5+ requires significant source changes and is not supported.

### Build for ESP8266

<details>
<summary>ESP8266</summary>

The SDK is already included. Do not use other SDK versions.

```bash
# Build
python ./idf.py build
# Flash
python ./idf.py -p /dev/ttyS5 flash
```

</details>

> Pre-built firmware for quick evaluation: [Releases](https://github.com/windowsair/wireless-esp8266-dap/releases)


## Usage

1. Get USBIP project

- Windows: [usbip-win](https://github.com/cezanne/usbip-win) .
- Linux: Distributed as part of the Linux kernel, but we have not yet tested on Linux platform, and the following instructions are all under Windows platform.

2. Start ESP chip and connect it to the device to be debugged

3. Connect it with usbip:

```bash
# HID Mode only
# for pre-compiled version on SourceForge
# or usbip old version
.\usbip.exe -D -a <your-esp-device-ip-address>  1-1

# 👉 Recommend
# HID Mode Or WinUSB Mode
# for usbip-win 0.3.0 kmdf ude
.\usbip.exe attach_ude -r <your-esp-device-ip-address> -b 1-1

```

If all goes well, you should see your device connected.

![image](https://user-images.githubusercontent.com/17078589/107849548-f903d780-6e36-11eb-846f-3eaf0c0dc089.png)


Here, we use MDK for testing:

![target](https://user-images.githubusercontent.com/17078589/73830040-eb3c6f00-483e-11ea-85ee-c40b68a836b2.png)


------

## FAQ

### Keil is showing a "RDDI-DAP ERROR" or "SWD/JTAG Communication Failure" message.

1. Check your line connection. Don't forget the 3v3 connection cable.
2. Check that your network connection is stable.


### DAP is slow or often abnormal.

Note that this project is sensitive to the network environment. If you are using a hotspot on your computer, you can try using network analyzer such as wireshark to observe the status of your AP network. During the idle time, the network should stay silent, while in the working state, there should be no too much packet loss.

Some LAN broadcast packets can cause serious impact, including:
- DropBox LAN Sync
- Logitech Arx Control
- ...

For ESP8266, this is not far from UDP FLOOD...😰

It is also affected by the surrounding radio environment, your AP situation (some NICs have terrible AP performance), distance, etc.


----

## Document

### Speed Strategy

The maximum rate of esp8266 pure IO is about 2MHz.
When you select max clock, we will take the following actions:

- `clock < 2Mhz` : Similar to the clock speed you choose.
- `2MHz <= clock < 10MHz` : Use the fastest pure IO speed.
- `clock >= 10MHz` : SPI acceleration using 40MHz clock.

> Note that the most significant speed constraint of this project is still the TCP connection speed.


### For OpenOCD user

Connect directly over WiFi — **no USB cable, no USBIP kernel driver required**.

The recommended path is the elaphureLink OpenOCD (already installed at `c:\openocd\elaphurelink\`):

```bat
c:\openocd\elaphurelink\bin\openocd.exe ^
  -s c:\openocd\elaphurelink\share\openocd\scripts ^
  -f openocd/elaphurelink.cfg ^
  -f target/stm32f4x.cfg
```

Flash a `.bin` file to a target (example: Maxim MAX32672):

```bat
openocd\flash_max32672.bat firmware.bin
```

Or use OpenOCD commands directly:

```tcl
halt
flash write_image erase firmware.bin 0x10000000
verify_image firmware.bin 0x10000000
reset run
```

See **[docs/openocd.md](docs/openocd.md)** for all three connection paths (elaphureLink OpenOCD, Python bridge, pyOCD API) with full command examples.

### For pyOCD user

pyOCD 0.44+ can connect directly over WiFi via the elaphureLink TCP interface — **no USB driver or USBIP needed**:

```python
from tests.pyocd_elaphurelink import make_probe
from pyocd.core.session import Session

probe = make_probe("192.168.137.123")   # or "dap.local"
with Session(probe, target_override="your_target") as session:
    session.open()
    t = session.target
    t.halt()
    print(hex(t.read_core_register("pc")))
```

Standalone probe test (checks connection without a target MCU attached):

```bat
python tests/pyocd_elaphurelink.py --ip 192.168.137.123
```

### System OTA

When this project is updated, you can update the firmware over the air.

Visit the following website for OTA operations: [online OTA](http://corsacota.surge.sh/?address=dap.local:3241)


For most devices, you don't need to care about flash size. However, improper setting of the flash size may cause the OTA to fail. In this case, please change the flash size with `idf.py menuconfig`, or modify `sdkconfig`:

```
# Choose a flash size.
CONFIG_ESPTOOLPY_FLASHSIZE_1MB=y
CONFIG_ESPTOOLPY_FLASHSIZE_2MB=y
CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y
CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y
CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y

# Then set a flash size
CONFIG_ESPTOOLPY_FLASHSIZE="2MB"
```

If flash size is 2MB, the sdkconfig file might look like this:

```
CONFIG_ESPTOOLPY_FLASHSIZE_2MB=y
CONFIG_ESPTOOLPY_FLASHSIZE="2MB"
```


For devices with 1MB flash size such as ESP8285, the following changes must be made:

```
CONFIG_PARTITION_TABLE_FILENAME="partitions_two_ota.1MB.csv"
CONFIG_ESPTOOLPY_FLASHSIZE_1MB=y
CONFIG_ESPTOOLPY_FLASHSIZE="1MB"
CONFIG_ESP8266_BOOT_COPY_APP=y
```

The flash size of the board can be checked with the esptool.py tool:

```bash
esptool.py -p (PORT) flash_id
```

### Uart TCP Bridge

Bridges **TCP port 1234 ↔ UART1** (GPIO21 TX / GPIO20 RX on ESP32-C3 XIAO).
Lets any PC application talk to a serial device wired to those pins — over WiFi,
no USB-serial adapter needed.

```text
PC TCP client (port 1234)
  ↕  WiFi
ESP32-C3
  ↕  GPIO21 TX / GPIO20 RX
Target MCU serial / AT modem / SWO trace
```

![uart_tcp_bridge](https://user-images.githubusercontent.com/17078589/150290065-05173965-8849-4452-ab7e-ec7649f46620.jpg)

**Supported baud rates:** 9600 · 14400 · 19200 · 28800 · 38400 · 56000 · 57600 · 115200

**Enable** in [main/wifi_configuration.h](main/wifi_configuration.h):

```c
#define USE_UART_BRIDGE      1
#define UART_BRIDGE_PORT     1234
#define UART_BRIDGE_BAUDRATE 115200
```

**Connect** from Windows — pick any:

- **Python terminal:** `python tests/uart_bridge.py --baud 115200`
- **PuTTY:** see step-by-step below
- **Netcat:** `ncat dap.local 1234`

**Baud-rate negotiation:** the very first TCP packet, if it is a plain decimal number
(e.g. `"115200"`), reconfigures the UART to that rate before forwarding begins.
Each new baud rate requires a new TCP connection.

#### PuTTY — step by step

1. Open **PuTTY**.
2. Set **Connection type** → **Raw** (not SSH, not Telnet).
3. **Host Name:** `dap.local` (or `192.168.137.123`)
4. **Port:** `1234`
5. *(Optional)* Go to **Terminal → Local echo → Force on** so you can see what you type.
6. Click **Open**.
7. **Immediately type the baud rate** (e.g. `115200`) and press **Enter** — this is the
   baud-rate negotiation packet. Do this before sending any other data.
8. The UART is now running at that rate. Type commands / read responses normally.

> **Tip:** Save the session (Session → Saved Sessions → "DAP-UART") to avoid
> re-entering the host and port each time. The baud rate still needs to be sent
> manually after each connect.

**Loopback test** (GPIO20 shorted to GPIO21 — verifies all baud rates):

```bat
python tests/uart_bridge.py --loopback --all-bauds
```

Full details, use cases (SWO trace, AT commands, target console), and API reference:
**[docs/uart_bridge.md](docs/uart_bridge.md)**


### elaphure-dap.js

For the ESP8266, this feature is turned off by default. You can turn it on in menuconfig:

```
CONFIG_USE_WEBSOCKET_DAP=y
```

----

## TODO / Future Work

### Hardware — not yet assembled / tested

- [ ] **VTarget PWM circuit** — assemble AP1117-ADJ + MOSFET (Q1, R4, R5, R6, R7, C2, C3) on PCB;
  firmware (GPIO3 LEDC) is ready and confirmed sending commands correctly
- [ ] **VTarget calibration** — after hardware assembly, measure actual output with a multimeter at
  1.25 V, 1.8 V, 2.5 V, 3.3 V, 5.0 V and compare against requested voltage.
  If deviation > ~5%, replace the linear interpolation in `vtarget_set_voltage()` with a
  calibration lookup table (see `main/vtarget_pwm.c` and `docs/vtarget.md`)

### Testing — confirmed working in software, not yet exercised on real hardware

- [ ] **OpenOCD with a real SWD target** — `dap info` confirmed; run full debug session
  (e.g. STM32F4 or MAX32672) via `openocd/elaphurelink.cfg`
- [ ] **MAX32672 flash** — run `openocd/flash_max32672.bat` against real hardware
- [ ] **pyOCD with a real SWD target** — `make_probe()` handshake confirmed; test actual
  register read/write with a target connected to the SWD pins
- [ ] **UART bridge loopback at multiple baud rates** — 115200 confirmed; run
  `python tests/uart_bridge.py --loopback --all-bauds` with a loopback jumper on GPIO20/21
- [ ] **VTarget ADC accuracy** — cross-check 5216 mV reading against a calibrated meter

### Firmware — known issues from code review

- [ ] **`uart_bridge.c` — `uart_read_bytes` return type**: result (int, can be -1 on error)
  stored in `size_t uart_buf_len`; on error -1 becomes SIZE_MAX and is passed to
  `netconn_write` → buffer overread. Fix: use a separate `int n = uart_read_bytes(...);
  if (n > 0) netconn_write(..., (size_t)n, ...)`.
- [ ] **`uart_bridge.c` — `netconn_write` error ignored**: failed write (remote disconnect)
  leaves `is_conn_valid = true`; task loops retrying forever. Fix: check return value and
  clear `is_conn_valid` on `ERR_CLSD` / `ERR_RST`.
- [ ] **`uart_bridge.c` — double queue create**: `uart_bridge_init()` and `uart_bridge_task()`
  both call `xQueueCreate` for `uart_server_events`, leaking the first queue.
  Fix: remove the `xQueueCreate` call from `uart_bridge_init()`.
- [ ] **TCP keepalive** — no keepalive on the elaphureLink or USBIP sockets; a stale
  connection keeps the server blocked until a new client connects.

### Future features

- [ ] **xPack OpenOCD TCP bridge** (`openocd/cmsis_dap_tcp_bridge.py`) — packet framing
  for the xPack `cmsis-dap backend tcp` mode not yet matched; Path 3 is WIP
- [ ] **WebSocket DAP** — firmware advertises the WebSocket protocol variant; no client
  or test exists yet
- [ ] **SWO / trace capture** — firmware advertises SWO Manchester; no capture client tested

----

## Develop

Check other branches to know the latest development progress.

Any kind of contribute is welcome, including but not limited to new features, ideas about circuits, documentation.

You can also ask questions to make this project better.

- [New issues](https://github.com/windowsair/wireless-esp8266-dap/issues)
- [New pull](https://github.com/windowsair/wireless-esp8266-dap/pulls)


### Issue

2020.12.1

TCP transmission speed needs to be further improved.

2020.11.11

Winusb is now available, but it is very slow.


2020.2.4

Due to the limitation of USB-HID (I'm not sure if this is a problem with USBIP or Windows), now each URB packet can only reach 255 bytes (About 1MBps bandwidth), which has not reached the upper limit of ESP8266 transmission bandwidth.

I now have an idea to construct a Man-in-the-middle between the two to forward traffic, thereby increasing the bandwidth of each transmission.

2020.1.31

At present, the adaptation to WCID, WinUSB, etc. has all been completed. However, when transmitting data on the endpoint, we received an error message from USBIP. This is most likely a problem with the USBIP project itself.

Due to the completeness of the USBIP protocol document, we have not yet understood its role in the Bulk transmission process, which may also lead to errors in subsequent processes.

We will continue to try to make it work on USB HID. Once the USBIP problem is solved, we will immediately transfer it to work on WinUSB


------

## Credit


Credits to the following project, people and organizations:

> - https://github.com/thevoidnn/esp8266-wifi-cmsis-dap for adapter firmware based on CMSIS-DAP v1.0
> - https://github.com/ARM-software/CMSIS_5 for CMSIS
> - https://github.com/cezanne/usbip-win for usbip windows


- [@HeavenSpree](https://www.github.com/HeavenSpree)
- [@Zy19930907](https://www.github.com/Zy19930907)
- [@caiguang1997](https://www.github.com/caiguang1997)
- [@ZhuYanzhen1](https://www.github.com/ZhuYanzhen1)


## License

[MIT LICENSE](LICENSE)

## References
- Project upstream (windowsair/wireless-esp8266-dap): https://github.com/windowsair/wireless-esp8266-dap
- CMSIS (ARM): https://github.com/ARM-software/CMSIS_5
- ESP-IDF documentation: https://docs.espressif.com/projects/esp-idf/en/latest/
- usbip-win (Windows USBIP client): https://github.com/cezanne/usbip-win

