@echo off
cd /d "%~dp0"
echo Starting Backend + Frontend...
echo   API:       http://localhost:8000
echo   Dashboard: http://localhost:3000
echo.
python start_all.py
pause
