@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ============================================================
echo   XAU STRATEGY RESEARCHER - AUTO REPORTING INSTALLER
echo ============================================================
echo.

set "TASK_NAME=XAU Strategy Research - Automatic ChatGPT Reporting"
set "SCRIPT=%CD%\tools\auto_research_reporter.py"

where py >nul 2>&1 || (
    echo [ERROR] Python Launcher ^(py.exe^) was not found.
    exit /b 1
)
if not exist "%SCRIPT%" (
    echo [ERROR] Reporter script not found: %SCRIPT%
    exit /b 1
)

rem Remove the older polling task if it exists; the new watcher supersedes it.
schtasks /Delete /TN "XAU Strategy Research - Large Result Audit" /F >nul 2>&1

rem Start the watcher automatically at Windows logon. It keeps running and
rem reacts to changes in results\ranked_strategies.json within about 10 seconds.
schtasks /Create /SC ONLOGON /TN "%TASK_NAME%" /TR "py -3.12 \"%SCRIPT%\" --watch 10" /F
if errorlevel 1 (
    echo.
    echo [ERROR] Could not create the scheduled task.
    echo Try running this BAT as Administrator if Windows denies task creation.
    exit /b 1
)

echo.
echo [OK] Automatic research reporting installed.
echo [OK] Task: %TASK_NAME%
echo [OK] Trigger: Windows logon + file-change watcher
necho [OK] Watch interval: 10 seconds
 echo [OK] Raw ranked_strategies.json stays local.
echo [OK] Only compact audit files are pushed to GitHub.
echo [OK] Publishing is idempotent and SHA-256 protected.
echo.
echo The system will now publish automatically after each completed Research.
