@echo off
REM Simple database refresh batch file
REM Double-click to run or use: refresh_db.bat

cd /d "%~dp0"
python refresh_db.py
pause
