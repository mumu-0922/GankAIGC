@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL_EXE%" if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL_EXE%" (
  for /f "delims=" %%P in ('where powershell.exe 2^>nul') do (
    set "POWERSHELL_EXE=%%P"
    goto :found_powershell
  )
)

:found_powershell
if not exist "%POWERSHELL_EXE%" (
  echo Cannot find Windows PowerShell.
  echo Please enable Windows PowerShell or install PowerShell, then run stop.bat again.
  pause
  exit /b 9009
)

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\stop.ps1"
echo.
pause
