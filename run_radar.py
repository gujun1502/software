# -*- coding: utf-8 -*-
"""
Out Building Decision · 商机雷达（邮件版·完整闭环）
读 inbox 里的采招网邮件 → 解析项目 → 决策引擎打分 → 出排序决策日报(PDF)
中标结果单列为"竞争情报"。

注意：邮件只给到标题/地区/类型，资质/业绩/控制价等"废标级"要求在详情页里
（你的采招网账号可看）。所以本报告是"契合度初筛+排序"，最终投不投以详情页为准。
"""
import os, sys, subprocess, pathlib, datetime, json
import parse_email
import decision_engine as DE
import push_wechat
import rotation
from extract import extract_area, extract_cost, extract_keywords

from app_paths import ROOT  # 打包后指向 exe 目录
TODAY = datetime.date.today().isoformat()
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
ENRICH_FILE = DATA / "详情增强.json"
for d in (REPORTS, DATA):
    d.mkdir(exist_ok=True)

# 时间窗：收「标书发出日期」在最近 WINDOW_DAYS 天内的商机。
# 为什么不是"只收昨天+今天"：采招网定制邮件到达本机时，内容普遍已滞后 4~8 天
# （如 7月7日 收到的邮件装的是 6月29日~7月3日 的信息），2 天窗会把几乎全部
# 数据剔光（曾出现 6168 条只剩 1 条、日报 0 商机）。7 天窗刚好盖住邮件滞后。
# 另一条保留通道：只要「截标时间」还没过（详情增强抓到的），项目就仍可投——
# 发布得早不等于机会已失效。
WINDOW_DAYS = 7
WINDOW_START = datetime.date.today() - datetime.timedelta(days=WINDOW_DAYS)


def _parse_pub_date(s):
    """把 pub_date(形如 2026-06-11)解析成 date；解析不了返回 None。"""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s[:10])
    except ValueError:
        return None


def in_window(p, enrich=None):
    """发出日期在最近 WINDOW_DAYS 天内，或截标时间未过 → 保留。
    无日期(解析不出)的条目按保留处理。"""
    d = _parse_pub_date(p.get("pub_date"))
    if d is None or d >= WINDOW_START:
        return True
    # 发布早于窗口，但详情页抓到的截标时间还没过 → 仍是活商机，保留
    e = (enrich or {}).get(p.get("id") or "") or {}
    dl = _parse_pub_date(e.get("截标时间"))
    return dl is not None and dl >= datetime.date.today()


def filter_window(projects, enrich=None):
    """剔除发出日期早于窗口起点、且截标已过(或未知)的项目，返回(保留列表, 剔除数)。"""
    kept = [p for p in projects if in_window(p, enrich)]
    return kept, len(projects) - len(kept)


def attention(score):
    if score >= 55:
        return "⭐建议重点关注"
    if score >= 40:
        return "○可关注"
    return "·暂不关注"


def listing_badge(day):
    """上榜状态徽标：第1天=🆕新，第2天=2️⃣第2天(末日，明天下架)。"""
    return "🆕 新" if day <= 1 else "2️⃣ 第2天"


