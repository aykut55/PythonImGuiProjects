@echo off
REM Yerel .venv ile main.py yi calistirir.
cd /d "%~dp0"
".venv\Scripts\python.exe" "%~dp0main.py"
pause
