# -*- coding: utf-8 -*-
"""
江苏招标商机 抓取模块（在你本机 / 中国境内运行）—— 接口直连版
=============================================================
源：江苏省公共资源交易网  http://jsggzy.jszwfw.gov.cn   （省级公共资源交易平台）

为什么用这个源（而非 jszbtb.com）？
  jszbtb.com 是强 WAF，普通请求/无头浏览器都 403。
  jsggzy.jszwfw.gov.cn 是省级官方平台、工程建设招标公告齐全，且暴露标准的"新点全文
  检索接口"，普通 requests 即可直连——和安徽 ahtba 一样省心，还自带城市/日期字段。

实测接口（已验证返回真实数据）：
  POST {HOME}/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew
  Content-Type: application/json;charset=utf-8
  body 关键字段：
    wd        关键词（在 title 里全文检索），如 "装饰" "装修" "室内" "设计"
    fields    "title"
    condition [{"fieldName":"categorynum","isLike":true,"likeType":2,"equal":"003"}]
              003 = 工程建设交易（招标公告/中标结果等都在此树下）
    sort      {"infodatepx":"0"}   按发布时间降序
    pn / rn   起始行 / 每页条数
  返回 result.records[]，每条含：
    title(含<em>高亮，需去标签)、linkurl(详情相对路径)、infodatepx(日期)、
    zhuanzai(城市)、categorynum(分类号)

输出：data/jiangsu_projects.json，字段与 parse_email.py 一致，run_radar 自动并入。

用法：
  python fetch_jiangsu.py --show              # 按默认关键词(室内/装饰/装修/精装)搜
  python fetch_jiangsu.py --kw 设计 装修      # 自定义关键词
  python fetch_jiangsu.py --pages 3           # 每词翻3页(每页20)
  python fetch_jiangsu.py --all               # 不限关键词，抓最新工程公告(供核对)
  python fetch_jiangsu.py --debug             # dump 接口原始JSON到 data/
"""
import re, json, argparse, pathlib, urllib.parse, datetime

import parse_email as PE   # 复用 classify / is_design，全项目同口径

from app_paths import ROOT  # 打包后指向 exe 目录
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
TODAY = datetime.date.today().isoformat()

HOME = "http://jsggzy.jszwfw.gov.cn"
API = "/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"
CATEGORY = "003"                              # 工程建设交易（含招标公告/中标等）
DEFAULT_KEYWORDS = ["室内", "装饰", "装修", "精装"]   # 贴你的室内/装饰装修设计业务

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Content-Type": "application/json;charset=utf-8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": HOME + "/",
}

CAT_KW = [
    ("中标候选人", ["中标候选人", "评标结果公示", "成交候选人", "中标候选"]),
    ("中标结果", ["中标公告", "中标结果", "成交公告", "成交结果", "中选公告"]),
    ("变更公告", ["变更", "更正", "澄清", "答疑", "终止", "废标", "流标"]),
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


def clean_title(t):
    return re.sub(r"\s+", " ", re.sub(r"</?em[^>]*>", "", t or "")).strip()


def record_to_project(rec):
    title = clean_title(rec.get("title") or rec.get("titlenew"))
    link = rec.get("linkurl") or ""
    detail = urllib.parse.urljoin(HOME, link) if link else ""
    date = (rec.get("infodatepx") or rec.get("infodate") or "").split(" ")[0]
    region = (rec.get("zhuanzai") or "江苏").strip()
    # 稳定 id：优先 infoid / linkurl 里的 uuid
    m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{20,})", link)
    pid = "js_" + (m.group(1).replace("-", "") if m else
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
        "来源": "jsggzy",
    }


def call_api(keyword="", category=CATEGORY, pn=0, rn=20):
    import requests
    param = {
        "token": "", "pn": pn, "rn": rn, "sdt": "", "edt": "",
        "wd": keyword, "inc_wd": "", "exc_wd": "", "fields": "title",
        "cnum": "001", "sort": '{"infodatepx":"0"}', "ssort": "title", "cl": 200,
        "terminal": "",
        "condition": [{"fieldName": "categorynum", "isLike": True,
                       "likeType": 2, "equal": category}],
        "time": None, "highlights": "title", "statistics": None,
        "unionCondition": None, "accuracy": "", "noParticiple": "1",
        "searchRange": None, "isBusiness": "1",
    }
    r = requests.post(HOME + API, headers=HEADERS, data=json.dumps(param),
                      timeout=25, verify=False)
    r.encoding = "utf-8"
    return r.json(), r.text


def crawl(keywords, pages=2, rn=20, debug=False):
    all_items, seen = [], set()
    for kw in keywords:
        for pg in range(pages):
            try:
                data, raw = call_api(kw, pn=pg * rn, rn=rn)
            except Exception as e:
                print(f"   [接口] 关键词「{kw or '不限'}」第{pg+1}页失败：{str(e)[:120]}")
                break
            if debug:
                tag = re.sub(r"\W+", "", kw) or "all"
                (DATA / f"jiangsu_debug_{tag}_p{pg+1}.json").write_text(raw, encoding="utf-8")
            recs = (data.get("result") or {}).get("records") or []
            fresh = 0
            for rec in recs:
                p = record_to_project(rec)
                if p["id"] in seen:
                    continue
                seen.add(p["id"])
                all_items.append(p)
                fresh += 1
            print(f"   [接口] 关键词「{kw or '不限'}」第{pg+1}页：返回{len(recs)}条，新增{fresh}")
            if not recs:
                break
    return all_items


def main():
    ap = argparse.ArgumentParser(description="江苏公共资源交易网抓取（本机运行）")
    ap.add_argument("--kw", nargs="*", default=None, help="搜索关键词，默认 室内/装饰/装修/精装")
    ap.add_argument("--all", action="store_true", help="不限关键词，抓最新工程公告")
    ap.add_argument("--pages", type=int, default=2, help="每个关键词翻页数（每页20）")
    ap.add_argument("--debug", action="store_true", help="dump 接口原始JSON")
    ap.add_argument("--show", action="store_true", help="终端打印预览")
    args = ap.parse_args()

    keywords = [""] if args.all else (args.kw if args.kw else DEFAULT_KEYWORDS)
    print(f"=== 江苏招标抓取 {TODAY} ===  源：{HOME}")
    print(f"关键词：{keywords or '不限'}　每词{args.pages}页（工程建设交易 003）")
    print("（提示：须在中国境内网络运行）")

    projects = crawl(keywords, pages=args.pages, debug=args.debug)
    out = DATA / "jiangsu_projects.json"
    out.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
    design = [p for p in projects if p["是否设计"]]

    print(f"\n=== 完成 ===")
    print(f"共抓 {len(projects)} 条；其中设计类 {len(design)} 条 → {out}")
    if not projects:
        print("\n⚠️ 抓到 0 条：①接口/字段可能变了 → 加 --debug 把 data/jiangsu_debug_*.json 发我；"
              "②试 --all 验证连通。")
    if args.show and projects:
        print("\n预览：")
        for p in (design or projects)[:20]:
            flag = "设计✅" if p["是否设计"] else "非设计"
            print(f"  [{p['region']}] {p['业务类型']}/{p['category']}/{flag} "
                  f"{p['pub_date']} | {p['title'][:36]}")


if __name__ == "__main__":
    main()
