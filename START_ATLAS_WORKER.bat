@echo off
title ATLAS 60-Second Background Worker
cd /d "%~dp0"

if not exist "atlas_local_secrets.bat" (
    echo ===================================================
    echo MISSING: atlas_local_secrets.bat
    echo.
    echo 1. Copy atlas_local_secrets_TEMPLATE.bat
    echo 2. Rename the copy to atlas_local_secrets.bat
    echo 3. Fill in your Supabase URL and keys
    echo 4. Run START_ATLAS_WORKER.bat again
    echo ===================================================
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo ATLAS is not installed yet.
    echo Double-click INSTALL_ONCE.bat first.
    pause
    exit /b 1
)

call atlas_local_secrets.bat

echo ==========================================
echo ATLAS WORKER STARTING
echo Keep this window open.
echo Snapshot target interval: 60 seconds
echo ==========================================
echo.

".venv\Scripts\python.exe" worker_60s.py

echo.
echo ATLAS worker stopped.
pause
