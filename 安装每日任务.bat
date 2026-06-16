@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================================
echo   注册「每日商机雷达」到 Windows 计划任务
echo   每天定点自动：进化(扩词/探源) + 全量刷新 + 出日报
echo ============================================================
echo.

set "TASKNAME=商机雷达每日进化"
set /p RUNTIME=每天几点跑？(24小时制，回车默认 08:30)：
if "%RUNTIME%"=="" set "RUNTIME=08:30"

echo.
echo 将注册：任务名「%TASKNAME%」，每天 %RUNTIME% 运行 _每日自动运行.bat
echo.

schtasks /Create /TN "%TASKNAME%" /TR "\"%~dp0_每日自动运行.bat\"" /SC DAILY /ST %RUNTIME% /F
if %errorlevel%==0 (
  echo.
  echo ✅ 注册成功！开机且到点就会自动跑（电脑需开机；笔记本插电更稳）。
  echo    立即试跑一次：    schtasks /Run /TN "%TASKNAME%"
  echo    查看下次运行时间：schtasks /Query /TN "%TASKNAME%" /V /FO LIST ^| findstr /i "下次 Next 状态 Status"
  echo    取消每日任务：    schtasks /Delete /TN "%TASKNAME%" /F
  echo    运行日志在：      data\每日运行日志.txt
) else (
  echo.
  echo ❌ 注册失败。多半是权限问题：请右键本 bat →「以管理员身份运行」再试。
)
echo.
pause
