@echo off
setlocal
echo ===================================================
echo  CyberPulse Intelligence - SQLite Database Backup
echo ===================================================

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python -c "from src.database import Database; db = Database(); path = db.backup_database(); print(f'[OK] Backup safely created at {path}')"
pause
