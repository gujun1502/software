@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================================
echo   安装本地大模型（Ollama + qwen2.5:7b） · 一次性
echo   装好后商机雷达就用本机模型抽取，免费 / 离线 / 不外传数据
echo ============================================================
echo.

REM ---- 1) 确认 Ollama 是否已安装 ----
where ollama >nul 2>nul
if %errorlevel%==0 goto HAVE_OLLAMA

echo [1/3] 未检测到 Ollama，正在用 winget 安装...
winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
if %errorlevel%==0 goto INSTALLED

echo.
echo   winget 安装失败或不可用。请手动下载安装后重跑本脚本：
echo   下载地址： https://ollama.com/download/windows
start "" "https://ollama.com/download/windows"
pause
exit /b 1

:INSTALLED
echo   Ollama 安装完成。若提示找不到命令，请关掉本窗口重开一次再跑。
set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"

:HAVE_OLLAMA
echo [1/3] Ollama 已就绪。
echo.

REM ---- 2) 拉取中文抽取模型 ----
echo [2/3] 拉取模型 qwen2.5:7b（约 4.7GB，首次较慢，请耐心等待）...
echo       想更准可改用 qwen2.5:14b（约 9GB）；想更快用 qwen2.5:3b。
ollama pull qwen2.5:7b
if not %errorlevel%==0 (
  echo   模型拉取失败。请确认 Ollama 服务已启动后重试。
  pause
  exit /b 1
)
echo.

REM ---- 3) 生成 / 开启 llm_config.json ----
echo [3/3] 配置 llm_config.json（把本地 Ollama 接入大模型链并启用）...
if exist "商机雷达.exe" (
  "商机雷达.exe" enable-llm qwen2.5:7b
) else (
  python enable_local_llm.py qwen2.5:7b || echo   （若没装 Python：手动在 llm_config.json 的 providers 顶部加一条本地 Ollama，并把 enabled 改 true）
)
echo.

echo ============================================================
echo   完成！现在跑「每日商机雷达.bat」或 python enrich.py --llm
echo   就会优先用本地 qwen2.5 抽取面积/造价/关键词。
echo   自检： ollama run qwen2.5:7b  然后输入一句话试试，Ctrl+D 退出。
echo ============================================================
pause
