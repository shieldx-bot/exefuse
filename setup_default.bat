@echo off
setlocal
cd /d "%~dp0"

if not exist defaults mkdir defaults

if exist Traffmonetizer.exe (
  copy /y Traffmonetizer.exe defaults\Traffmonetizer.exe >nul
  echo [OK] Da copy Traffmonetizer.exe vao defaults\
) else (
  if exist defaults\Traffmonetizer.exe (
    echo [OK] defaults\Traffmonetizer.exe da co san.
  ) else (
    echo [!] Khong thay Traffmonetizer.exe trong thu muc nay.
    echo     Hay copy file Traffmonetizer.exe vao thu muc defaults\ thu cong,
    echo     hoac dat file can an vao defaults\ voi ten bat ky (.exe).
  )
)
pause
