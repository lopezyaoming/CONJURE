@echo off
REM CONJURE UI Launcher
REM Runs the main CONJURE UI overlay

echo Starting CONJURE UI Overlay...

REM Change to the script directory
cd /d "%~dp0"

REM Run the UI with the conda environment Python
"C:\Users\Juan\.conda\envs\venv\python.exe" Agent/conjure_ui.py

pause 