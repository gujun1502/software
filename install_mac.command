#!/bin/bash
# Out Building Decision · macOS 一键安装
# 双击本文件，或在终端运行: bash install_mac.command
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
echo "=========================================="
echo "  Out Building Decision · Mac 安装"
echo "  目录: $DIR"
echo "=========================================="

# 1. 检查 python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未找到 python3。"
  echo "请先安装 Python：https://www.python.org/downloads/  或  brew install python"
  exit 1
fi
PYBIN="$(command -v python3)"
echo "[1/4] 使用 Python: $PYBIN ($($PYBIN --version 2>&1))"

# 2. 安装依赖
echo "[2/4] 安装依赖 (requests / beautifulsoup4 / lxml / markdown) ..."
"$PYBIN" -m pip install --user --quiet --upgrade requests beautifulsoup4 lxml markdown || {
  echo "[提示] pip 安装失败，尝试不带 --user 重试 ..."
  "$PYBIN" -m pip install --quiet --upgrade requests beautifulsoup4 lxml markdown
}

# 3. 检查浏览器（生成 PDF 用）
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "/Applications/Microsoft Edge.app" ] && [ ! -d "/Applications/Chromium.app" ]; then
  echo "[提示] 未发现 Chrome/Edge。PDF 生成需要，请安装 Google Chrome：https://www.google.com/chrome/"
else
  echo "[3/4] 已发现浏览器，可生成 PDF。"
fi

# 4. 安装 launchd 定时任务（每天 9:30 / 9:45 / 10:00，当天只跑一次）
PLIST="$HOME/Library/LaunchAgents/com.obd.dailyradar.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.obd.dailyradar</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYBIN</string>
    <string>$DIR/daily_job.py</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>45</integer></dict>
    <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$DIR/data/launchd.log</string>
  <key>StandardErrorPath</key><string>$DIR/data/launchd.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
EOF
launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"
echo "[4/4] 定时任务已安装：每天 9:30 / 9:45 / 10:00 自动运行（当天只跑一次）。"

echo ""
echo "=========================================="
echo "  安装完成！"
echo "  - 立即手动跑一次：双击 每日商机雷达.command"
echo "  - 每天自动出报告 + 推送微信，无需操作"
echo "  - 卸载定时：launchctl unload $PLIST"
echo "=========================================="
read -n 1 -s -r -p "按任意键关闭..."
echo ""
