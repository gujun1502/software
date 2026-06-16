# -*- coding: utf-8 -*-
"""统一的应用根目录。
- 开发(源码)运行：= 本文件所在目录。
- PyInstaller 打包成 exe 后：= exe 所在目录（这样 配置文件 / data / reports 都在 exe 旁边，
  用户可直接编辑配置、看到生成的报告）。
所有模块都从这里取 ROOT，保证源码版与 exe 版行为一致。
"""
import sys
import pathlib

if getattr(sys, "frozen", False):          # PyInstaller 冻结后为 True
    ROOT = pathlib.Path(sys.executable).resolve().parent
else:
    ROOT = pathlib.Path(__file__).resolve().parent
