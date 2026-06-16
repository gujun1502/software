@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在用 PyInstaller 打包 商机雷达.exe ...
echo (首次需先安装：pip install pyinstaller)
echo.
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
echo.
echo 完成。exe 在  dist\商机雷达.exe
echo 把它连同 配置文件/ data/ inbox/ 一起拷贝即可分发（参考 商机雷达_公司安装包）。
pause
