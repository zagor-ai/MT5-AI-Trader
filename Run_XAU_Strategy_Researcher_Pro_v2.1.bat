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

REM ============================================================
REM CONFIGURATION
REM ============================================================

set "PYTHON_EXE="
set "PYTHON_VERSION_OK=0"

REM ============================================================
REM STEP 1 - CHECK PYTHON LAUNCHER
REM ============================================================

echo [INFO] Searching for Python 3.10...
echo.

where py >nul 2>nul

if not errorlevel 1 (
    echo [INFO] Python Launcher found.

    for /f "delims=" %%V in ('py -3.10 --version 2^>nul') do (
        echo [INFO] Launcher response: %%V

        echo %%V | findstr /C:"Python 3.10" >nul

        if not errorlevel 1 (
            set "PYTHON_EXE=py -3.10"
            set "PYTHON_VERSION_OK=1"
        )
    )
)

REM ============================================================
REM STEP 2 - CHECK NORMAL PYTHON COMMAND
REM ============================================================

if "%PYTHON_VERSION_OK%"=="0" (

    echo.
    echo [INFO] Checking python command...

    where python >nul 2>nul

    if not errorlevel 1 (

        for /f "delims=" %%V in ('python --version 2^>nul') do (
            echo [INFO] Python response: %%V

            echo %%V | findstr /C:"Python 3.10" >nul

            if not errorlevel 1 (
                set "PYTHON_EXE=python"
                set "PYTHON_VERSION_OK=1"
            )
        )
    )
)

REM ============================================================
REM STEP 3 - CHECK COMMON ANACONDA INSTALLATIONS
REM ============================================================

if "%PYTHON_VERSION_OK%"=="0" (

    echo.
    echo [INFO] Checking common Anaconda locations...

    if exist "%USERPROFILE%\anaconda3\python.exe" (
        "%USERPROFILE%\anaconda3\python.exe" --version

        for /f "delims=" %%V in ('"%USERPROFILE%\anaconda3\python.exe" --version 2^>nul') do (
            echo %%V | findstr /C:"Python 3.10" >nul

            if not errorlevel 1 (
                set "PYTHON_EXE=%USERPROFILE%\anaconda3\python.exe"
                set "PYTHON_VERSION_OK=1"
            )
        )
    )
)

REM ============================================================
REM STEP 4 - CHECK MINICONDA
REM ============================================================

if "%PYTHON_VERSION_OK%"=="0" (

    if exist "%USERPROFILE%\miniconda3\python.exe" (

        "%USERPROFILE%\miniconda3\python.exe" --version

        for /f "delims=" %%V in ('"%USERPROFILE%\miniconda3\python.exe" --version 2^>nul') do (
            echo %%V | findstr /C:"Python 3.10" >nul

            if not errorlevel 1 (
                set "PYTHON_EXE=%USERPROFILE%\miniconda3\python.exe"
                set "PYTHON_VERSION_OK=1"
            )
        )
    )
)

REM ============================================================
REM STEP 5 - CHECK ANACONDA3 IN C:\ProgramData
REM ============================================================

if "%PYTHON_VERSION_OK%"=="0" (

    if exist "C:\ProgramData\Anaconda3\python.exe" (

        "C:\ProgramData\Anaconda3\python.exe" --version

        for /f "delims=" %%V in ('"C:\ProgramData\Anaconda3\python.exe" --version 2^>nul') do (
            echo %%V | findstr /C:"Python 3.10" >nul

            if not errorlevel 1 (
                set "PYTHON_EXE=C:\ProgramData\Anaconda3\python.exe"
                set "PYTHON_VERSION_OK=1"
            )
        )
    )
)

REM ============================================================
REM STEP 6 - CHECK LOCAL PROJECT VENV
REM ============================================================

if "%PYTHON_VERSION_OK%"=="0" (

    if exist "%CD%\.venv\Scripts\python.exe" (

        "%CD%\.venv\Scripts\python.exe" --version

        for /f "delims=" %%V in ('"%CD%\.venv\Scripts\python.exe" --version 2^>nul') do (
            echo %%V | findstr /C:"Python 3.10" >nul

            if not errorlevel 1 (
                set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
                set "PYTHON_VERSION_OK=1"
            )
        )
    )
)

REM ============================================================
REM PYTHON NOT FOUND
REM ============================================================