def load_enrichment():
    """读 enrich.py 抓详情页生成的增强缓存（面积/造价/关键词），按项目 id 索引。
    运行「更新数据」抓详情页后才会有；没有就回退到「标题识别」。"""
    if not ENRICH_FILE.exists():
        return {}
    try:
        return json.loads(ENRICH_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  (详情增强缓存读取失败，回退标题识别: {e})")
        return {}


def field_of(p, key, enrich, title_fallback):
    """优先用详情页增强值；没有/为空(—)再退回标题识别。"""
    e = enrich.get(p.get("id") or "") or {}
    v = (e.get(key) or "").strip()
    if v and v != "—":
        return v
    return title_fallback


def build_report(scored, results, filtered, enrich=None, intentions=None,
                 days_map=None, rot_stats=None):
    enrich = enrich or {}
    intentions = intentions or []
    days_map = days_map or {}
    rot_stats = rot_stats or {}
    enriched_n = sum(1 for p, _ in scored if (enrich.get(p.get("id") or "") or {}).get("ok"))
    L = [f"# 商机雷达决策日报 · {TODAY}", ""]
    L.append(f"> **设计类**可投商机 **{len(scored)}** 条　|　采购意向(需求前置) {len(intentions)} 条　|　"
             f"竞争情报 {len(results)} 条　|　已剔除非设计类 {len(filtered)} 条　|　已抓详情页补全 {enriched_n} 条")
    L.append("")

    # 一、可投商机排序：面积+控制价合并一格(上下排)，新增「标书发出/截标」一列
    L.append("## 一、可投商机 · 契合度排序")
    L.append("")
    if rot_stats:
        ok = "✅满足" if rot_stats.get("保证新增满足") else "⚠️不足(请运行更新/进化补新源)"
        L.append(f"> 🔄 **每日轮换**：本期上榜 **{rot_stats.get('上榜', len(scored))}** 条"
                 f"（🆕 全新 {rot_stats.get('新增', 0)} 条·2️⃣ 第2天 {rot_stats.get('第2天', 0)} 条），"
                 f"昨日满 2 天**自动下架 {rot_stats.get('下架', 0)} 条**。"
                 f"每天保证 ≥{rot_stats.get('MIN_NEW', 3)} 条全新：{ok}。")
        L.append("")
    L.append("> 单元格上下两行：「面积/控制价」= 上面积·下控制价；"
             "「标书发出/截标」= 上发布日·下投标截止。`—` 表示该项未取到。"
             "「上榜」列：🆕 新=今日首次出现；2️⃣ 第2天=明日起下架。")
    L.append("")
    L.append("| 名次 | 上榜 | 关注度 | 契合度 | 业务 | 地区 | 面积/控制价 | 标书发出/截标 | 关键词 | 项目 |")
    L.append("|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|---|")
    for i, (p, d) in enumerate(scored, 1):
        score = d["契合度"] if d["契合度"] is not None else 0
        title = p["title"].replace("|", "／")
        link = f"[{title}]({p['detail_url']})" if p.get("detail_url") else title
        area = field_of(p, "设计面积", enrich, extract_area(p["title"]))
        cost = field_of(p, "设计造价", enrich, extract_cost(p["title"]))
        deadline = field_of(p, "截标时间", enrich, "—")
        release = p.get("pub_date") or "—"
        area_cost = f"{area}<br>{cost}"          # 上：面积　下：控制价
        time_cell = f"{release}<br>{deadline}"    # 上：标书发出　下：截标
        kw = field_of(p, "关键词", enrich, extract_keywords(p["title"]))
        badge = listing_badge(days_map.get(p.get("id") or p.get("title"), 1))
        L.append(f"| {i} | {badge} | {attention(score)} | {score} | {p['业务类型']} "
                 f"| {p['region']} | {area_cost} | {time_cell} | {kw} | {link} |")
    L.append("")

    # 二、需求前置 · 采购意向公开（招标前几个月发布，最值钱的需求信号）
    if intentions:
        L.append("## 二、需求前置 · 采购意向公开")
        L.append("")
        L.append("> 这些是**招标前**发布的「谁要建/要改造什么」，比招标公告更早拿到，"
                 "便于提前接触业主。`—` 表示该项未取到。")
        L.append("")
        L.append("| 关注度 | 契合度 | 业务 | 地区 | 预算/面积 | 关键词 | 项目 |")
        L.append("|:--:|:--:|:--:|:--:|:--:|:--:|---|")
        for p, d in intentions:
            score = d["契合度"] if d["契合度"] is not None else 0
            title = p["title"].replace("|", "／")
            link = f"[{title}]({p['detail_url']})" if p.get("detail_url") else title
            cost = field_of(p, "设计造价", enrich, extract_cost(p["title"]))
            area = field_of(p, "设计面积", enrich, extract_area(p["title"]))
            kw = field_of(p, "关键词", enrich, extract_keywords(p["title"]))
            L.append(f"| {attention(score)} | {score} | {p['业务类型']} | {p['region']} "
                     f"| {cost}<br>{area} | {kw} | {link} |")
        L.append("")

    # 三、竞争情报（同样标出 造价 / 关键词，方便看价格规律）
    if results:
        L.append("## 三、竞争情报 · 近期同类中标结果")
        L.append("")
        L.append("> 这些是类似项目谁中了，用于判断对手与价格规律（第三期接入报价测算）。")
        L.append("")
        L.append("| 地区 | 业务 | 造价/中标价 | 关键词 | 项目 |")
        L.append("|:--:|:--:|:--:|:--:|---|")
        for p in results:
            title = p["title"].replace("|", "／")
            link = f"[{title}]({p['detail_url']})" if p.get("detail_url") else title
            cost = field_of(p, "设计造价", enrich, extract_cost(p["title"]))
            kw = field_of(p, "关键词", enrich, extract_keywords(p["title"]))
            L.append(f"| {p['region']} | {p['业务类型']} | {cost} | {kw} | {link} |")
        L.append("")

    # 四、说明与关注事项（注释统一挪到最后，正文更清爽）
    L.append("## 四、说明与关注事项")
    L.append("")
    L.append("> 🎯 **只保留「室内/装饰装修设计」类**——装饰装修工程、施工、供应商、"
             "材料采购、维修、监理等均已自动剔除（贵司只做设计）。")
    L.append("")
    L.append("> 📐 **面积 / 造价来源**：列表只给到「标题」，**设计面积·设计造价写在详情页里**。"
             "运行「更新数据并生成」会自动抓详情页、并由 MiniMax 大模型补全面积/造价/截标；"
             "未抓到的退回标题识别，`—` 表示标题与详情页都没取到，需人工打开详情页确认。")
    L.append("")
    L.append("> ⚠️ 邮件只含标题/地区/类型；**资质·业绩·控制价等「废标级」要求需打开详情页确认**"
             "（你的采招网账号可看）。本表为契合度初筛排序，帮你定「先看哪几个」。")
    L.append("")
    L.append(f"> 🕒 **时间窗（最近{WINDOW_DAYS}天 + 截标未过）**：所有板块、所有方向"
             f"(含银行/办公/酒店/民宿/私人银行/家办等)保留「标书发出日期」在 "
             f"**{WINDOW_START.isoformat()} 及以后**的；发布更早但**截标时间还没到**的也保留"
             "（机会未失效）。采招网邮件普遍滞后数天，故窗口取一周而非两天。"
             "无发出日期的条目一律保留，请打开详情页核对发布时间。")
    L.append("")
    L.append("> 🔎 **本期数据范围**：采招网定制邮件 + 江苏/安徽/湖南/四川/浙江等公共资源交易网抓取"
             "（每日自动重抓最近一周新公告）。特定业主(如某银行某分行)未出现时，"
             "可能发布在窗口外或走了其他平台，建议在采招网账号内直接搜索确认。")
    L.append("")
    L.append("---")
    L.append(f"*Out Building Decision · 邮件版商机雷达 · {TODAY}　决策仅供参考，最终由人拍板*")
    return "\n".join(L)


def push_summary(scored, results, filtered, days_map=None):
    """生成并推送微信文字摘要（TOP重点商机）。"""
    import json as _json
    days_map = days_map or {}
    n = _json.loads((ROOT / "push_config.json").read_text(encoding="utf-8")).get("top_n", 8) \
        if (ROOT / "push_config.json").exists() else 8
    title = f"商机雷达 {TODAY}：{len(scored)}条设计商机"
    lines = [f"### 📡 商机雷达 · {TODAY}",
             f"**设计类可投商机 {len(scored)} 条**　竞争情报 {len(results)} 条"
             f"　(已省略非设计 {len(filtered)} 条)", "",
             f"#### 重点关注 · 契合度 TOP{min(n, len(scored))}"]
    for i, (p, d) in enumerate(scored[:n], 1):
        score = d["契合度"] if d["契合度"] is not None else 0
        mark = "🆕" if days_map.get(p.get("id") or p.get("title"), 1) <= 1 else "2️⃣"
        lines.append(f"{i}. {mark} **[{score}]** {p['业务类型']}·{p['region']}　{p['title'][:26]}")
    lines.append("")
    lines.append("> 完整决策日报 PDF 在电脑 reports 文件夹。")
    push_wechat.push(title, "\n".join(lines))


def to_pdf(md):
    md_path = REPORTS / f"商机雷达日报_{TODAY}.md"
    pdf_path = REPORTS / f"商机雷达日报_{TODAY}.pdf"
    md_path.write_text(md, encoding="utf-8")
    try:
        try:
            from scripts import md_to_pdf_edge        # 包/打包模式（PyInstaller 可静态发现）
        except Exception:
            sys.path.insert(0, str(ROOT / "scripts"))
            import md_to_pdf_edge                      # 源码散装模式兜底
        md_to_pdf_edge.convert(md_path, pdf_path)   # 跨平台自动找浏览器
        return pdf_path
    except Exception as e:
        print("  (PDF生成失败，保留markdown:", e, ")")
    return md_path


def load_scraped(projects):
    """并入本机抓取的省级站商机（如安徽 ahjyztb），按 id/标题去重。
    这些文件由 fetch_ahjyztb.py 等在本机生成，schema 与邮件项目一致。"""
    seen = {p.get("id") or p["title"] for p in projects}
    merged = list(projects)
    for fp in sorted(DATA.glob("*_projects.json")):
        try:
            items = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  (跳过 {fp.name}: {e})")
            continue
        added = 0
        for p in items:
            key = p.get("id") or p.get("title")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(p)
            added += 1
        if added:
            print(f"  并入 {fp.name}: 新增 {added} 条")
    return merged


def open_file(path):
    """跨平台用系统默认程序打开文件（一键按钮生成后自动打开 PDF）。"""
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))                       # noqa: 仅 Windows
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as e:
        print(f"  (自动打开失败，请手动打开 {path}: {e})")


