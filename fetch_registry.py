# -*- coding: utf-8 -*-
"""
通用「新点(epoint)全文检索」抓取器 + 源注册表驱动
=============================================================
很多省市公共资源交易中心都跑同一套新点 inteligentsearch 后端（和已验证的江苏 jsggzy 同款）。
本模块把抓取逻辑做成「数据驱动」：要加一个省，只在 sources.json 加一行，不用写新爬虫。

源注册表 sources.json 里每条：
  id/name/region/home/api/category/id_prefix/status
  status: verified=已验证可抓 / candidate=候选待探测 / disabled=停用

用法：
  python fetch_registry.py                # 抓所有 verified 源（默认关键词 室内/装饰/装修/精装）
  python fetch_registry.py --kw 设计 装修 # 自定义关键词
  python fetch_registry.py --pages 3      # 每词翻 N 页（每页20）
  python fetch_registry.py --probe        # 探测所有 candidate 源，连通(能返回记录)的自动升为 verified
  python fetch_registry.py --only sdggzy  # 只跑指定源
  python fetch_registry.py --list         # 列出注册表
输出：data/reg_<id>_projects.json（字段与 parse_email 一致，run_radar 自动并入）。
"""
import re, sys, json, argparse, pathlib, urllib.parse, datetime

import parse_email as PE   # 复用 classify / is_design，全项目同口径
import keywords as KW       # 共享关键词库（含进化引擎发现的新词）
from app_paths import ROOT  # 打包后指向 exe 目录

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:    # 静音 verify=False 的 InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
REGISTRY = ROOT / "sources.json"
TODAY = datetime.date.today().isoformat()
DEFAULT_KEYWORDS = ["室内", "装饰", "装修", "精装"]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Content-Type": "application/json;charset=utf-8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CAT_KW = [
    ("采购意向", ["采购意向", "意向公开", "采购计划公开"]),   # 招标前的需求前置信号，最高优先
    ("中标候选人", ["中标候选人", "评标结果公示", "成交候选人", "中标候选"]),
    ("中标结果", ["中标公告", "中标结果", "成交公告", "成交结果", "中选公告"]),
    ("变更公告", ["变更", "更正", "澄清", "答疑", "终止", "废标", "流标"]),
    ("招标预告", ["预告", "预公告"]),
    ("采购信息", ["采购公告", "采购需求", "询价", "询比", "竞争性磋商",
                  "竞争性谈判", "单一来源", "比选"]),
    ("招标公告", ["招标公告", "资格预审", "邀请", "公开招标"]),
]


# ---------------- 注册表读写 ----------------
def load_registry():
    if not REGISTRY.exists():
        return {"version": 1, "sources": []}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def save_registry(reg):
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- 解析 ----------------
def classify_category(title):
    for cat, kws in CAT_KW:
        if any(k in title for k in kws):
            return cat
    return "招标公告"


def clean_title(t):
    return re.sub(r"\s+", " ", re.sub(r"</?em[^>]*>", "", t or "")).strip()


def record_to_project(rec, src):
    title = clean_title(rec.get("title") or rec.get("titlenew"))
    link = rec.get("linkurl") or ""
    detail = urllib.parse.urljoin(src["home"], link) if link else ""
    date = (rec.get("infodatepx") or rec.get("infodate") or "").split(" ")[0]
    if not date and link:                      # 部分源(如浙江)infodate为空，日期在链接路径 /YYYYMMDD/ 里
        md = re.search(r"/(\d{4})(\d{2})(\d{2})/", link)
        if md:
            date = f"{md.group(1)}-{md.group(2)}-{md.group(3)}"
    region = (rec.get("zhuanzai") or src.get("region") or "").strip()
    pfx = src.get("id_prefix") or src["id"]
    m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{20,})", link)
    pid = f"{pfx}_" + (m.group(1).replace("-", "") if m else
                       (str(rec.get("infoid") or "") or re.sub(r"\W+", "", title)[:28]))
    return {
        "id": pid,
        "title": title,
        "region": region,
        "category": classify_category(title),
        "pub_date": date,
        "detail_url": detail,
        "业务类型": PE.classify(title),
        "是否设计": PE.is_design(title),
        "来源": src["id"],
    }


