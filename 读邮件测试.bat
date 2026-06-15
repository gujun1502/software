@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ==========================================
echo   Read email via IMAP - test
echo ==========================================
echo.
python fetch_email.py > "inbox\read_log.txt" 2>&1
type "inbox\read_log.txt"
echo.
echo ==========================================
echo   Done. Saved emails are in the inbox folder.
echo   If error above, send me inbox\read_log.txt
echo ==========================================
pause
