@echo off
setlocal
echo ===================================================
echo  CyberPulse Intelligence - Windows Setup
echo ===================================================

cd /d "%~dp0"

echo [*] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.11+.
    pause
    exit /b 1
)

echo [*] Creating virtual environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
)

echo [*] Activating virtual environment and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [*] Initializing database and running pre-flight tests...
python run_collector.py

echo ===================================================
echo [SUCCESS] CyberPulse Intelligence is ready!
echo Run 'run.bat' to launch the SOC dashboard.
echo ===================================================
pause
