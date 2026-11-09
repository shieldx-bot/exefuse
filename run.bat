@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

%PY% --version >nul 2>nul
if not %errorlevel%==0 (
  echo [ExeFuse] Chua cai Python!
  echo           Tai va cai tai: https://www.python.org/downloads/
  echo           LUU Y: khi cai phai tick "Add python.exe to PATH".
  echo           Sau do chay lai file nay.
  pause
  exit /b 1
)

echo [ExeFuse] Dang cai dependencies (lan dau co the mat 1-2 phut)...
%PY% -m pip install -r requirements.txt

echo.
echo [ExeFuse] Khoi dong web UI tai http://127.0.0.1:5000
echo [ExeFuse] Dong cua so nay de tat server.
echo.
start "" "http://127.0.0.1:5000"
%PY% app.py
pause
