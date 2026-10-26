@echo off
rem Run the Invigil launcher from the repo root: invigil start | stop | status | calibrate
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m invigil %*
) else (
    python -m invigil %*
)
rem Keep the window open on an error, so a double-clicked shortcut shows why.
if errorlevel 1 pause
