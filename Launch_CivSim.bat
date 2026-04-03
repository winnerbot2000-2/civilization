@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" launch_civsim.py %*
) else (
  python launch_civsim.py %*
)
if errorlevel 1 (
  echo.
  echo Launcher failed. If this is a fresh checkout, install dependencies with:
  echo   pip install -e .[dev,viewer]
)
echo.
echo Press any key to close this window.
pause >nul
