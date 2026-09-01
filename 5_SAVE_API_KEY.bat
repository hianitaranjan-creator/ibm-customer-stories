@echo off
title IBM Customer Stories — Save Tavily API Key
color 1F
echo.
echo ============================================================
echo   Save your Tavily API Key
echo ============================================================
echo.
echo To get your free key (2 minutes):
echo   1. Go to https://app.tavily.com/sign-up
echo   2. Sign up with your email (no credit card needed)
echo   3. Copy the API key shown on your dashboard
echo      It starts with:  tvly-
echo.
echo ============================================================
echo.
set /p TAVILY_KEY="Paste your Tavily key here and press Enter: "

if "%TAVILY_KEY%"=="" (
    color 4F
    echo.
    echo ERROR: No key was entered. Please try again.
    pause
    exit /b 1
)

REM Write the key to .env in this folder
echo TAVILY_API_KEY=%TAVILY_KEY%> "%~dp0.env"

echo.
echo Testing the key...
"%~dp0.venv\Scripts\python.exe" -c "
from tavily import TavilyClient
import sys
key = '%TAVILY_KEY%'
try:
    c = TavilyClient(key)
    r = c.search('IBM case study', max_results=1)
    print('  Connection: OK')
    print('  Tavily is working correctly.')
except Exception as e:
    print('  ERROR: ' + str(e))
    sys.exit(1)
" 2>&1

if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo.
    echo The key did not work. Please check:
    echo   - Did you copy the whole key? It should be about 50 characters long.
    echo   - Does it start with  tvly-  ?
    echo   - Try getting a new key from https://app.tavily.com
    echo.
    pause
    exit /b 1
)

color 2F
echo.
echo ============================================================
echo   KEY SAVED SUCCESSFULLY!
echo.
echo   Now run 3_RUN_ALL_STORIES.bat to collect all stories.
echo ============================================================
echo.
pause
