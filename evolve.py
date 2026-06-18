# -*- coding: utf-8 -*-
"""
每日进化引擎
=============================================================
让商机雷达每天比前一天「懂得更多、覆盖更广」。每日做三件事：

  1) 关键词进化：用本地大模型(Ollama，抓不到退 MiniMax)，结合最近抓到的标题，
     发现「室内/装饰装修设计」相关的新检索词，写入 keywords.json（discovered）。
     新词第二天自动进入所有抓取器的检索范围（fetch_registry / fetch_intention）。
  2) 信息源进化：探测注册表里的 candidate 源，能连通的自动升为 verified（covers 更多省市）。
  3) 记录进化日志：统计源数/词数/项目数/设计命中，和昨天比，写 data/进化日志.json
     与 reports/进化日志.md（人看的增长曲线）。

用法：
  python evolve.py                # 完整进化（关键词+源探测+记日志）
  python evolve.py --no-llm       # 只探测源+记日志，不动大模型
  python evolve.py --kw-only      # 只做关键词进化
  python evolve.py --max-new 8    # 每天最多新增几个词（默认 6）
"""
import re, sys, json, argparse, datetime

import enrich
import keywords as KW
import fetch_registry as FR
from app_paths import ROOT

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DATA = ROOT / "data"
REPORTS = ROOT / "reports"
DATA.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)
LOG_JSON = DATA / "进化日志.json"
LOG_MD = REPORTS / "进化日志.md"
TODAY = datetime.date.today().isoformat()

EXPAND_SYS = (
    "你是招投标检索词扩展助手，服务对象只做「室内 / 装饰装修 / 既有建筑改造」设计业务。"
    "给你现有检索词和最近抓到的项目标题，请提出**新的、能多覆盖同类设计商机或采购意向**的"
    "中文检索短词（每个 2-6 字，适合做全文搜索的词，如 幕墙/医院装修/学校改造/精装修/"
    "展厅设计/办公装修/竞争性磋商 等）。只输出 JSON：{\"新词\":[\"...\",\"...\"]}，"
    "不要解释，不要重复给定的词，不要给太宽泛的词（如 工程/项目/采购）。"
)


# ---------------- 1) 关键词进化 ----------------
def sample_titles(n=40):
    titles = []
    for fp in sorted(DATA.glob("*_projects.json")):
        try:
            for p in json.loads(fp.read_text(encoding="utf-8")):
                if p.get("是否设计"):
                    titles.append(p.get("title", "")[:40])
        except Exception:
            continue
    return titles[:n]


def evolve_keywords(cfg, max_new=6):
    data = KW.load_data()
    current = KW.load()   # base + directions(民宿/私人投资等新方向) + discovered，避免重复发现
    titles = sample_titles()
    user = (f"现有检索词：{ '、'.join(current) }\n\n"
            f"最近抓到的设计类标题（节选）：\n- " + "\n- ".join(titles or ["（暂无样本）"]) +
            f"\n\n请提出最多 {max_new} 个新检索短词。")
    content, who = enrich.llm_complete(cfg, EXPAND_SYS, user, json_mode=True)
    if not content:
        print("  关键词进化：本地/云端大模型都不可用，本次跳过（不影响其他进化）。")
        return []
    try:
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip().strip("`")
        i, j = content.find("{"), content.rfind("}")
        obj = json.loads(content[i:j + 1] if i != -1 else content)
        cand = [str(k).strip() for k in (obj.get("新词") or []) if str(k).strip()]
    except Exception as e:
        print(f"  关键词进化：解析失败跳过（{str(e)[:60]}）")
        return []
    have = set(current)
    fresh = []
    for k in cand:
        if 2 <= len(k) <= 6 and k not in have and k not in fresh:
            fresh.append(k)
    fresh = fresh[:max_new]
    if fresh:
        data["discovered"] = list(data.get("discovered", [])) + fresh
        data["updated"] = TODAY
        KW.save_data(data)
        print(f"  关键词进化：+{len(fresh)} 个新词（{who}）→ {fresh}")
    else:
        print("  关键词进化：本次无新增（模型未给出未见过的有效词）。")
    return fresh


