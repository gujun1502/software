@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ==========================================
echo   Out Building Decision - Daily Radar
echo ==========================================
echo.
echo [Step 1/2] Reading email via IMAP ...
python fetch_email.py
echo.
echo [Step 2/2] Scoring projects and building report ...
python run_radar.py
echo.
echo ==========================================
echo   Done. Open the report PDF in: reports folder
echo   (商机雷达日报_YYYY-MM-DD.pdf)
echo ==========================================
pause
