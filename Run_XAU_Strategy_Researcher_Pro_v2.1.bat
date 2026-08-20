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

set "PYTHON_EXE="
set "PYTHON_VERSION_OK=0"

REM ============================================================
REM FIND PYTHON 3.12
REM ============================================================
echo [INFO] Searching for Python 3.12...
echo.

where py >nul 2>nul
if not errorlevel 1 (
    echo [INFO] Python Launcher found.
    for /f "delims=" %%V in ('py -3.12 --version 2^>nul') do (
        echo [INFO] Launcher response: %%V
        echo %%V | findstr /C:"Python 3.12" >nul
        if not errorlevel 1 (
            set "PYTHON_EXE=py -3.12"
            set "PYTHON_VERSION_OK=1"
        )
    )
)

REM ============================================================
REM FALLBACK: PYTHON COMMAND
REM ============================================================
if "%PYTHON_VERSION_OK%"=="0" (
    echo [INFO] Checking python command...
    where python >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%V in ('python --version 2^>nul') do (
            echo [INFO] Python response: %%V
            echo %%V | findstr /C:"Python 3.12" >nul
            if not errorlevel 1 (
                set "PYTHON_EXE=python"
                set "PYTHON_VERSION_OK=1"
            )
        )
    )
)

REM ============================================================
REM FALLBACK: STANDARD PYTHON 3.12 INSTALLATION
REM ============================================================
if "%PYTHON_VERSION_OK%"=="0" if exist "C:\Program Files\Python312\python.exe" (
    echo [INFO] Checking C:\Program Files\Python312\python.exe...
    for /f "delims=" %%V in ('"C:\Program Files\Python312\python.exe" --version 2^>nul') do (
        echo [INFO] Python response: %%V
        echo %%V | findstr /C:"Python 3.12" >nul
        if not errorlevel 1 (
            set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
            set "PYTHON_VERSION_OK=1"
        )
    )
)

REM ============================================================
REM PYTHON NOT FOUND
REM ============================================================
if "%PYTHON_VERSION_OK%"=="0" (
    echo.
    echo ============================================================
    echo [ERROR] Python 3.12 was NOT found.
    echo ============================================================
    echo.
    echo Please run: py -0p
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [OK] Python 3.12 runtime found
echo ============================================================
echo.
echo [INFO] Python command:
echo %PYTHON_EXE%
%PYTHON_EXE% --version

if errorlevel 1 (
    echo [ERROR] Python executable cannot be started.
    pause
    exit /b 1
)

REM ============================================================
REM CHECK REQUIRED PACKAGES
REM ============================================================
echo.
echo [INFO] Checking required packages...
%PYTHON_EXE% -c "import numpy, pandas, MetaTrader5; print('numpy:',numpy.__version__); print('pandas:',pandas.__version__); print('MetaTrader5: OK')"
if errorlevel 1 (
    echo.
    echo [ERROR] Required packages are missing or cannot be imported.
    echo [INFO] Run: %PYTHON_EXE% -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo [OK] Required packages available.

REM ============================================================
REM CHECK APPLICATION FILE
REM ============================================================
echo.
echo [INFO] Checking application file...
if not exist "%CD%\XAU_Strategy_Researcher_Pro_v2.1.py" (
    echo [ERROR] Application file not found.
    echo Expected: %CD%\XAU_Strategy_Researcher_Pro_v2.1.py
    pause
    exit /b 1
)
echo [OK] Application file found.

REM ============================================================
REM LAUNCH APPLICATION
REM ============================================================
echo.
echo ============================================================
echo       STARTING XAU STRATEGY RESEARCHER PRO v2.1
echo ============================================================
echo.
echo [INFO] Python:
%PYTHON_EXE% --version
echo.
echo [INFO] Executable:
%PYTHON_EXE% -c "import sys; print(sys.executable)"
echo.
echo [INFO] Research-only mode:
echo NO REAL TRADING ORDERS WILL BE SENT.
echo.
echo ============================================================
echo.

%PYTHON_EXE% "%CD%\XAU_Strategy_Researcher_Pro_v2.1.py"
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
