@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ==========================================
echo   Out Building Decision - Daily Radar
echo   Full refresh
echo   收邮件 - 江苏/安徽/上海抓取 - 详情页增强(MiniMax) - 出日报
echo ==========================================
echo.
python radar_app.py update
echo.
if errorlevel 1 (
  echo [ERROR] See messages above.
  pause
) else (
  echo Done. PDF should have opened automatically (also in reports\).
  timeout /t 4 >nul
)
