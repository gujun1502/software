#!/bin/bash
# Out Building Decision · 手动跑一次（macOS）
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
echo "=========================================="
echo "  Out Building Decision · 商机雷达"
echo "=========================================="
PYBIN="$(command -v python3)"
echo "[1/2] 读取采招网邮件 ..."
"$PYBIN" fetch_email.py
echo "[2/2] 决策打分并生成日报 ..."
"$PYBIN" run_radar.py
echo ""
echo "完成。日报 PDF 在 reports 文件夹。"
read -n 1 -s -r -p "按任意键关闭..."
echo ""