def main():
    print(f"=== 商机雷达(邮件版) {TODAY} ===")
    profile = DE.load_profile()
    projects = parse_email.parse_inbox(ROOT / "inbox")
    projects = load_scraped(projects)      # 合并本机抓取的省级站（安徽等）
    print(f"解析到 {len(projects)} 条项目")

    # 时间窗过滤：留「发出日期在最近一周」或「截标时间未过」的（其余剔除）
    enrich = load_enrichment()
    projects, dropped = filter_window(projects, enrich)
    print(f"时间窗筛选(发出日期 ≥ {WINDOW_START.isoformat()} 或截标未过)："
          f"剔除过旧 {dropped} 条，保留 {len(projects)} 条")

    bids_all = [p for p in projects if p["category"] in ("招标公告", "采购信息", "招标预告")]
    results_all = [p for p in projects if p["category"] in ("中标结果", "中标候选人")]
    intent_all = [p for p in projects if p["category"] == "采购意向"]

    # 只保留"设计"类（贵司只做室内/装饰装修设计）
    bids = [p for p in bids_all if p["是否设计"]]
    filtered = [p for p in bids_all if not p["是否设计"]]      # 非设计，剔除供核对
    results = [p for p in results_all if p["是否设计"]]        # 竞争情报也只看设计类
    intents = [p for p in intent_all if p["是否设计"]]         # 采购意向也只看设计类

    def score_all(items):
        out = []
        for p in items:
            proj = {"项目名称": p["title"], "项目类型": p["业务类型"], "业主": p["title"]}
            out.append((p, DE.decide(proj, profile)))
        out.sort(key=lambda x: -(x[1]["契合度"] or 0))
        return out

    scored = score_all(bids)
    scored_intent = score_all(intents)

    # 每日轮换/下架：连续上榜满 2 天的第 3 天移除，保证每天有新商机进来
    scored, dropped_rot, rot_stats, days_map = rotation.apply_rotation(scored)
    print(f"轮换下架：上榜 {rot_stats['上榜']} 条（全新 {rot_stats['新增']}·第2天 "
          f"{rot_stats['第2天']}），满2天下架 {rot_stats['下架']} 条")
    if not rot_stats["保证新增满足"]:
        print(f"  ⚠️ 今日全新商机仅 {rot_stats['新增']} 条 < 保证值 {rot_stats['MIN_NEW']} 条；"
              f"建议运行『更新数据』或『进化(扩词/探新源)』补充新源。")

    # 存竞争情报到历史中标库
    win_db = DATA / "历史中标.json"
    existing = json.loads(win_db.read_text(encoding="utf-8")) if win_db.exists() else []
    seen = {w.get("id") for w in existing}
    for p in results:
        if p["id"] not in seen:
            existing.append(p)
    win_db.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    md = build_report(scored, results, filtered, enrich, scored_intent,
                      days_map=days_map, rot_stats=rot_stats)
    out = to_pdf(md)
    try:
        push_summary(scored, results, filtered, days_map)
    except Exception as e:
        print("  (微信推送出错，不影响报告:", e, ")")
    print(f"\n=== 完成 ===")
    print(f"设计类可投商机 {len(scored)} 条｜采购意向 {len(scored_intent)} 条｜"
          f"竞争情报 {len(results)} 条｜已剔除非设计类 {len(filtered)} 条（累计中标入库 {len(existing)}）")
    print(f"决策日报：{out}")
    if scored:
        print("\n契合度前5：")
        for p, d in scored[:5]:
            print(f"  {d['契合度']:>5} | {p['业务类型']} | {p['title'][:30]}")
    if "--open" in sys.argv:        # 一键按钮：生成后自动用默认程序打开 PDF
        open_file(out)


if __name__ == "__main__":
    main()
