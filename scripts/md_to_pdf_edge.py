# -*- coding: utf-8 -*-
"""markdown → 带中文样式HTML → 用系统 Chrome/Edge 无头打印 PDF。跨平台(Win/macOS/Linux)。
用法: python md_to_pdf_edge.py input.md output.pdf [browser_path]
不传 browser_path 时自动探测系统浏览器。"""
import os, sys, subprocess, pathlib, urllib.parse, platform, shutil, tempfile, time
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


def find_browsers():
    """返回所有存在的浏览器路径（按优先级），用于失败时换一个重试。"""
    sysname = platform.system()
    if sysname == "Windows":
        cands = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    elif sysname == "Darwin":
        cands = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    else:
        cands = [shutil.which(n) for n in ("google-chrome", "chromium",
                 "chromium-browser", "microsoft-edge", "msedge")]
    out = []
    for c in cands:
        if c and pathlib.Path(c).exists() and c not in out:
            out.append(c)
    return out


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


def _try_print(browser, out_pdf, url):
    """用一个浏览器把 url 打印到 out_pdf（全新临时文件）；写出非空文件返回 True。"""
    try:
        if out_pdf.exists():
            out_pdf.unlink()
    except Exception:
        pass
    try:
        with tempfile.TemporaryDirectory(prefix="md2pdf_") as profile:
            subprocess.run(
                [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                 f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                 f"--print-to-pdf={out_pdf}", url],
                check=True, timeout=120,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False
    return out_pdf.exists() and out_pdf.stat().st_size > 1000


def convert(md_path, pdf_path, browser=None):
    # 用绝对路径：headless 浏览器在独立 user-data-dir 下，相对路径可能解析到非预期目录而静默不写。
    md_path, pdf_path = pathlib.Path(md_path).resolve(), pathlib.Path(pdf_path).resolve()
    browsers = [browser] if browser else find_browsers()
    if not browsers:
        raise RuntimeError("未找到 Chrome/Edge 浏览器，无法生成PDF。请安装 Microsoft Edge 或 Google Chrome。")
    body = markdown.markdown(md_path.read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code", "toc", "sane_lists"])
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>{body}</body></html>"""
    html_path = md_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    url = "file:///" + urllib.parse.quote(str(md_path.with_suffix(".html")).replace("\\", "/").lstrip("/"))

    # 关键：先打到全新的临时 PDF（绝不会被占用），成功后再落到目标名。
    # 这样既绕开「无头实例静默失败」，也绕开「目标PDF正被阅读器打开锁住」。
    tmp_pdf = pdf_path.with_name(pdf_path.stem + ".__building__.pdf")
    ok, last = False, None
    for b in browsers:
        for _ in range(2):
            if _try_print(b, tmp_pdf, url):
                ok = True
                break
            last = b
            time.sleep(1.0)
        if ok:
            break
    if not ok:
        raise RuntimeError(
            f"浏览器未写出PDF（{len(browsers)}个浏览器各试2次仍失败，最后用 {last}）。"
            f"常见原因：杀软拦截无头浏览器/磁盘只读。已保留 markdown 与 html。")

    # 落到目标名；若目标被占用（PDF 正在阅读器里打开），改存带时间戳的新名字。
    try:
        os.replace(tmp_pdf, pdf_path)
        return pdf_path
    except Exception:
        alt = pdf_path.with_name(pdf_path.stem + "_" + time.strftime("%H%M%S") + ".pdf")
        try:
            os.replace(tmp_pdf, alt)
        except Exception:
            return tmp_pdf      # 实在不行就返回临时文件本身
        print(f"  (原PDF似乎正被打开/占用，已另存为 {alt.name})")
        return alt


if __name__ == "__main__":
    out = convert(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    print("PDF_DONE", out, out.stat().st_size, "bytes")
