# WSL Build Guide — wireless-esp8266-dap (ESP32-C3)

Automated local build that exactly replicates the GitHub CI environment.

## Requirements

| Item | Version | Notes |
|------|---------|-------|
| Windows 10/11 | any | WSL2 required |
| WSL2 — Ubuntu | 22.04 / 24.04 / 26.04 | other distros untested |
| ESP-IDF | **v4.4.2 exactly** | newer IDF breaks the codebase |
| Python (for IDF) | **3.10** | gevent 1.5.0 in IDF requirements fails on 3.11+ |
| esptool | v4.6.2 | matches CI merge step |
| Target | esp32c3 | Seeed XIAO ESP32-C3 |

> **Do not use a newer IDF version.** The source code targets IDF v4.4.2 APIs.  
> Adapting to newer IDF requires changes across `spi_switch.c`, `gpio_common.h`,  
> `DAP_vendor.c` and several other files — this is intentionally avoided.

---

## First-Time Setup

Open your **Ubuntu WSL terminal** and run:

```bash
python3 "/mnt/c/Users/<YourName>/path/to/wireless-esp8266-dap/build_WSL.py"
```

The script runs six steps automatically:

| Step | Action | Duration |
|------|--------|----------|
| 1/6 | Install apt packages | ~1 min |
| 2/6 | Install Python 3.10 via deadsnakes PPA | ~1 min |
| 3/6 | Clone ESP-IDF v4.4.2 + submodules | ~5–10 min |
| 4/6 | Install IDF tools for esp32c3 | ~3–5 min |
| 5/6 | Clone esptool v4.6.2 | ~30 s |
| 6/6 | Build firmware + merge binaries | ~2–4 min |

Each step is skipped automatically on subsequent runs if already completed.

---

## Subsequent Builds

```bash
# Build only (skip all setup steps)
python3 build_WSL.py --build

# Clean build (remove build directory first)
python3 build_WSL.py --build --clean
```

---

## Output Binaries

After a successful build, two files are created in `~/build_wireless_dap/`:

| File | Use |
|------|-----|
| `wireless_esp_dap_full.bin` | Flash this — contains bootloader + partition table + app merged at correct offsets |
| `wireless_esp_dap_app.bin` | App only (for OTA updates) |

Flash offsets (esp32c3):

| Binary | Offset |
|--------|--------|
| bootloader | `0x0` |
| partition table | `0x8000` |
| application | `0x10000` |

---

## Flashing (Windows)

Connect the XIAO ESP32-C3 via USB (COM12 by default).

```bat
flash_eps.bat
```

Or manually:

```bat
python -m esptool -p COM12 -b 460800 --chip esp32c3 write_flash 0x0 wireless_esp_dap_full.bin
```

To find the binary from Windows Explorer:

```
\\wsl$\Ubuntu\home\<username>\build_wireless_dap\wireless_esp_dap_full.bin
```

---

## How Python 3.10 Is Handled

Ubuntu 24.04+ ships Python 3.12–3.14 as the system Python. IDF v4.4.2's
`requirements.txt` pulls in `gevent==1.5.0` (via `gdbgui`), which uses Cython
extensions incompatible with Python 3.11+.

The script installs Python 3.10 from the **deadsnakes PPA** and creates a PATH
shim (`~/idf_python_shim/`) so IDF's `detect_python.sh` finds `python3.10`
instead of the system `python3`. The IDF virtual environment is created at:

```
~/.espressif/python_env/idf4.4_py3.10_env/
```

---

## Common Errors and Fixes

### `KeyError: 'idfSelectedId'`
Previous failed install left a partial `~/.espressif/idf-env.json`.  
**Fix:** The script removes it automatically before each install attempt.  
Manual fix: `rm ~/.espressif/idf-env.json`

### `gevent` / Cython compilation failure
Python version is too new (3.11+). IDF uses Python 3.14 from the system.  
**Fix:** The script installs Python 3.10 and shims the PATH. If it still fails:
```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3.10-dev python3.10-distutils
```
Then delete the stamp file and retry:
```bash
rm ~/esp/esp-idf-v4.4.2/.installed_esp32c3
python3 build_WSL.py
```

### `sudo: timed out` when running from PowerShell
`sudo` cannot prompt for a password in non-interactive WSL sessions.  
**Fix:** Run the script directly inside the Ubuntu terminal app, not from PowerShell.

### `Operation not permitted` during CMake
CMake cannot perform some operations on Windows NTFS via `/mnt/c/`.  
**Fix:** The script always uses `~/build_wireless_dap` (Linux native filesystem) as the build directory. Never use `-B` pointing to `/mnt/c/`.

### `install.sh: No such file or directory` for `detect_python.sh`
Caused by sourcing `install.sh` (`. install.sh`) instead of executing it — `BASH_SOURCE[0]` is wrong when sourced.  
**Fix:** Already handled — the script calls `bash install.sh` as a subprocess.

---

## Environment Summary (matches GitHub CI exactly)

```yaml
# From .github/workflows/main.yml
- uses: espressif/esp-idf-ci-action@v1
  with:
    esp_idf_version: v4.4.2
    target: esp32c3

# esptool merge offsets for esp32c3:
merge_bin -o wireless_esp_dap_full.bin
  0x0     bootloader/bootloader.bin
  0x8000  partition_table/partition-table.bin
  0x10000 wireless_esp_dap.bin
```

---

## WiFi Configuration

Edit `main/wifi_configuration.h` before building (this file is git-ignored — never commit it):

```c
static struct { const char *ssid; const char *password; } wifi_list[] = {
    {.ssid = "YourSSID",  .password = "YourPassword"},
    {.ssid = "FallbackAP", .password = "12345678"},  // fallback AP mode
};

#define USE_STATIC_IP  1
#define DAP_IP_ADDRESS 192, 168, 137, 123   // default — auto-increments if taken
#define DAP_IP_GATEWAY 192, 168, 137, 1
#define DAP_IP_NETMASK 255, 255, 255, 0
```

The firmware connects with DHCP first, probes the configured static IP with ICMP,
increments the last octet (`.123` → `.124` → … → `.255`) until a free address is
found, then locks it in as static. The chosen IP is printed on serial (COM12, 115200 baud).

### Serial Debug Commands (115200 baud, COM12)

| Key | Action |
|-----|--------|
| `v` | Read VTref voltage |
| `s` | Print full status (IP, RSSI, VTref, free heap) |
| `h` | Print help |
| `r` | Reboot |
