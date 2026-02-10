@echo off
REM ============================================================
REM DAHAB AI - Persistent Worker Process
REM ============================================================
REM This script starts the worker in the background.
REM The worker will keep running even after closing this window.
REM It generates recommendations, evaluates them, and trades 24/7.
REM
REM Usage:
REM   Double-click this file OR run from command line:
REM   run_worker.bat
REM ============================================================

echo ============================================================
echo   DAHAB AI - Starting Persistent Worker
echo ============================================================
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Starting worker process in background...
echo Worker log: %~dp0worker_output.log
echo.

REM Start worker.py as a detached background process
start /b "" python worker.py >> worker_output.log 2>&1

echo.
echo [OK] Worker started successfully!
echo.
echo The worker will:
echo   - Generate recommendations continuously
echo   - Evaluate past recommendations automatically
echo   - Execute paper trades based on forecasts
echo   - Keep running even when Streamlit website is closed
echo.
echo To stop the worker, close this window or use Task Manager.
echo To view worker logs: type worker_output.log
echo.

REM Keep window open to show worker is running
echo Press any key to close this window (worker continues in background)...
pause >nul
