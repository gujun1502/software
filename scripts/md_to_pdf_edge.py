# -*- coding: utf-8 -*-
"""markdown → 带中文样式HTML → 用系统 Chrome/Edge 无头打印 PDF。跨平台(Win/macOS/Linux)。
用法: python md_to_pdf_edge.py input.md output.pdf [browser_path]
不传 browser_path 时自动探测系统浏览器。"""
import sys, subprocess, pathlib, urllib.parse, platform, shutil
import markdown


def find_browser():
    """跨平台找一个 Chromium 内核浏览器（Edge / Chrome / Chromium）。"""
    sysname = platform.system()
    candidates = []
    if sysname == "Windows":
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    elif sysname == "Darwin":  # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    else:  # Linux
        for name in ("google-chrome", "chromium", "chromium-browser",
                     "microsoft-edge", "msedge"):
            p = shutil.which(name)
            if p:
                candidates.append(p)
    for c in candidates:
        if c and pathlib.Path(c).exists():
            return c
    return None


CSS = """
@page { size: A4; margin: 1.8cm 1.6cm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei","PingFang SC","Hiragino Sans GB","Songti SC","SimSun",sans-serif;
       font-size: 11.5pt; line-height: 1.75; color: #1a1a1a; }
h1 { font-size: 22pt; color: #0b3d66; border-bottom: 3px solid #0b3d66; padding-bottom: 8px; margin-top: 0; }
h2 { font-size: 16pt; color: #0b3d66; border-left: 6px solid #2e7fb8; padding-left: 10px; margin-top: 28px; }
h3 { font-size: 13pt; color: #1f5a82; margin-top: 20px; }
h4 { font-size: 12pt; color: #333; }
blockquote { background: #eef5fb; border-left: 4px solid #2e7fb8; margin: 12px 0; padding: 8px 14px; color: #335; }
table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 10.5pt; }
th, td { border: 1px solid #b9c9d6; padding: 6px 9px; text-align: left; vertical-align: top; }
th { background: #0b3d66; color: #fff; }
tr:nth-child(even) td { background: #f3f8fc; }
pre { background: #1e2530; color: #e6edf3; padding: 14px; border-radius: 6px; overflow-x: auto;
      font-size: 8.6pt; line-height: 1.45; font-family: "Consolas","Menlo","Courier New",monospace; white-space: pre; }
code { font-family: "Consolas","Menlo","Courier New",monospace; }
:not(pre) > code { background: #eef1f4; color: #c0341d; padding: 1px 5px; border-radius: 3px; font-size: 9.5pt; }
hr { border: none; border-top: 1px solid #ccd; margin: 22px 0; }
strong { color: #0b3d66; }
ul, ol { padding-left: 24px; }
li { margin: 3px 0; }
h2, h3 { page-break-after: avoid; }
table, pre, blockquote { page-break-inside: avoid; }
"""


def convert(md_path, pdf_path, browser=None):
    md_path, pdf_path = pathlib.Path(md_path), pathlib.Path(pdf_path)
    browser = browser or find_browser()
    if not browser or not pathlib.Path(browser).exists():
        raise RuntimeError("未找到 Chrome/Edge 浏览器，无法生成PDF。请安装 Google Chrome。")
    body = markdown.markdown(md_path.read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code", "toc", "sane_lists"])
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>{body}</body></html>"""
    html_path = md_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    url = "file:///" + urllib.parse.quote(str(md_path.with_suffix(".html")).replace("\\", "/").lstrip("/"))
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", url], check=True, timeout=120)
    return pdf_path


if __name__ == "__main__":
    out = convert(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    print("PDF_DONE", out, out.stat().st_size, "bytes")
