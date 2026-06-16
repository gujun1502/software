@echo off
chcp 65001 >nul
REM 每日定时任务实际执行的脚本（由「安装每日任务.bat」注册到 Windows 计划任务）。
REM 优先用打包好的 商机雷达.exe；没有则用 python 跑源码。运行日志追加到 data\每日运行日志.txt。
cd /d "%~dp0"
if not exist "data" mkdir data
set "LOG=data\每日运行日志.txt"
echo. >> "%LOG%"
echo ======== %date% %time% 每日自动运行开始 ======== >> "%LOG%"

if exist "商机雷达.exe" (
  "商机雷达.exe" auto >> "%LOG%" 2>&1
) else (
  python radar_app.py auto >> "%LOG%" 2>&1
)

echo ======== %date% %time% 结束（退出码 %errorlevel%） ======== >> "%LOG%"
