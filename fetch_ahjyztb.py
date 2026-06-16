# -*- coding: utf-8 -*-
"""
安徽招标投标信息网 抓取模块（在你本机 / 中国境内运行）
====================================================

数据源（已实测可用）：安徽省招标投标信息网  https://www.ahtba.org.cn
  （你最初给的 www.ahjyztb.gov.cn 在本机 DNS 解析失败；ahtba.org.cn 是同一来源、
   省招标采购协会主办，实测能抓到公告。如你确认 ahjyztb 的可用地址，改 HOME 即可。）

核心做法（实测接口，最稳）：
  直接 POST 它的列表接口，按关键词搜"设计"标——一步到位拿到你要的设计类商机：
    POST {HOME}/site/trade/affiche/pageList
    Content-Type: application/json
    body: {"afficheTitle":"设计","tradeType":"","afficheType":"",
           "regionCode":"","publishTimeType":"","afficheSourceType":"",
           "tradeClassify":"","pageNum":1,"pageSize":20}
    返回：列表 HTML 片段，每条在 <div class="titBox"> 内：
          .tit a[href=/site/trade/affiche/detail/...]  → 标题+详情链接
          .nums                                        → 发布日期
  这是普通 AJAX 接口，requests 即可，无需 Playwright。

输出：data/ahjyztb_projects.json，字段与 parse_email.py 完全一致，
      可被 run_radar.py 的 load_scraped() 自动并入每日雷达。

用法：
  python fetch_ahjyztb.py                  # 按默认关键词(设计/装饰装修)搜，输出JSON
  python fetch_ahjyztb.py --kw 设计 装修   # 自定义关键词
  python fetch_ahjyztb.py --pages 3        # 每个关键词翻3页
  python fetch_ahjyztb.py --all            # 不限关键词，抓最新全部公告(供核对)
  python fetch_ahjyztb.py --show           # 终端打印预览
  python fetch_ahjyztb.py --debug          # dump 接口返回片段到 data/ 供排查
"""
import re, json, argparse, pathlib, urllib.parse, datetime

import parse_email as PE   # 复用业务分类(classify)与是否设计(is_design)，全项目同口径

from app_paths import ROOT  # 打包后指向 exe 目录
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
TODAY = datetime.date.today().isoformat()

HOME = "https://www.ahtba.org.cn"           # 实测可用；如有 ahjyztb 可用域名改这里
PAGELIST_API = "/site/trade/affiche/pageList"
LIST_PAGE = "/site/trade/affiche/gotoTradeList"
# 你只做室内/装饰装修设计，所以用这些贴身关键词，而不是宽泛的"设计"
# （宽泛"设计"会把高速公路/水利/农田等市政基建设计全捞进来）。
# 想抓更广可加 --kw 设计 装修 室内 ...
DEFAULT_KEYWORDS = ["室内", "装饰", "装修", "精装"]
# 安徽16个地级市，用于干净地识别地区（避免从标题里截出错误片段）
AH_CITIES = ["合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆",
             "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": HOME + LIST_PAGE,
}

# 公告类型识别（与 parse_email.CATEGORIES 同口径）
CAT_KW = [
    ("中标候选人", ["中标候选人", "评标结果公示", "成交候选人", "中标候选"]),
    ("中标结果", ["中标公告", "中标结果", "成交公告", "成交结果", "中选公告"]),
    ("变更公告", ["变更", "更正", "澄清", "答疑", "终止", "废标流标"]),
    ("招标预告", ["预告", "预公告"]),
    ("采购信息", ["采购公告", "采购需求", "询价", "询比", "竞争性磋商",
                  "竞争性谈判", "单一来源", "比选"]),
    ("招标公告", ["招标公告", "资格预审", "邀请", "公开招标"]),
]


def classify_category(title):
    for cat, kws in CAT_KW:
        if any(k in title for k in kws):
            return cat
    return "招标公告"


def extract_region(text):
    """干净地取地区：先[地区]/【】，再命中16个地级市，再独立的 XX县/区，否则'安徽'。"""
    m = re.search(r"[\[【]\s*([^\]】]{2,12}?)\s*[\]】]", text)
    if m:
        cand = m.group(1).strip()
        # 括号里若是公告/状态词（重发、变更、第二次…）不是地区，跳过往下找
        if not re.search(r"公告|公示|结果|变更|重发|招标|采购|第.次|流标|终止|更正", cand):
            return cand
    for c in AH_CITIES:                 # 地级市名唯一，直接命中最稳
        if c in text:
            return c + "市"
    # 县/区：要求前面不是汉字，避免从'高速公路和县'这种里截错
    m = re.search(r"(?:^|[^一-龥])([一-龥]{2,3}[县区])", text)
    return m.group(1) if m else "安徽"


