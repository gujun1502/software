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
from extract import extract_area, extract_cost, extract_keywords

from app_paths import ROOT  # 打包后指向 exe 目录
TODAY = datetime.date.today().isoformat()
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
ENRICH_FILE = DATA / "详情增强.json"
for d in (REPORTS, DATA):
    d.mkdir(exist_ok=True)


def attention(score):
    if score >= 55:
        return "⭐建议重点关注"
    if score >= 40:
        return "○可关注"
    return "·暂不关注"


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


def build_report(scored, results, filtered, enrich=None):
    enrich = enrich or {}
    enriched_n = sum(1 for p, _ in scored if (enrich.get(p.get("id") or "") or {}).get("ok"))
    L = [f"# 商机雷达决策日报 · {TODAY}", ""]
    L.append(f"> **设计类**可投商机 **{len(scored)}** 条　|　竞争情报 {len(results)} 条　|　"
             f"已剔除非设计类 {len(filtered)} 条　|　已抓详情页补全 {enriched_n} 条")
    L.append("")

    # 一、可投商机排序：面积+控制价合并一格(上下排)，新增「标书发出/截标」一列
    L.append("## 一、可投商机 · 契合度排序")
    L.append("")
    L.append("> 单元格上下两行：「面积/控制价」= 上面积·下控制价；"
             "「标书发出/截标」= 上发布日·下投标截止。`—` 表示该项未取到。")
    L.append("")
    L.append("| 名次 | 关注度 | 契合度 | 业务 | 地区 | 面积/控制价 | 标书发出/截标 | 关键词 | 项目 |")
    L.append("|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|---|")
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
        L.append(f"| {i} | {attention(score)} | {score} | {p['业务类型']} "
                 f"| {p['region']} | {area_cost} | {time_cell} | {kw} | {link} |")
    L.append("")

    # 二、竞争情报（同样标出 造价 / 关键词，方便看价格规律）
    if results:
        L.append("## 二、竞争情报 · 近期同类中标结果")
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

    # 三、说明与关注事项（注释统一挪到最后，正文更清爽）
    L.append("## 三、说明与关注事项")
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
    L.append("> 🔎 **本期数据范围**：采招网定制邮件 + 江苏/安徽公共资源交易网抓取。"
             "检索「中国银行」仅命中：**武汉江夏支行**（已列入第1位）、**陕西省分行**"
             "（供应商选型入围，非设计已剔除）；**未发现「中国银行徐州分行」装修设计项目**——"
             "不在本期邮件与抓取范围内（可能发布时间在窗口外或走了其他平台，建议在采招网账号内直接搜索确认）。")
    L.append("")
    L.append("---")
    L.append(f"*Out Building Decision · 邮件版商机雷达 · {TODAY}　决策仅供参考，最终由人拍板*")
    return "\n".join(L)


def push_summary(scored, results, filtered):
    """生成并推送微信文字摘要（TOP重点商机）。"""
    import json as _json
    n = _json.loads((ROOT / "push_config.json").read_text(encoding="utf-8")).get("top_n", 8) \
        if (ROOT / "push_config.json").exists() else 8
    title = f"商机雷达 {TODAY}：{len(scored)}条设计商机"
    lines = [f"### 📡 商机雷达 · {TODAY}",
             f"**设计类可投商机 {len(scored)} 条**　竞争情报 {len(results)} 条"
             f"　(已省略非设计 {len(filtered)} 条)", "",
             f"#### 重点关注 · 契合度 TOP{min(n, len(scored))}"]
    for i, (p, d) in enumerate(scored[:n], 1):
        score = d["契合度"] if d["契合度"] is not None else 0
        lines.append(f"{i}. **[{score}]** {p['业务类型']}·{p['region']}　{p['title'][:26]}")
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

    bids_all = [p for p in projects if p["category"] in ("招标公告", "采购信息", "招标预告")]
    results_all = [p for p in projects if p["category"] in ("中标结果", "中标候选人")]

    # 只保留"设计"类（贵司只做室内/装饰装修设计）
    bids = [p for p in bids_all if p["是否设计"]]
    filtered = [p for p in bids_all if not p["是否设计"]]      # 非设计，剔除供核对
    results = [p for p in results_all if p["是否设计"]]        # 竞争情报也只看设计类

    scored = []
    for p in bids:
        proj = {"项目名称": p["title"], "项目类型": p["业务类型"], "业主": p["title"]}
        d = DE.decide(proj, profile)
        scored.append((p, d))
    scored.sort(key=lambda x: -(x[1]["契合度"] or 0))

    # 存竞争情报到历史中标库
    win_db = DATA / "历史中标.json"
    existing = json.loads(win_db.read_text(encoding="utf-8")) if win_db.exists() else []
    seen = {w.get("id") for w in existing}
    for p in results:
        if p["id"] not in seen:
            existing.append(p)
    win_db.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    enrich = load_enrichment()
    md = build_report(scored, results, filtered, enrich)
    out = to_pdf(md)
    try:
        push_summary(scored, results, filtered)
    except Exception as e:
        print("  (微信推送出错，不影响报告:", e, ")")
    print(f"\n=== 完成 ===")
    print(f"设计类可投商机 {len(scored)} 条｜竞争情报 {len(results)} 条｜"
          f"已剔除非设计类 {len(filtered)} 条（累计中标入库 {len(existing)}）")
    print(f"决策日报：{out}")
    if scored:
        print("\n契合度前5：")
        for p, d in scored[:5]:
            print(f"  {d['契合度']:>5} | {p['业务类型']} | {p['title'][:30]}")
    if "--open" in sys.argv:        # 一键按钮：生成后自动用默认程序打开 PDF
        open_file(out)


if __name__ == "__main__":
    main()
