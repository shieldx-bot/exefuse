@echo off
chcp 65001 >nul
setlocal
rem ================================================================
rem  ExeFuse - Kiem chung file bundle tren may Windows that
rem  Cach dung: keo tha file bundle vao file bat nay, hoac:
rem             verify_windows.bat "C:\duong\dan\Ten_Bundle.exe"
rem ================================================================

set "BUNDLE=%~1"
if "%BUNDLE%"=="" (
  echo Cach dung: verify_windows.bat "C:\duong\dan\Ten_Bundle.exe"
  echo    hoac keo tha file bundle can kiem chung vao file bat nay.
  pause
  exit /b 1
)
if not exist "%BUNDLE%" (
  echo Khong tim thay file: %BUNDLE%
  pause
  exit /b 1
)
set "NAME=%~nx1"

echo ================================================================
echo  ExeFuse kiem chung: %NAME%
echo ================================================================
echo.
echo [1/5] Kich hoat bundle va cho 15 giay de cac tien trinh khoi dong...
start "" "%BUNDLE%"
timeout /t 15 /nobreak >nul
echo.
echo [2/5] Tien trinh trong Task Manager theo ten "%NAME%":
echo ---------------------------------------------------------------
tasklist /fi "IMAGENAME eq %NAME%"
echo ---------------------------------------------------------------
echo    Neu thay nhieu dong cung ten "%NAME%" = CHUAN!
echo    (Tien trinh an da duoc dong vai trung ten file output)
echo.
echo [3/5] Kiem tra tien trinh nao con hien TEN THAT:
tasklist | findstr /i "traffmonetizer __hidden_app__ __visible_app__"
if errorlevel 1 echo    Khong co tien trinh nao hien ten that - TOT!
echo.
echo [4/5] settings.json ma launcher tu ghi (auto-token):
set "SR=%APPDATA%\traffmonetizer\settings.json"
set "SL=%LOCALAPPDATA%\traffmonetizer\settings.json"
if exist "%SR%" (
  echo    Roaming : %SR%
  echo    ----------------------------------------
  type "%SR%"
  echo.
  echo    ----------------------------------------
) else (
  echo    Roaming : KHONG THAY %SR%
)
if exist "%SL%" (
  echo    Local   : %SL%
) else (
  echo    Local   : KHONG THAY %SL%
)
echo.
echo [5/5] Kiem tra ket noi mang den backend Traffmonetizer:
ping -n 2 data.traffmonetizer.io | findstr /i "Reply TTL" >nul
if not errorlevel 1 (
  echo    data.traffmonetizer.io : KET NOI DUOC
) else (
  echo    data.traffmonetizer.io : KHONG PING DUOC - may co the chan mang
)
echo.
echo ================================================================
echo  HOAN TAT. Buoc cuoi: mo https://app.traffmonetizer.io/
echo  Dashboard - Devices: neu device moi xuat hien "Online" thi
echo  auto-token + tu dong ket noi HOAT DONG that su.
echo ================================================================
echo.
set /p KILL=Tat tien trinh bundle ngay bay gio? (Y/N):
if /i "%KILL%"=="Y" taskkill /im "%NAME%" /t /f
endlocal
pause
