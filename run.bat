@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

echo [ExeFuse] Dang cai dependencies (lan dau co the mat 1-2 phut)...
%PY% -m pip install -r requirements.txt

echo.
echo [ExeFuse] Khoi dong web UI tai http://127.0.0.1:5000
echo [ExeFuse] Dong cua so nay de tat server.
echo.
start "" "http://127.0.0.1:5000"
%PY% app.py
pause
