from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Run_XAU_Strategy_Researcher_Pro_v2.1.1.bat"

bat = r'''@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title XAU Strategy Researcher Pro v2.1.1

echo ============================================================
echo       XAU STRATEGY RESEARCHER PRO v2.1.1
echo ============================================================
echo.
echo [INFO] Checking Python 3.12...

py -3.12 --version >nul 2>nul
if not errorlevel 1 set "PYTHON_EXE=py -3.12"

if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"

if not defined PYTHON_EXE (
    echo [ERROR] Python 3.12 was not found.
    py -0p
    pause
    exit /b 1
)

%PYTHON_EXE% --version
echo.
echo [INFO] Checking required packages...
%PYTHON_EXE% -c "import MetaTrader5, pandas, numpy; print('[OK] Required packages available.')"
if errorlevel 1 (
    echo [INFO] Installing required packages...
    %PYTHON_EXE% -m pip install MetaTrader5 pandas numpy
    if errorlevel 1 (
        echo [ERROR] Package installation failed.
        pause
        exit /b 1
    )
)

if not exist "XAU_Strategy_Researcher_Pro_v2.1.1.py" (
    echo [ERROR] Application file not found.
    pause
    exit /b 1
)

echo [INFO] Starting research-only application...
%PYTHON_EXE% "XAU_Strategy_Researcher_Pro_v2.1.1.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo [INFO] Application exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
'''

OUT.write_text(bat, encoding="utf-8", newline="\r\n")
print(f"Generated {OUT.name}")
