@echo off
title IBM Customer Stories — Open Dashboard
echo.
echo Opening the IBM Customer Stories Dashboard in your browser...
echo.

if not exist "output\dashboard\index.html" (
    color 4F
    echo ERROR: The dashboard has not been created yet.
    echo.
    echo Please run  2_TEST_10_STORIES.bat  or  3_RUN_ALL_STORIES.bat  first.
    echo.
    pause
    exit /b 1
)

start "" "output\dashboard\index.html"
echo Dashboard opened.
echo.
timeout /t 3 >nul
