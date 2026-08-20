from pathlib import Path

bat = r'''@echo off
title XAU Strategy Researcher Pro
cd /d "%~dp0"

echo ============================================================
echo        XAU Strategy Researcher Pro - Launcher
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found in PATH.
    echo.
    echo Please install Python or add it to PATH.
    pause
    exit /b 1
)

if not exist "XAU_Strategy_Researcher_Pro_v1.py" (
    echo ERROR: XAU_Strategy_Researcher_Pro_v1.py was not found.
    echo.
    echo Put this BAT file in the same folder as the Python file.
    pause
    exit /b 1
)

echo Checking required Python packages...
python -c "import MetaTrader5, pandas, numpy" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Required packages are missing.
    echo Installing:
    echo MetaTrader5 pandas numpy
    echo.
    python -m pip install MetaTrader5 pandas numpy
    if errorlevel 1 (
        echo.
        echo ERROR: Package installation failed.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Starting XAU Strategy Researcher Pro...
echo.

python "XAU_Strategy_Researcher_Pro_v1.py"

echo.
echo ============================================================
echo Program finished.
echo ============================================================
pause
'''

path = Path("/mnt/data/Run_XAU_Strategy_Researcher_Pro.bat")
path.write_text(bat, encoding="utf-8")
print(path)
