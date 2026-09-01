@echo off
title IBM Customer Stories — TEST (10 stories)
color 1F
echo.
echo ============================================================
echo   IBM Customer Stories — Test Run (10 stories only)
echo ============================================================
echo.
echo This will:
echo   - Visit www.ibm.com/case-studies
echo   - Download exactly 10 stories (slowly and politely)
echo   - Save them to the cache folder so they are not
echo     downloaded again on future runs
echo   - Create:  output\IBM_Customer_Stories_TEST.xlsx
echo   - Open the dashboard in your browser
echo.
echo Please do NOT close this window while it is running.
echo The download takes 20-40 seconds for 10 stories.
echo.

REM ── Check setup has been run ─────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    color 4F
    echo ERROR: Setup has not been run yet.
    echo Please double-click  1_SETUP.bat  first.
    echo.
    pause
    exit /b 1
)

echo Starting...
echo.
.venv\Scripts\python.exe run.py --mode test
if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo.
    echo Something went wrong. Please check the messages above.
    echo The full log is in:  logs\run_log.txt
    pause
    exit /b 1
)

echo.
echo Opening dashboard in your browser...
start "" "output\dashboard\index.html"

echo.
color 2F
echo ============================================================
echo   TEST COMPLETE
echo.
echo   Excel file:  output\IBM_Customer_Stories_TEST.xlsx
echo   Dashboard:   output\dashboard\index.html
echo   Log file:    logs\run_log.txt
echo.
echo   Review the results.
echo   When happy, double-click  3_RUN_ALL_STORIES.bat
echo ============================================================
echo.
pause