if "%PYTHON_VERSION_OK%"=="0" (

    echo.
    echo ============================================================
    echo [ERROR] Python 3.10 was NOT found.
    echo ============================================================
    echo.
    echo The Python Launcher exists, but Python 3.10 runtime
    echo is not installed or is not registered correctly.
    echo.
    echo Please run:
    echo.
    echo     py -0p
    echo.
    echo This will show all installed Python versions.
    echo.
    echo If you use Anaconda, run:
    echo.
    echo     where python
    echo.
    echo and:
    echo.
    echo     conda info
    echo.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM PYTHON FOUND
REM ============================================================

echo.
echo ============================================================
echo [OK] Python runtime found
echo ============================================================
echo.
echo [INFO] Python command:
echo %PYTHON_EXE%
echo.

%PYTHON_EXE% --version

if errorlevel 1 (
    echo.
    echo [ERROR] Python executable cannot be started.
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM CHECK PIP
REM ============================================================

echo.
echo [INFO] Checking pip...

%PYTHON_EXE% -m pip --version >nul 2>nul

if errorlevel 1 (

    echo [WARN] pip is not available.
    echo [INFO] Attempting ensurepip...

    %PYTHON_EXE% -m ensurepip --upgrade

    if errorlevel 1 (
        echo.
        echo [ERROR] Could not initialize pip.
        echo.
        pause
        exit /b 1
    )
)

echo [OK] pip available.

REM ============================================================
REM CHECK NUMPY
REM ============================================================

echo.
echo [INFO] Checking numpy...

%PYTHON_EXE% -c "import numpy; print('numpy:', numpy.__version__)" >nul 2>nul

if errorlevel 1 (

    echo [INFO] numpy is missing.
    echo [INFO] Installing numpy...

    %PYTHON_EXE% -m pip install --upgrade numpy

    if errorlevel 1 (
        echo.
        echo [ERROR] numpy installation failed.
        echo.
        pause
        exit /b 1
    )
)

echo [OK] numpy available.

REM ============================================================
REM CHECK PANDAS
REM ============================================================

echo.
echo [INFO] Checking pandas...

%PYTHON_EXE% -c "import pandas; print('pandas:', pandas.__version__)" >nul 2>nul

if errorlevel 1 (

    echo [INFO] pandas is missing.
    echo [INFO] Installing pandas...

    %PYTHON_EXE% -m pip install --upgrade pandas

    if errorlevel 1 (
        echo.
        echo [ERROR] pandas installation failed.
        echo.
        pause
        exit /b 1
    )
)

echo [OK] pandas available.

REM ============================================================
REM CHECK METATRADER5
REM ============================================================

echo.
echo [INFO] Checking MetaTrader5 package...

%PYTHON_EXE% -c "import MetaTrader5; print('MetaTrader5:', MetaTrader5.__version__)" >nul 2>nul

if errorlevel 1 (

    echo [WARN] MetaTrader5 package is missing.
    echo.
    echo [INFO] Installing MetaTrader5...
    echo.

    %PYTHON_EXE% -m pip install --upgrade MetaTrader5

    if errorlevel 1 (
        echo.
        echo ============================================================
        echo [ERROR] MetaTrader5 installation failed.
        echo ============================================================
        echo.
        echo Python being used:
        %PYTHON_EXE% --version
        echo.
        echo Python path:
        %PYTHON_EXE% -c "import sys; print(sys.executable)"
        echo.
        pause
        exit /b 1
    )
)

echo [OK] MetaTrader5 available.

REM ============================================================
REM FINAL PACKAGE TEST
REM ============================================================

echo.
echo ============================================================
echo [INFO] Running package diagnostics...
echo ============================================================
echo.

%PYTHON_EXE% -c "import sys; print('[PYTHON] ', sys.version); print('[PYTHON PATH]', sys.executable); import numpy; print('[NUMPY] OK'); import pandas; print('[PANDAS] OK'); import MetaTrader5; print('[MT5 PACKAGE] OK')"

if errorlevel 1 (
    echo.
    echo [ERROR] Package diagnostic failed.
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM CHECK APPLICATION FILE
REM ============================================================

echo.
echo [INFO] Checking application file...

if not exist "%CD%\XAU_Strategy_Researcher_Pro_v2.1.py" (

    echo.
    echo ============================================================
    echo [ERROR] Application file not found.
    echo ============================================================
    echo.
    echo Expected:
    echo %CD%\XAU_Strategy_Researcher_Pro_v2.1.py
    echo.
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
echo [INFO] Application:
echo XAU_Strategy_Researcher_Pro_v2.1.py
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