# ---------------- 2) 信息源进化 ----------------
def evolve_sources():
    reg = FR.load_registry()
    cands = [s for s in reg.get("sources", []) if s.get("status") == "candidate"]
    promoted = []
    for s in cands:
        ok, n = FR.probe_source(s)
        if ok:
            s["status"] = "verified"
            promoted.append(s["id"])
            print(f"  信息源进化：✅ {s['id']} 连通 → 升级 verified")
    if promoted:
        FR.save_registry(reg)
    else:
        print("  信息源进化：本次无候选源连通（候选 URL 可能需更正，详见 sources.json）。")
    verified = sum(1 for s in reg.get("sources", []) if s.get("status") == "verified")
    return promoted, verified, len(cands)


# ---------------- 3) 进化日志 ----------------
def current_metrics():
    projects, cats = [], {}
    seen = set()
    for fp in sorted(DATA.glob("*_projects.json")):
        try:
            items = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in items:
            key = p.get("id") or p.get("title")
            if key in seen:
                continue
            seen.add(key)
            projects.append(p)
            cats[p.get("category", "?")] = cats.get(p.get("category", "?"), 0) + 1
    design = sum(1 for p in projects if p.get("是否设计"))
    reg = FR.load_registry()
    return {
        "date": TODAY,
        "源_verified": sum(1 for s in reg.get("sources", []) if s.get("status") == "verified"),
        "源_candidate": sum(1 for s in reg.get("sources", []) if s.get("status") == "candidate"),
        "关键词数": len(KW.load()),
        "项目总数": len(projects),
        "设计命中": design,
        "采购意向": cats.get("采购意向", 0),
    }


def record_log(metrics, kw_new, src_new):
    history = []
    if LOG_JSON.exists():
        try:
            history = json.loads(LOG_JSON.read_text(encoding="utf-8"))
        except Exception:
            history = []
    prev = history[-1] if history else None
    metrics["今日新增词"] = kw_new
    metrics["今日新增源"] = src_new
    # 同日重跑则覆盖当天那条
    history = [h for h in history if h.get("date") != TODAY]
    history.append(metrics)
    LOG_JSON.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def delta(k):
        if not prev:
            return ""
        d = metrics[k] - prev.get(k, 0)
        return f"（{'+' if d >= 0 else ''}{d}）" if d else "（持平）"

    lines = [f"# 商机雷达 · 进化日志", "",
             f"> 每天 evolve.py 自动记录。越往下，覆盖越广、识别越准。", "",
             f"## {TODAY} 今日进化",
             f"- 信息源：verified **{metrics['源_verified']}** {delta('源_verified')}"
             f"，候选 {metrics['源_candidate']}（今日新转正 {src_new} 个）",
             f"- 关键词：**{metrics['关键词数']}** 个 {delta('关键词数')}（今日新发现 {kw_new} 个）",
             f"- 项目库：**{metrics['项目总数']}** 条 {delta('项目总数')}，"
             f"设计命中 {metrics['设计命中']} {delta('设计命中')}",
             f"- 采购意向：{metrics['采购意向']} 条 {delta('采购意向')}", "",
             "## 历史趋势", "",
             "| 日期 | verified源 | 关键词 | 项目总数 | 设计命中 | 采购意向 |",
             "|:--:|:--:|:--:|:--:|:--:|:--:|"]
    for h in history[-30:]:
        lines.append(f"| {h['date']} | {h.get('源_verified','-')} | {h.get('关键词数','-')} "
                     f"| {h.get('项目总数','-')} | {h.get('设计命中','-')} | {h.get('采购意向','-')} |")
    LOG_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="每日进化引擎")
    ap.add_argument("--no-llm", action="store_true", help="不做关键词进化（不调大模型）")
    ap.add_argument("--kw-only", action="store_true", help="只做关键词进化")
    ap.add_argument("--max-new", type=int, default=6, help="每天最多新增关键词数")
    args = ap.parse_args()

    print(f"=== 每日进化 {TODAY} ===")
    kw_new = src_new = 0

    if not args.no_llm:
        cfg = enrich.load_llm_config(True)   # 尝试启用大模型链
        print(f"  大模型链：{cfg.get('chain', '无')}")
        kw_new = len(evolve_keywords(cfg, max_new=args.max_new))

    if not args.kw_only:
        promoted, verified, n_cand = evolve_sources()
        src_new = len(promoted)

    metrics = current_metrics()
    record_log(metrics, kw_new, src_new)
    print(f"\n=== 进化完成 ===")
    print(f"  源 verified {metrics['源_verified']}｜关键词 {metrics['关键词数']}"
          f"｜项目 {metrics['项目总数']}｜设计命中 {metrics['设计命中']}"
          f"｜采购意向 {metrics['采购意向']}")
    print(f"  日志：{LOG_MD}")


if __name__ == "__main__":
    main()
