@echo off
setlocal
echo ===================================================
echo  CyberPulse Intelligence - Launching SOC Dashboard
echo ===================================================

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo [*] Starting Streamlit server on 127.0.0.1:8501...
python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501
