@echo off
:: Build ESP32-C3 firmware via WSL.  Usage:
::   build          -- full setup + build
::   build --build  -- build only (skip IDF setup)
::   build --clean  -- clean build dir first
wsl python3 "/mnt/c/Users/RWache/OneDrive - Rockwell Automation, Inc/Simulation tools/GitHub/wireless-esp8266-dap/build_WSL.py" %*
