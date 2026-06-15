# -*- coding: utf-8 -*-
"""
Out Building Decision · 商机雷达（邮件版·完整闭环）
读 inbox 里的采招网邮件 → 解析项目 → 决策引擎打分 → 出排序决策日报(PDF)
中标结果单列为"竞争情报"。

注意：邮件只给到标题/地区/类型，资质/业绩/控制价等"废标级"要求在详情页里
（你的采招网账号可看）。所以本报告是"契合度初筛+排序"，最终投不投以详情页为准。
"""
import sys, subprocess, pathlib, datetime, json
import parse_email
import decision_engine as DE
import push_wechat

ROOT = pathlib.Path(__file__).resolve().parent
TODAY = datetime.date.today().isoformat()
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
for d in (REPORTS, DATA):
    d.mkdir(exist_ok=True)


def attention(score):
    if score >= 55:
        return "⭐建议重点关注"
    if score >= 40:
        return "○可关注"
    return "·暂不关注"


def build_report(scored, results, filtered):
    L = [f"# 商机雷达决策日报 · {TODAY}", ""]
    L.append(f"> 来源：采招网定制邮件　|　**设计类**可投商机 **{len(scored)}** 条　|　"
             f"竞争情报 {len(results)} 条　|　已剔除非设计类 {len(filtered)} 条")
    L.append("")
    L.append("> 🎯 **只保留「室内/装饰装修设计」类**——装饰装修工程、施工、供应商、"
             "材料采购、维修、监理等均已自动剔除（贵司只做设计）。")
    L.append("")
    L.append("> ⚠️ 邮件只含标题/地区/类型；**资质·业绩·控制价等「废标级」要求需打开详情页确认**"
             "（你的采招网账号可看）。本表为契合度初筛排序，帮你定「先看哪几个」。")
    L.append("")

    # 一、可投商机排序
    L.append("## 一、可投商机 · 契合度排序")
    L.append("")
    L.append("| 名次 | 关注度 | 契合度 | 业务 | 地区 | 项目 |")
    L.append("|:--:|:--:|:--:|:--:|:--:|---|")
    for i, (p, d) in enumerate(scored, 1):
        score = d["契合度"] if d["契合度"] is not None else 0
        title = p["title"].replace("|", "／")
        link = f"[{title}]({p['detail_url']})" if p.get("detail_url") else title
        L.append(f"| {i} | {attention(score)} | {score} | {p['业务类型']} "
                 f"| {p['region']} | {link} |")
    L.append("")

    # 二、竞争情报
    if results:
        L.append("## 二、竞争情报 · 近期同类中标结果")
        L.append("")
        L.append("> 这些是类似项目谁中了，用于判断对手与价格规律（第三期接入报价测算）。")
        L.append("")
        L.append("| 地区 | 业务 | 项目 |")
        L.append("|:--:|:--:|---|")
        for p in results:
            title = p["title"].replace("|", "／")
            link = f"[{title}]({p['detail_url']})" if p.get("detail_url") else title
            L.append(f"| {p['region']} | {p['业务类型']} | {link} |")
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
        sys.path.insert(0, str(ROOT / "scripts"))
        import md_to_pdf_edge
        md_to_pdf_edge.convert(md_path, pdf_path)   # 跨平台自动找浏览器
        return pdf_path
    except Exception as e:
        print("  (PDF生成失败，保留markdown:", e, ")")
    return md_path


def main():
    print(f"=== 商机雷达(邮件版) {TODAY} ===")
    profile = DE.load_profile()
    projects = parse_email.parse_inbox(ROOT / "inbox")
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

    md = build_report(scored, results, filtered)
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


if __name__ == "__main__":
    main()
