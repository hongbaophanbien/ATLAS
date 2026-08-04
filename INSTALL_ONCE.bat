@echo off
title ATLAS - First Time Installation
cd /d "%~dp0"

echo ==========================================
echo ATLAS - INSTALLATION (RUN ONE TIME ONLY)
echo ==========================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py"
) else (
    set "PYTHON_CMD=python"
)

%PYTHON_CMD% --version
if errorlevel 1 (
    echo.
    echo Python was not found.
    echo Install Python 3.12, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
)

echo Installing ATLAS dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo INSTALLATION COMPLETE.
echo Next: edit atlas_local_secrets.bat and then double-click START_ATLAS_WORKER.bat
pause
