@echo off
REM CONJURE UI Direct Startup Batch File
REM Starts the direct UI.py copy for CONJURE

echo Starting CONJURE UI (Direct UI.py Copy)...

REM Change to the script directory
cd /d "%~dp0"

REM Run with the conda environment Python
"C:\Users\Juan\.conda\envs\venv\python.exe" start_conjure_ui_direct.py

pause
