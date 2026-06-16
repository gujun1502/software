# -*- coding: utf-8 -*-
"""
详情页增强（在国内网络直连环境运行即可）
==========================================================
把可投商机的详情页正文抓下来 → 提取「设计面积 / 设计造价 / 关键词」→ 写入
data/详情增强.json（按项目 id 索引）。run_radar.py 出报告时优先用这里的值，
抓不到的退回标题识别。

提取器三层兜底（可插拔，OpenAI 兼容）：
  · 本地 Ollama（默认 qwen2.5:7b）：免费/离线/隐私，优先用。没装或没起服务自动跳过。
  · 云端 MiniMax：本地抽不到/超时时兜底（需在 llm_config.json 填 api_key 才启用）。
  · 正则（extract.py）：最后兜底，永不缺席。
  谁先成功用谁；全失败退正则。国内直连即可，无需任何代理。

用法：
  python enrich.py                 # 抓「可投商机(设计类招标)」详情页，正则提取
  python enrich.py --llm           # 强制启用大模型（覆盖配置）
  python enrich.py --no-llm        # 强制只用正则
  python enrich.py --include-results  # 连竞争情报(中标结果)也抓，便于看价格
  python enrich.py --force         # 忽略缓存，全部重抓
  python enrich.py --limit 10      # 只处理前 10 条（先小批量验证）
"""
import re, sys, json, time, argparse, pathlib, datetime
import requests

# 控制台编码兜底：Windows GBK 控制台直接 print emoji/特殊字符会 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import parse_email
import extract as EX
from fetch_detail import fetch_detail

from app_paths import ROOT  # 打包后指向 exe 目录
DATA = ROOT / "data"
INBOX = ROOT / "inbox"
ENRICH_FILE = DATA / "详情增强.json"
LLM_CONFIG = ROOT / "llm_config.json"
DATA.mkdir(exist_ok=True)


# ---------------- 项目集合（与 run_radar 同口径）----------------
def load_all_projects():
    projects = parse_email.parse_inbox(INBOX) if INBOX.exists() else []
    seen = {p.get("id") or p["title"] for p in projects}
    for fp in sorted(DATA.glob("*_projects.json")):
        try:
            items = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in items:
            key = p.get("id") or p.get("title")
            if key and key not in seen:
                seen.add(key)
                projects.append(p)
    return projects


# ---------------- 大模型抽取（OpenAI 兼容，三层兜底：本地Ollama→云端MiniMax→正则）----------------
# 默认 provider 链：本地 Ollama 优先（免费/离线/隐私），抓不到/没装/超时自动退云端 MiniMax，
# 再退正则。每个 provider 都是 OpenAI 兼容端点，换厂商只改 base_url/model/api_key。
DEFAULT_PROVIDERS = [
    {"name": "本地Ollama", "base_url": "http://localhost:11434/v1",
     "api_key": "ollama", "model": "qwen2.5:7b", "timeout": 120},
    {"name": "MiniMax兜底", "base_url": "https://api.minimaxi.com/v1",
     "api_key": "", "model": "MiniMax-Text-01", "timeout": 60},
]


def _is_local(base_url):
    u = (base_url or "").lower()
    return "localhost" in u or "127.0.0.1" in u or "::1" in u


def _normalize_providers(cfg):
    """把配置归一成 provider 列表。
    新格式：cfg["providers"]=[{name,base_url,api_key,model,timeout}, ...]。
    旧格式：顶层 base_url/model/api_key → 包成单个 provider（向后兼容）。
    缺省：用 DEFAULT_PROVIDERS（本地 Ollama + MiniMax 兜底）。"""
    raw = cfg.get("providers")
    if not (isinstance(raw, list) and raw):
        if cfg.get("base_url") or cfg.get("model"):          # 旧单 provider 格式
            raw = [{"name": cfg.get("model") or "provider", "base_url": cfg.get("base_url", ""),
                    "api_key": cfg.get("api_key", ""), "model": cfg.get("model", "")}]
        else:
            raw = DEFAULT_PROVIDERS
    provs = []
    for p in raw:
        base = (p.get("base_url") or "").strip()
        provs.append({
            "name": (p.get("name") or p.get("model") or "provider"),
            "base_url": base,
            "api_key": (p.get("api_key") or "").strip(),
            "model": (p.get("model") or "").strip(),
            "timeout": p.get("timeout", 60),
            "local": _is_local(base),
        })
    return provs


