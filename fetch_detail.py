# -*- coding: utf-8 -*-
"""
详情页抓取（在你本机 / 中国境内、最好关 VPN 直连时运行）。
给一个商机的 detail_url，把详情页正文文本抓下来，供 enrich.py 提取 面积/造价/关键词。

支持情况：
  ✅ 江苏公共资源交易网  jsggzy.jszwfw.gov.cn   —— 静态 HTML，直接抓
  ✅ 安徽招标投标网      ahtba.org.cn           —— 尝试静态抓 + 接口兜底
  ⚠️ 采招网            *.bidcenter.com.cn      —— SPA + 需登录，自动抓不到正文，
                                                  需复用你浏览器登录后的 cookie（见 COOKIE_FILE）。

纯爬虫，不依赖任何大模型，关 VPN 也能跑。
"""
import re, json, pathlib
import requests
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()  # 政府站常用自签证书，verify=False 时静音告警

from app_paths import ROOT  # 打包后指向 exe 目录
COOKIE_FILE = ROOT / "bidcenter_cookies.txt"   # 可选：把采招网登录后的 Cookie 串放这（gitignored）

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

MAX_CHARS = 8000   # 截断，够正则/大模型提取面积造价即可


def _clean_text(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "head", "nav", "footer"]):
        tag.decompose()
    # 优先常见正文容器，找不到退回 body
    node = None
    for sel in ["#mainContent", ".article-content", ".detail-content", ".content",
                ".ewb-article", "#content", ".news_content", ".trade-detail"]:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 80:
            break
        node = None
    text = (node or soup.body or soup).get_text("\n", strip=True)
    text = text.replace("\xa0", " ").replace("　", " ")  # nbsp / 全角空格
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text[:MAX_CHARS]


def _host(url):
    m = re.search(r"https?://([^/]+)", url or "")
    return m.group(1).lower() if m else ""


def _load_cookies():
    if COOKIE_FILE.exists():
        raw = COOKIE_FILE.read_text(encoding="utf-8").strip()
        if raw:
            return raw
    return None


def fetch_detail(url, timeout=25):
    """返回 {ok, text, note, host}。ok=False 时 text 为空，note 说明原因。"""
    host = _host(url)
    if not url or not host:
        return {"ok": False, "text": "", "note": "无 detail_url", "host": host}

    # 采招网：SPA + 需登录，没有 cookie 抓不到正文
    if "bidcenter.com.cn" in host:
        cookie = _load_cookies()
        if not cookie:
            return {"ok": False, "text": "",
                    "note": "采招网需登录(SPA)，请把登录后的Cookie存到 bidcenter_cookies.txt 后重试",
                    "host": host}
        # 有 cookie 时尝试带 cookie 抓 hash 路由对应的页面（能力有限，作占位）
        try:
            h = dict(HEADERS); h["Cookie"] = cookie
            r = requests.get(url.split("#")[0], headers=h, timeout=timeout, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            txt = _clean_text(r.text)
            return {"ok": len(txt) > 120, "text": txt,
                    "note": "" if len(txt) > 120 else "带cookie仍未取到正文(可能纯前端渲染)", "host": host}
        except Exception as e:
            return {"ok": False, "text": "", "note": f"采招网抓取异常: {str(e)[:100]}", "host": host}

    # 公开静态站（江苏 jsggzy / 安徽 ahtba 等）：直接抓
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
        r.encoding = r.apparent_encoding or "utf-8"
        txt = _clean_text(r.text)
        if len(txt) > 120:
            return {"ok": True, "text": txt, "note": "", "host": host}
        return {"ok": False, "text": txt,
                "note": "正文过短(可能是动态渲染/跳转页)", "host": host}
    except Exception as e:
        return {"ok": False, "text": "", "note": f"抓取异常: {str(e)[:100]}", "host": host}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python fetch_detail.py <detail_url>")
        sys.exit(1)
    res = fetch_detail(sys.argv[1])
    print(f"host={res['host']}  ok={res['ok']}  note={res['note']}")
    print("-" * 60)
    # 终端编码兜底，避免 \xa0 等字符在 GBK 控制台报错
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(res["text"][:1500])
