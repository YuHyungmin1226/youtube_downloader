@echo off
setlocal
cd /d "%~dp0"
title YouTube Downloader

:: Check if Python is installed and accessible
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.10 or later from https://www.python.org/
    pause
    exit /b 1
)

:: Check required dependencies and auto-install if missing
python -c "import PySide6, yt_dlp, imageio_ffmpeg" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Installing required packages from requirements.txt...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install required dependencies.
        pause
        exit /b 1
    )
)

:: Launch YouTube Downloader
echo [INFO] Launching YouTube Downloader...
python youtube_downloader.py %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application terminated with error code %errorlevel%.
    pause
    exit /b %errorlevel%
)

endlocal
