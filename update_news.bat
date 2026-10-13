@echo off
setlocal
echo ===================================================
echo  CyberPulse Intelligence - News Update Cycle
echo ===================================================

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python run_collector.py >> logs\update.log 2>&1
echo [OK] Update cycle complete at %DATE% %TIME%
