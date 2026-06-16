@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo 正在用现有数据生成商机雷达日报...
python radar_app.py report
if errorlevel 1 (
  echo.
  echo [出错] 请看上面的提示。
  pause
)
