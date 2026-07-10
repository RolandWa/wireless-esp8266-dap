@echo off
REM ============================================================
REM  Flash MAX32672 via wireless-esp8266-dap (elaphureLink)
REM
REM  Usage:
REM    flash_max32672.bat firmware.bin
REM    flash_max32672.bat firmware.bin 0x10010000
REM
REM  Default load address: 0x10000000 (MAX32672 flash base)
REM ============================================================
setlocal

set OPENOCD=c:\openocd\elaphurelink\bin\openocd.exe
set SCRIPTS=c:\openocd\elaphurelink\share\openocd\scripts
set DAP_HOST=dap.local

if "%~1"=="" (
    echo.
    echo  ERROR: no .bin file specified.
    echo  Usage: %~nx0 firmware.bin [load_address]
    echo.
    exit /b 1
)

set BINFILE=%~1
set ADDR=%~2
if "%ADDR%"=="" set ADDR=0x10000000

echo.
echo  Device : %DAP_HOST%  (wireless ESP DAP)
echo  Target : MAX32672
echo  File   : %BINFILE%
echo  Addr   : %ADDR%
echo.

"%OPENOCD%" -s "%SCRIPTS%" ^
  -c "adapter driver cmsis-dap" ^
  -c "cmsis-dap backend elaphurelink" ^
  -c "cmsis-dap elaphurelink addr %DAP_HOST%" ^
  -c "adapter speed 1000" ^
  -c "reset_config srst_only" ^
  -c "swd newdap max32672.cpu -irlen 4 -expected-id 0x2ba01477 -ignore-version" ^
  -c "dap create max32672.dap -chain-position max32672.cpu" ^
  -c "target create max32672.cpu cortex_m -dap max32672.dap" ^
  -c "max32672.cpu configure -work-area-phys 0x20000000 -work-area-size 0x8000 -work-area-backup 0" ^
  -c "flash bank max32672.flash max32xxx 0x10000000 0x100000 0 0 max32672.cpu 0x40029000 0x2000 100" ^
  -c "init" ^
  -c "program {%BINFILE%} %ADDR% verify reset exit"

if %ERRORLEVEL% neq 0 (
    echo.
    echo  FAILED - check SWD wiring and device power.
    exit /b %ERRORLEVEL%
)

echo.
echo  Done - MAX32672 running new firmware.
