@echo off
title ATLAS - One Scan Test
cd /d "%~dp0"

if not exist "atlas_local_secrets.bat" (
    echo Missing atlas_local_secrets.bat
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Run INSTALL_ONCE.bat first.
    pause
    exit /b 1
)

call atlas_local_secrets.bat
".venv\Scripts\python.exe" background_scan.py
pause
