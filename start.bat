@echo off
chcp 65001 >nul
title Plant Trait Extractor - Backend Server

echo ==============================================
echo   Plant Trait Extractor - Local Backend
echo ==============================================
echo.
echo Starting Python backend...
echo.

cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python first.
    pause
    exit /b 1
)

:: Install dependencies
echo Installing dependencies...
pip install flask flask-cors requests beautifulsoup4 -q

echo.
echo Starting server...
echo.

:: Start server
python server.py

pause
