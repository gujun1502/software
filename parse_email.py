# -*- coding: utf-8 -*-
"""解析采招网定制邮件HTML → 项目列表（地区/标题/类型/详情链接/日期/业务分类）。"""
import re, urllib.parse, pathlib
from bs4 import BeautifulSoup

# 业务类型分类（顺序有讲究：私人银行/家办先于银行，避免被归成普通银行；
# 银行优先于办公，避免"银行办公楼"被归成办公；民宿先于酒店，避免"度假民宿"被归成酒店；
# 私人/别墅、文旅康养、私人银行/家办为新拓展方向）
TYPE_KW = [
    ("私人银行/家办", ["私人银行", "私行", "家族办公室", "家办", "财富管理中心",
                    "私人财富", "财富中心", "私人银行中心"]),
    ("银行", ["银行", "农商", "农村商业银行", "信用社", "村镇银行", "信用联社"]),
    ("证券", ["证券"]),
    ("保险", ["保险", "人寿", "财险", "太平洋保险"]),
    ("金融", ["金融", "基金", "信托", "期货", "财富"]),
    ("民宿", ["民宿", "客栈", "农家乐", "乡村民宿", "田园民宿"]),
    ("私人/别墅", ["别墅", "私宅", "私人住宅", "豪宅", "大平层", "自建房",
                "私人会所", "会所", "私人定制", "私人投资", "样板房", "售楼处"]),
    ("文旅康养", ["文旅", "康养", "田园综合体", "特色小镇", "乡村振兴", "营地", "露营"]),
    ("酒店", ["酒店", "宾馆", "希尔顿", "度假", "温泉酒店", "度假村"]),
    ("展厅", ["展厅", "展示中心", "汽车展厅", "4S店", "4s店", "展销", "体验中心"]),
    ("科技研发", ["研发中心", "总部研发", "科技总部", "科创", "研发楼", "实验楼", "孵化"]),
    ("厂房", ["厂房", "车间", "产业园", "工业园", "标准厂房", "通用厂房"]),
    ("商业", ["商业综合体", "购物中心", "商业广场", "商场", "万达", "商业空间"]),
    ("办公", ["办公", "写字楼", "机关", "政府", "营业厅", "营业部", "网点", "支行"]),
]
CATEGORIES = ["招标公告", "中标结果", "采购信息", "招标预告",
              "变更公告", "中标候选人", "招标预公告"]


def classify(title):
    for t, kws in TYPE_KW:
        if any(k in title for k in kws):
            return t
    return "其他"


# 我方只做室内/装饰装修「设计」，不做工程/施工/供货/材料
# 「方案征集/设计竞赛/概念方案」是纯设计类商机的常见标题写法，之前因不含"设计"二字被漏掉；
# 软装/美陈属设计邻接业务，一并纳入（个别制作安装类会混入，由人工在日报里略过）。
DESIGN_WORDS = ["设计", "方案设计", "室内设计", "装修设计", "装饰设计",
                "施工图设计", "深化设计", "效果图",
                "方案征集", "设计竞赛", "概念方案", "软装", "美陈"]
NON_DESIGN_WORDS = ["供应商", "供货", "材料", "询价采购", "家具采购",
                    "施工总承包", "维修保养", "监理", "造价"]


def is_design(title):
    """判定是否属于'设计'类（我方业务）。规则：含'设计'类词；
    若只含工程/施工/供货/材料等且无'设计'，则非我方业务。"""
    has_design = any(w in title for w in DESIGN_WORDS)
    if not has_design:
        return False
    # 含设计但同时是'供应商/材料/询价采购/监理'这类，仍视为非设计采买
    if any(w in title for w in ["供应商", "供货", "材料", "询价采购", "家具采购"]):
        return False
    return True


def _real_url(href):
    m = re.search(r"[?&]url=([^&]+)", href or "")
    return urllib.parse.unquote(m.group(1)) if m else (href or "")


def parse_email_html(html):
    soup = BeautifulSoup(html, "lxml")
    projects = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        decoded = urllib.parse.unquote(href)
        if "customDesBx" not in decoded:           # 只认标题链接
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        pid = None
        m = re.search(r"customDesBx/(\d+)", decoded)
        if m:
            pid = m.group(1)
        row = a.find_parent("tr")
        region, category, date = "", "", ""
        if row:
            tds = row.find_all("td")
            if tds:
                mr = re.search(r"\[([^\]]+)\]", tds[0].get_text())
                region = mr.group(1) if mr else ""
            rowtext = row.get_text(" ", strip=True)
            for a2 in row.find_all("a"):
                t2 = a2.get_text(strip=True)
                if t2 in CATEGORIES:
                    category = t2
                    break
            md = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", rowtext)
            if md:
                date = f"{md.group(1)}-{int(md.group(2)):02d}-{int(md.group(3)):02d}"
        projects.append({
            "id": pid, "title": title, "region": region,
            "category": category or "招标公告", "pub_date": date,
            "detail_url": _real_url(href), "业务类型": classify(title),
            "是否设计": is_design(title),
        })
    return projects


def _date_from_filename(name):
    """采招网邮件行内无日期，从文件名「您定制的06月11日…」推出标书发出日期(近似)。
    年份取文件名开头的 20xx（收件日），无则留空。"""
    ym = re.search(r"(20\d{2})", name)
    md = re.search(r"(\d{1,2})月(\d{1,2})日", name)
    if md:
        year = ym.group(1) if ym else ""
        if year:
            return f"{year}-{int(md.group(1)):02d}-{int(md.group(2)):02d}"
    return ""


def parse_inbox(inbox_dir):
    """解析 inbox 下所有采招网邮件，按项目ID去重。"""
    seen, out = set(), []
    for fp in sorted(pathlib.Path(inbox_dir).glob("*.html")):
        file_date = _date_from_filename(fp.name)
        for p in parse_email_html(fp.read_text(encoding="utf-8")):
            key = p["id"] or p["title"]
            if key in seen:
                continue
            seen.add(key)
            p["来源邮件"] = fp.name
            if not p.get("pub_date"):          # 行内无日期 → 用邮件主题日期近似
                p["pub_date"] = file_date
            out.append(p)
    return out


if __name__ == "__main__":
    import sys
    items = parse_inbox(pathlib.Path(__file__).resolve().parent / "inbox")
    print(f"共解析 {len(items)} 条（去重后）")
    from collections import Counter
    print("按类别:", dict(Counter(p["category"] for p in items)))
    print("按业务:", dict(Counter(p["业务类型"] for p in items)))
    print("\n示例前8条:")
    for p in items[:8]:
        print(f"  [{p['region']}] {p['业务类型']}/{p['category']} | {p['title'][:34]}")
