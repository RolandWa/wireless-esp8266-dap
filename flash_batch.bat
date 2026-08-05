@echo off
:: Batch flash multiple XIAO ESP32-C3 boards one by one.
:: Plug in a device, press ENTER, it flashes, then repeat for the next.
::
:: Usage: flash_batch.bat [total_count]
::   total_count: how many boards to flash (default 7)

setlocal enabledelayedexpansion
set PYTHON=C:\Users\RWache\AppData\Local\Programs\Python\Python312\python.exe
set TOTAL=%~1
if "%TOTAL%"=="" set TOTAL=7

echo ============================================================
echo  Batch flash ESP32-C3 XIAO wireless DAP
echo  Firmware : wireless_esp_dap_full.bin
echo  Boards   : %TOTAL%
echo ============================================================
echo.

set /a PASS=0
set /a FAIL=0

:NEXT_BOARD
set /a BOARD=PASS+FAIL+1
if %BOARD% GTR %TOTAL% goto DONE

echo ------------------------------------------------------------
echo  Board %BOARD% of %TOTAL%   (passed: %PASS%  failed: %FAIL%)
echo ------------------------------------------------------------
echo  1. Plug in the board via USB
echo  2. Wait for Windows to assign a COM port
echo  3. Press ENTER to auto-detect and flash
echo     (or type a port manually, e.g. COM14, then ENTER)
echo.
set /p USER_PORT=  Port [auto]:

if "%USER_PORT%"=="" (
    echo  Detecting COM port...
    for /f %%P in ('"%PYTHON%" detect_port.py') do set PORT=%%P
    if "!PORT!"=="" (
        echo  ERROR: No ESP32-C3 device found. Plug it in and press ENTER to retry.
        set /p DUMMY=  Press ENTER...
        goto NEXT_BOARD
    )
) else (
    set PORT=!USER_PORT!
)

echo  Flashing !PORT! ...
"%PYTHON%" -m esptool -p !PORT! -b 460800 --chip esp32c3 write_flash 0x0 wireless_esp_dap_full.bin

if !ERRORLEVEL! EQU 0 (
    set /a PASS=PASS+1
    echo.
    echo  [OK] Board %BOARD% flashed successfully on !PORT!
) else (
    set /a FAIL=FAIL+1
    echo.
    echo  [FAIL] Board %BOARD% failed on !PORT!
)

echo.
goto NEXT_BOARD

:DONE
echo ============================================================
echo  Done!  Passed: %PASS%  Failed: %FAIL%  Total: %TOTAL%
echo ============================================================
if %FAIL% GTR 0 (
    echo  WARNING: %FAIL% board(s) failed. Re-flash them manually:
    echo    flash_eps.bat COMxx
)
pause
