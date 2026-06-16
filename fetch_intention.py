# -*- coding: utf-8 -*-
"""
政府采购意向公开 抓取（需求前置信号）—— 中国政府采购网 ccgp
=============================================================
「采购意向公开」是招标前几个月发布的「谁要建/要改造什么」，是最值钱的需求前置信号。
来源：中国政府采购网全文检索 search.ccgp.gov.cn/bxsearch（公开 HTML 列表）。

特点与边界（务必知道）：
  · ccgp 有反爬，可能返回 412/空页/需 JS。本脚本尽力直连，抓不到就**优雅跳过**，
    不影响整体流程；抓到多少算多少。
  · 输出 data/reg_ccgp_intention_projects.json，category=采购意向，run_radar 单列一节。

用法：
  python fetch_intention.py                 # 默认关键词(室内/装饰/装修/改造/精装)
  python fetch_intention.py --kw 装修 改造  # 自定义
  python fetch_intention.py --days 90       # 时间窗口(默认近90天)
  python fetch_intention.py --pages 2       # 每词翻页
"""
import re, sys, json, argparse, datetime, urllib.parse

import parse_email as PE
import keywords as KW
from app_paths import ROOT

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
TODAY = datetime.date.today()
DEFAULT_KEYWORDS = ["室内", "装饰", "装修", "改造", "精装"]

SEARCH = "http://search.ccgp.gov.cn/bxsearch"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://www.ccgp.gov.cn/",
}


def _stamp(s):
    return re.sub(r"\W+", "", s)[:28]


def parse_list_html(html, kw):
    """从 bxsearch 结果页粗解析：每条 <li> 里有 <a href> 标题、<span>发布时间。
    只保留标题含「意向」的（采购意向公开）。"""
    items = []
    # 结果块通常是 <ul class="vT-srch-result-list-bid"> 下若干 <li>
    for li in re.findall(r"<li[^>]*>(.*?)</li>", html, flags=re.S):
        m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', li, flags=re.S)
        if not m:
            continue
        url = m.group(1).strip()
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        title = re.sub(r"\s+", " ", title)
        if not title or ("意向" not in title and "意向" not in li):
            continue
        dm = re.search(r"(20\d{2}[.\-/年]\d{1,2}[.\-/月]\d{1,2})", li)
        date = re.sub(r"[年月]", "-", dm.group(1)).rstrip("-").replace(".", "-") if dm else ""
        items.append({"title": title, "url": url, "date": date})
    return items


def crawl(keywords, days=90, pages=1):
    import requests
    end = TODAY
    start = TODAY - datetime.timedelta(days=days)
    out, seen = [], set()
    for kw in keywords:
        for pg in range(1, pages + 1):
            params = {
                "searchtype": 1, "page_index": pg, "bidSort": 0,
                "kw": kw, "pinMu": 0, "bidType": 0, "dbselect": "bidx",
                "start_time": start.strftime("%Y:%m:%d"),
                "end_time": end.strftime("%Y:%m:%d"),
                "timeType": 6, "displayZone": "", "zoneId": "",
                "pppStatus": 0, "agentName": "",
            }
            try:
                r = requests.get(SEARCH, params=params, headers=HEADERS, timeout=20)
                r.encoding = "utf-8"
                rows = parse_list_html(r.text, kw)
            except Exception as e:
                print(f"   [ccgp] 「{kw}」第{pg}页失败：{str(e)[:90]}")
                break
            fresh = 0
            for row in rows:
                title = row["title"]
                pid = "ccgp_" + _stamp(title)
                if pid in seen:
                    continue
                seen.add(pid)
                detail = urllib.parse.urljoin("http://www.ccgp.gov.cn/", row["url"])
                out.append({
                    "id": pid, "title": title,
                    "region": "全国", "category": "采购意向",
                    "pub_date": row["date"] or "", "detail_url": detail,
                    "业务类型": PE.classify(title), "是否设计": PE.is_design(title),
                    "来源": "ccgp采购意向",
                })
                fresh += 1
            print(f"   [ccgp] 「{kw}」第{pg}页：意向 {len(rows)} 新增 {fresh}")
            if not rows:
                break
    return out


def main():
    ap = argparse.ArgumentParser(description="政府采购意向公开抓取（ccgp，尽力直连）")
    ap.add_argument("--kw", nargs="*", default=None)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--pages", type=int, default=1)
    args = ap.parse_args()
    kws = args.kw if args.kw else KW.load()

    print(f"=== 政府采购意向抓取 {TODAY.isoformat()} ===  近{args.days}天，关键词 {kws}")
    print("（提示：ccgp 有反爬，抓不到会优雅跳过，不影响其他流程）")
    items = crawl(kws, days=args.days, pages=args.pages)
    design = [p for p in items if p["是否设计"]]
    out = DATA / "reg_ccgp_intention_projects.json"
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 完成 ===  采购意向 {len(items)} 条（设计类 {len(design)}）→ {out.name}")
    if not items:
        print("  本次未抓到（ccgp 反爬或窗口内无匹配）。结构已就绪，可换网络/关 VPN 再试。")


if __name__ == "__main__":
    main()
