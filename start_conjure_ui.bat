@echo off
REM CONJURE UI Startup Batch File
REM Starts the CONJURE UI system on Windows

echo Starting CONJURE UI System...

REM Change to the script directory
cd /d "%~dp0"

REM Run with the conda environment Python
"C:\Users\Juan\.conda\envs\venv\python.exe" start_conjure_ui.py

pause