def load_llm_config(cli_override=None):
    """返回 {enabled, providers:[可用provider...], chain}。
    provider 可用条件：有 base_url+model，且(本地 或 已填 api_key)。
    本地 Ollama 不需要真 key；云端没填 key 的会被自动跳过（留作以后填上即生效的兜底位）。"""
    cfg = {"enabled": False}
    if LLM_CONFIG.exists():
        try:
            cfg.update(json.loads(LLM_CONFIG.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  (llm_config.json 解析失败，按禁用处理: {e})")
    if cli_override is True:
        cfg["enabled"] = True
    elif cli_override is False:
        cfg["enabled"] = False

    all_provs = _normalize_providers(cfg)
    usable = [p for p in all_provs if p["base_url"] and p["model"]
              and (p["local"] or p["api_key"])]
    if cfg.get("enabled") and not usable:
        print("  ⚠️ 已启用大模型但没有可用 provider（本地未配 / 云端没填 api_key），降级为只用正则。")
        cfg["enabled"] = False
    cfg["providers"] = usable
    cfg["chain"] = " → ".join(f"{p['name']}({p['model']})" for p in usable) or "无"
    return cfg


LLM_PROMPT = (
    "你是招投标公告信息抽取助手。从给定公告正文中抽取以下字段，只输出一个 JSON 对象，"
    "不要输出任何解释：\n"
    '{"面积":"如 3500㎡，没有写则空字符串","造价":"控制价/预算/中标价，如 280万元，没有则空字符串",'
    '"截标时间":"投标/响应文件递交截止时间，如 2026-06-20 09:30，没有则空字符串",'
    '"关键词":["最多4个，如 竞争性磋商/迁址/精装修/EPC/室内装饰 等"]}\n'
    "面积优先取装修/室内/改造面积，其次建筑面积。造价优先取招标控制价/最高限价/预算金额。"
    "截标时间优先取投标文件/响应文件递交截止时间，其次开标时间。"
)


def _chat(prov, messages, json_mode=True):
    """向单个 provider 发一次 OpenAI 兼容 chat 请求，返回助手文本；网络/HTTP 失败抛异常。"""
    url = prov["base_url"].rstrip("/")
    if "completion" not in url:          # 允许直接给完整端点；否则补标准路径
        url += "/chat/completions"
    body = {"model": prov["model"], "messages": messages, "temperature": 0}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(url, headers={"Authorization": f"Bearer {prov['api_key'] or 'x'}",
                                    "Content-Type": "application/json"},
                      data=json.dumps(body), timeout=prov.get("timeout", 60))
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse_llm_json(content):
    """清洗并解析模型返回：去 <think>…</think>、```json 包裹，截取 {…} 主体。"""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    content = content.strip("`")
    i, j = content.find("{"), content.rfind("}")
    if i != -1 and j != -1 and j > i:
        content = content[i:j + 1]
    obj = json.loads(content)
    area = (obj.get("面积") or "").strip()
    cost = (obj.get("造价") or "").strip()
    dl = (obj.get("截标时间") or "").strip()
    kws = obj.get("关键词") or []
    kw = "·".join([str(k).strip() for k in kws if str(k).strip()][:4])
    return {"设计面积": area or "—", "设计造价": cost or "—",
            "截标时间": dl or "—", "关键词": kw or "—"}


def llm_complete(cfg, system, user, json_mode=True):
    """沿 provider 链依次发一次对话：本地Ollama→云端MiniMax→…，谁先成功用谁。
    返回 (文本, provider标识)；全部失败返回 (None, None)。供抽取/进化等多处复用。"""
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    for prov in cfg.get("providers", []):
        try:
            try:
                content = _chat(prov, messages, json_mode=json_mode)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                raise                                          # 连接层失败(如本地没起)：换下一个 provider
            except Exception:
                # 含 HTTP 400：个别厂商(MiniMax 等)不支持 response_format，去掉它在同源重试一次
                content = _chat(prov, messages, json_mode=False)
            return content, f"{prov['name']}/{prov['model']}"
        except Exception as e:
            tag = "本地未启动" if prov["local"] else "失败"
            print(f"      ({prov['name']} {tag}，尝试下一个: {str(e)[:70]})")
            continue
    return None, None


def llm_extract(cfg, title, text):
    """结构化抽取：沿 provider 链调用，全部失败返回 None（由调用方退回正则）。"""
    content, who = llm_complete(cfg, LLM_PROMPT,
                                f"【标题】{title}\n【正文】\n{text[:6000]}", json_mode=True)
    if content is None:
        return None
    try:
        res = _parse_llm_json(content)
        res["_provider"] = who
        return res
    except Exception as e:
        print(f"      (解析大模型返回失败，回退正则: {str(e)[:70]})")
        return None


# ---------------- 主流程 ----------------
def enrich_one(p, cfg):
    text_src = fetch_detail(p.get("detail_url", ""))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rec = {"ok": False, "设计面积": "—", "设计造价": "—", "截标时间": "—", "关键词": "—",
           "note": text_src["note"], "host": text_src["host"],
           "来源页": p.get("detail_url", ""), "抓取时间": now}
    if not text_src["ok"]:
        return rec
    text = text_src["text"]
    # 先正则兜底
    rec.update({
        "设计面积": EX.extract_area(text),
        "设计造价": EX.extract_cost(text),
        "截标时间": EX.extract_deadline(text),
        "关键词": EX.extract_keywords(text, n=4),
        "ok": True,
    })
    # 大模型增强：非空字段覆盖正则
    if cfg["enabled"]:
        llm = llm_extract(cfg, p["title"], text)
        if llm:
            for k in ("设计面积", "设计造价", "截标时间", "关键词"):
                if llm[k] and llm[k] != "—":
                    rec[k] = llm[k]
            rec["来源"] = llm.get("_provider", "LLM")
    return rec


def main():
    ap = argparse.ArgumentParser(description="详情页增强（国内网络直连运行）")
    ap.add_argument("--llm", dest="llm", action="store_true", default=None, help="强制启用大模型")
    ap.add_argument("--no-llm", dest="llm", action="store_false", help="强制只用正则")
    ap.add_argument("--include-results", action="store_true", help="连竞争情报(中标结果)也抓")
    ap.add_argument("--force", action="store_true", help="忽略缓存全部重抓")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条")
    ap.add_argument("--sleep", type=float, default=0.8, help="每条间隔秒数(礼貌抓取)")
    args = ap.parse_args()

    cfg = load_llm_config(args.llm)
    print(f"=== 详情页增强 ===  提取器：{'正则 + 大模型链[' + cfg['chain'] + ']' if cfg['enabled'] else '仅正则'}")
    print("（提示：国内网络直连即可运行；本地 Ollama 离线可用）")

    projects = load_all_projects()
    bid_cats = ("招标公告", "采购信息", "招标预告")
    targets = [p for p in projects if p.get("是否设计") and
               (p.get("category") in bid_cats or
                (args.include_results and p.get("category") in ("中标结果", "中标候选人")))]
    if args.limit:
        targets = targets[:args.limit]

    cache = {}
    if ENRICH_FILE.exists():
        try:
            cache = json.loads(ENRICH_FILE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    done = ok = 0
    for i, p in enumerate(targets, 1):
        key = p.get("id") or p["title"]
        if not args.force and cache.get(key, {}).get("ok"):
            continue
        rec = enrich_one(p, cfg)
        cache[key] = rec
        done += 1
        ok += 1 if rec["ok"] else 0
        # 先落盘再打印，避免打印异常导致本条结果丢失
        ENRICH_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        flag = "OK" if rec["ok"] else "--"
        extra = (f"面积={rec['设计面积']} 造价={rec['设计造价']} 截标={rec['截标时间']}"
                 if rec["ok"] else rec["note"][:40])
        print(f"  [{i}/{len(targets)}] {flag} {p['title'][:26]} | {extra}")
        if args.sleep:
            time.sleep(args.sleep)

    print(f"\n=== 完成 ===  本次处理 {done} 条，成功补全 {ok} 条 → {ENRICH_FILE}")
    print("现在跑 `python run_radar.py` 即可生成带面积/造价的日报。")


if __name__ == "__main__":
    main()
