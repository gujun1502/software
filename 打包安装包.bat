@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   商机雷达 · 一键重打安装包
echo   步骤：PyInstaller 重打 exe → Inno Setup 编译 setup → 输出到桌面
echo   （需已安装 pyinstaller 和 Inno Setup 6；改版本号请编辑
echo     installer\商机雷达安装包.iss 里的 MyAppVersion）
echo ============================================================
echo.

echo [1/2] PyInstaller 重打 dist\商机雷达.exe ...
python -m PyInstaller --onefile --console --name 商机雷达 --noconfirm ^
  --collect-all markdown ^
  --collect-submodules bs4 ^
  --hidden-import lxml._elementpath ^
  --hidden-import win32crypt --hidden-import win32file ^
  --hidden-import cryptography.hazmat.primitives.ciphers.aead ^
  --hidden-import evolve --hidden-import fetch_registry --hidden-import fetch_intention ^
  --hidden-import fetch_jiangsu --hidden-import fetch_ahjyztb --hidden-import fetch_shcpe ^
  --hidden-import keywords --hidden-import enable_local_llm --hidden-import enrich ^
  radar_app.py
if not %errorlevel%==0 (
  echo [出错] PyInstaller 打包失败。
  pause
  exit /b 1
)

echo.
echo [2/2] Inno Setup 编译安装包 ...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo [出错] 未找到 Inno Setup 6，请先安装：winget install JRSoftware.InnoSetup
  pause
  exit /b 1
)
"%ISCC%" "installer\商机雷达安装包.iss"
if not %errorlevel%==0 (
  echo [出错] 安装包编译失败。
  pause
  exit /b 1
)

echo.
echo ✅ 完成。安装包已输出到桌面：商机雷达安装包_v版本号.exe
pause
