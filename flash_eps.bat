@echo off
:: Flash ESP32-C3 XIAO wireless DAP firmware.
:: Usage: flash_eps.bat [COMx]
::   If no port given, auto-detects the first ESP32-C3 USB serial device.
setlocal enabledelayedexpansion
set PYTHON=C:\Users\RWache\AppData\Local\Programs\Python\Python312\python.exe

set PORT=%~1
if "%PORT%"=="" (
    for /f %%P in ('"%PYTHON%" detect_port.py') do set PORT=%%P
    if "!PORT!"=="" (
        echo ERROR: No ESP32-C3 device found. Plug in the board or pass COMx manually.
        exit /b 1
    )
    echo Auto-detected port: !PORT!
)

"%PYTHON%" -m esptool -p !PORT! -b 460800 --chip esp32c3 write_flash 0x0 wireless_esp_dap_full.bin
