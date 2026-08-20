@echo off
setlocal EnableExtensions EnableDelayedExpansion

title XAU Strategy Researcher Pro v2.1.1

cd /d "%~dp0"

echo.
echo ============================================================
echo       XAU STRATEGY RESEARCHER PRO v2.1.1
echo ============================================================
echo.
echo [INFO] Working directory:
echo %CD%
echo.

set "PYTHON_EXE="

REM ============================================================
REM FIND PYTHON 3.12
REM ============================================================

where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=py -3.12"
)

if not defined PYTHON_EXE (
    where python >nul 2>nul
    if not errorlevel 1 (
        python --version 2>nul | findstr /C:"Python 3.12" >nul
        if not errorlevel 1 set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE if exist "%USERPROFILE%\anaconda3\python.exe" (
    "%USERPROFILE%\anaconda3\python.exe" --version 2>nul | findstr /C:"Python 3.12" >nul
    if not errorlevel 1 set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe"
)

if not defined PYTHON_EXE (
    echo.
    echo [ERROR] Python 3.12 was not found.
    echo.
    echo Run:
    echo     py -0p
    echo.
    echo and send the result if needed.
    echo.
    pause
    exit /b 1
)

echo [OK] Python runtime found:
echo.
%PYTHON_EXE% --version

echo.
echo [INFO] Python executable:
%PYTHON_EXE% -c "import sys; print(sys.executable)"

echo.
echo [INFO] Checking required packages...

%PYTHON_EXE% -c "import numpy, pandas, MetaTrader5; print('Packages: OK')" >nul 2>nul
if errorlevel 1 (
    echo [WARN] Required packages missing. Installing...
    %PYTHON_EXE% -m pip install numpy pandas MetaTrader5
    if errorlevel 1 (
        echo.
        echo [ERROR] Package installation failed.
        pause
        exit /b 1
    )
)

echo [OK] Required packages available.

echo.
echo [INFO] Checking application files...

if not exist "%CD%\XAU_Strategy_Researcher_Pro_v2.1.py" (
    echo [ERROR] Base v2.1 engine not found.
    echo Expected:
    echo %CD%\XAU_Strategy_Researcher_Pro_v2.1.py
    pause
    exit /b 1
)

if not exist "%CD%\XAU_Strategy_Researcher_Pro_v2.1.1.py" (
    echo [ERROR] v2.1.1 launcher not found.
    echo Expected:
    echo %CD%\XAU_Strategy_Researcher_Pro_v2.1.1.py
    pause
    exit /b 1
)

echo [OK] Application files found.

echo.
echo ============================================================
echo       STARTING RESEARCH ENGINE v2.1.1
echo ============================================================
echo.
echo [INFO] Mode: Research / Backtest only
echo [INFO] Real MT5 orders: DISABLED
echo [INFO] Data loader: Chunked MT5 history
echo.

%PYTHON_EXE% "%CD%\XAU_Strategy_Researcher_Pro_v2.1.1.py"

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
