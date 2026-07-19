@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0daily_run.ps1"
exit /b %errorlevel%
