@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_tasks.ps1" /remove %*
set "RC=%errorlevel%"
if /i not "%~1"=="/auto" pause
exit /b %RC%