def extract_date(text):
    m = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text or "")
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def make_project(title, href, date, home):
    title = re.sub(r"\s+", " ", title).strip()
    detail = urllib.parse.urljoin(home, href) if href else ""
    # 详情链接里的 uuid 做稳定 id；与邮件源 id 不冲突
    m = re.search(r"/(?:detail|contryDetail)/([0-9a-f\-]{8,})", detail)
    pid = ("ah_" + m.group(1).replace("-", "")) if m else ("ah_" + re.sub(r"\W+", "", title)[:32])
    return {
        "id": pid,
        "title": title,
        "region": extract_region(title),
        "category": classify_category(title),
        "pub_date": date or "",
        "detail_url": detail,
        "业务类型": PE.classify(title),
        "是否设计": PE.is_design(title),
        "来源": "ahtba",
    }


# ---------------------------------------------------------------------------
# 精确解析 pageList 返回的 HTML 片段：只认真正的公告条目，过滤左侧机构排行等噪声
# ---------------------------------------------------------------------------
def parse_list_fragment(html, home):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for box in soup.select(".titBox"):
        a = box.select_one(".tit a[href]") or box.select_one("a[href]")
        if not a:
            continue
        href = a.get("href", "")
        if "/affiche/detail/" not in href and "/affiche/contryDetail/" not in href:
            continue  # 只要真正的公告详情链接
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        nums = box.select_one(".nums")
        date = extract_date(nums.get_text()) if nums else extract_date(box.get_text())
        p = make_project(title, href, date, home)
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# 调它的 pageList 接口（requests POST JSON）
# ---------------------------------------------------------------------------
def call_pagelist(keyword="", pages=2, page_size=20, debug=False):
    import requests
    url = HOME + PAGELIST_API
    items, seen = [], set()
    for pg in range(1, pages + 1):
        payload = {
            "tradeType": "", "tradeClassify": "", "afficheType": "",
            "publishTimeType": "", "regionCode": "", "afficheSourceType": "",
            "afficheTitle": keyword, "pageNum": pg, "pageSize": page_size,
        }
        try:
            r = requests.post(url, json=payload, headers=HEADERS, timeout=25)
            r.encoding = r.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"   [接口] 第{pg}页请求失败：{str(e)[:120]}")
            break
        if debug:
            tag = re.sub(r"\W+", "", keyword) or "all"
            (DATA / f"ahjyztb_debug_{tag}_p{pg}.html").write_text(r.text, encoding="utf-8")
        page_items = parse_list_fragment(r.text, HOME)
        fresh = [p for p in page_items if p["id"] not in seen]
        for p in fresh:
            seen.add(p["id"])
        items += fresh
        print(f"   [接口] 关键词「{keyword or '不限'}」第{pg}页：本页{len(page_items)}条，新增{len(fresh)}")
        if not page_items:
            break   # 没有更多了
    return items


def crawl(keywords, pages=2, debug=False):
    all_items, seen = [], set()
    for kw in keywords:
        for p in call_pagelist(kw, pages=pages, debug=debug):
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            all_items.append(p)
    return all_items


def main():
    ap = argparse.ArgumentParser(description="安徽招标投标信息网抓取（本机运行）")
    ap.add_argument("--kw", nargs="*", default=None, help="搜索关键词，默认 设计/装饰装修")
    ap.add_argument("--all", action="store_true", help="不限关键词，抓最新全部公告")
    ap.add_argument("--pages", type=int, default=2, help="每个关键词翻页数")
    ap.add_argument("--debug", action="store_true", help="dump 接口返回片段")
    ap.add_argument("--show", action="store_true", help="终端打印预览")
    args = ap.parse_args()

    keywords = [""] if args.all else (args.kw if args.kw else DEFAULT_KEYWORDS)
    print(f"=== 安徽招标抓取 {TODAY} ===  源：{HOME}")
    print(f"关键词：{keywords or '不限'}　每词{args.pages}页")
    print("（提示：须在中国境内网络运行；境外IP会被拦）")

    projects = crawl(keywords, pages=args.pages, debug=args.debug)

    out = DATA / "ahjyztb_projects.json"
    out.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
    design = [p for p in projects if p["是否设计"]]

    print(f"\n=== 完成 ===")
    print(f"共抓 {len(projects)} 条；其中设计类 {len(design)} 条 → {out}")
    if not projects:
        print("\n⚠️ 抓到 0 条。可能：①接口或字段变了 → 加 --debug 把 data/ahjyztb_debug_*.html 发我；"
              "②该关键词近期确无公告 → 试 --all 看是否能抓到任意公告验证连通。")
    if args.show and projects:
        print("\n预览：")
        for p in (design or projects)[:20]:
            flag = "设计✅" if p["是否设计"] else "非设计"
            print(f"  [{p['region']}] {p['业务类型']}/{p['category']}/{flag} "
                  f"{p['pub_date']} | {p['title'][:36]}")


if __name__ == "__main__":
    main()
