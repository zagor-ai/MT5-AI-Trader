@echo off
setlocal EnableExtensions EnableDelayedExpansion

title XAU Strategy Researcher Pro v2.1

cd /d "%~dp0"

echo ============================================================
echo       XAU STRATEGY RESEARCHER PRO v2.1
echo ============================================================
echo.
echo [INFO] Working directory:
echo %CD%
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3.10 --version >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PYTHON_CMD=py -3.10"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python was not found.
    echo.
    echo Please install Python 3.10+ and make sure it is in PATH.
    echo.
    pause
    exit /b 1
)

echo [INFO] Python command:
echo %PYTHON_CMD%
echo.

echo [INFO] Checking Python...
%PYTHON_CMD% --version

echo.
echo [INFO] Checking required packages...

%PYTHON_CMD% -c "import MetaTrader5; print('MetaTrader5: OK')" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] MetaTrader5 package is missing.
    echo.
    echo Installing required packages...
    %PYTHON_CMD% -m pip install MetaTrader5 pandas numpy

    if errorlevel 1 (
        echo.
        echo [ERROR] Package installation failed.
        echo.
        pause
        exit /b 1
    )
)

%PYTHON_CMD% -c "import pandas; print('pandas: OK')" 2>nul
if errorlevel 1 (
    echo [INFO] Installing pandas...
    %PYTHON_CMD% -m pip install pandas
)

%PYTHON_CMD% -c "import numpy; print('numpy: OK')" 2>nul
if errorlevel 1 (
    echo [INFO] Installing numpy...
    %PYTHON_CMD% -m pip install numpy
)

echo.
echo ============================================================
echo [START] Launching XAU Strategy Researcher Pro v2.1
echo ============================================================
echo.

if not exist "XAU_Strategy_Researcher_Pro_v2.1.py" (
    echo [ERROR] Python application file not found:
    echo XAU_Strategy_Researcher_Pro_v2.1.py
    echo.
    pause
    exit /b 1
)

%PYTHON_CMD% "XAU_Strategy_Researcher_Pro_v2.1.py"

set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo ============================================================
if "%EXIT_CODE%"=="0" (
    echo [INFO] Application closed normally.
) else (
    echo [ERROR] Application exited with code %EXIT_CODE%.
)
echo ============================================================
echo.

pause
exit /b %EXIT_CODE%