# ---------------- 新点接口 ----------------
def call_epoint(src, keyword="", pn=0, rn=20, timeout=20):
    import requests
    param = {
        "token": "", "pn": pn, "rn": rn, "sdt": "", "edt": "",
        "wd": keyword, "inc_wd": "", "exc_wd": "", "fields": "title",
        "cnum": "001", "sort": '{"infodatepx":"0"}', "ssort": "title", "cl": 200,
        "terminal": "",
        "condition": [{"fieldName": "categorynum", "isLike": True,
                       "likeType": 2, "equal": src.get("category", "003")}],
        "time": None, "highlights": "title", "statistics": None,
        "unionCondition": None, "accuracy": "", "noParticiple": "1",
        "searchRange": None, "isBusiness": "1",
    }
    url = src["home"].rstrip("/") + src.get("api", "/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew")
    headers = dict(HEADERS, Referer=src["home"].rstrip("/") + "/")
    r = requests.post(url, headers=headers, data=json.dumps(param),
                      timeout=timeout, verify=False)
    r.encoding = "utf-8"
    return r.json()


def crawl_source(src, keywords, pages=2, rn=20):
    items, seen = [], set()
    for kw in keywords:
        for pg in range(pages):
            try:
                data = call_epoint(src, kw, pn=pg * rn, rn=rn)
            except Exception as e:
                print(f"   [{src['id']}] 关键词「{kw or '不限'}」第{pg+1}页失败：{str(e)[:90]}")
                break
            recs = (data.get("result") or {}).get("records") or []
            fresh = 0
            for rec in recs:
                p = record_to_project(rec, src)
                if p["id"] in seen:
                    continue
                seen.add(p["id"])
                items.append(p)
                fresh += 1
            print(f"   [{src['id']}] 「{kw or '不限'}」第{pg+1}页：返回{len(recs)} 新增{fresh}")
            if not recs:
                break
    return items


def probe_source(src):
    """探测候选源是否连通：能返回 ≥1 条记录即算通。返回 (ok, 条数)。"""
    try:
        data = call_epoint(src, "招标", pn=0, rn=5, timeout=15)
        recs = (data.get("result") or {}).get("records") or []
        return (len(recs) > 0, len(recs))
    except Exception as e:
        print(f"   [{src['id']}] 探测失败：{str(e)[:90]}")
        return (False, 0)


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser(description="通用新点抓取器（注册表驱动）")
    ap.add_argument("--kw", nargs="*", default=None, help="关键词，默认 室内/装饰/装修/精装")
    ap.add_argument("--pages", type=int, default=2, help="每词翻页数（每页20）")
    ap.add_argument("--only", default=None, help="只跑指定源 id")
    ap.add_argument("--probe", action="store_true", help="探测候选源，连通的自动升为 verified")
    ap.add_argument("--list", action="store_true", help="列出注册表")
    args = ap.parse_args()

    reg = load_registry()
    sources = reg.get("sources", [])

    if args.list:
        print(f"=== 源注册表（{len(sources)} 条）===")
        for s in sources:
            print(f"  [{s.get('status','?'):9}] {s['id']:10} {s.get('region','')}  {s['name']}  {s.get('home','')}")
        return

    if args.probe:
        cands = [s for s in sources if s.get("status") == "candidate"]
        if args.only:
            cands = [s for s in cands if s["id"] == args.only]
        print(f"=== 探测候选源 {len(cands)} 个 ===")
        promoted = 0
        for s in cands:
            ok, n = probe_source(s)
            if ok:
                s["status"] = "verified"
                promoted += 1
                print(f"  ✅ {s['id']} 连通（样本{n}条）→ 升级 verified")
            else:
                print(f"  ❌ {s['id']} 未连通，保持 candidate")
        save_registry(reg)
        print(f"\n=== 探测完成 ===  新转正 {promoted} 个；现 verified "
              f"{sum(1 for s in sources if s.get('status')=='verified')} 个。")
        return

    keywords = args.kw if args.kw else KW.load()
    targets = [s for s in sources if s.get("status") == "verified"
               and s.get("kind", "epoint") == "epoint"]
    if args.only:
        targets = [s for s in sources if s["id"] == args.only]
    print(f"=== 注册表抓取 {TODAY} ===  verified 源 {len(targets)} 个，关键词 {keywords}，每词{args.pages}页")
    print("（提示：须在中国境内网络运行；抓不到的源自动跳过，不影响其他源）")

    grand = 0
    for s in targets:
        print(f"\n· {s['name']}（{s['id']}）{s.get('home','')}")
        items = crawl_source(s, keywords, pages=args.pages)
        out = DATA / f"reg_{s['id']}_projects.json"
        out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        design = sum(1 for p in items if p["是否设计"])
        grand += len(items)
        print(f"  → {len(items)} 条（设计类 {design}）写入 {out.name}")

    print(f"\n=== 完成 ===  {len(targets)} 个源共抓 {grand} 条。跑 run_radar.py 即并入日报。")


if __name__ == "__main__":
    main()
