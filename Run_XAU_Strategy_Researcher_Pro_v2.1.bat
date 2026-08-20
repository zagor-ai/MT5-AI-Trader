@echo off
setlocal
title XAU Strategy Researcher Pro v2.1
cd /d "%~dp0"

echo ============================================================
echo       XAU Strategy Researcher Pro v2.1
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found in PATH.
    echo Activate your Anaconda environment or install Python.
    pause
    exit /b 1
)

if not exist "XAU_Strategy_Researcher_Pro_v2.1.py" (
    echo ERROR: XAU_Strategy_Researcher_Pro_v2.1.py not found.
    echo Put this BAT file in the same folder as the Python file.
    pause
    exit /b 1
)

echo Checking required packages...
python -c "import MetaTrader5, pandas, numpy" >nul 2>&1
if errorlevel 1 (
    echo Required packages are missing.
    echo Installing MetaTrader5 pandas numpy...
    echo.
    python -m pip install MetaTrader5 pandas numpy
    if errorlevel 1 (
        echo.
        echo ERROR: Package installation failed.
        pause
        exit /b 1
    )
)

echo.
echo Starting XAU Strategy Researcher Pro v2.1...
echo.
python "XAU_Strategy_Researcher_Pro_v2.1.py"

echo.
echo ============================================================
echo Program closed.
echo ============================================================
pause
endlocal
