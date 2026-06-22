# -*- coding: utf-8 -*-
"""共享关键词库。base=人工设定的核心词；discovered=进化引擎(evolve.py)用大模型发现的新词。
各抓取器调 load() 拿到合并去重后的检索词，于是「新词」第二天自动进入抓取范围。"""
import json
from app_paths import ROOT

KW_FILE = ROOT / "keywords.json"
BASE_DEFAULT = ["室内", "装饰", "装修", "精装", "改造"]

# 新拓展业务方向的默认检索词（写进代码随仓库分发，因为 keywords.json 被 gitignore）。
# 注意：本地若已存在 keywords.json，则以文件里的 directions 为准（用户/进化结果优先），
# 这些默认值只在「没有该字段」时兜底（如全新克隆、首次运行）。
DIRECTIONS_DEFAULT = {
    "民宿文旅": ["民宿", "精品民宿", "民宿设计", "民宿改造", "乡村民宿", "文旅民宿", "客栈",
                 "度假酒店", "精品酒店", "温泉酒店", "康养中心", "田园综合体", "特色小镇", "老宅改造"],
    "私人投资": ["私人投资", "私人定制", "私宅", "别墅", "别墅设计", "豪宅", "大平层", "自建房",
                 "私人会所", "会所设计", "样板房", "售楼处", "餐饮空间", "商业空间"],
    "私人银行家办": ["私人银行", "家族办公室", "家办", "财富管理中心", "私人财富", "财富中心",
                   "私人银行中心", "高端财富", "私行"],
    "对标业绩类型": ["证券", "证券营业部", "证券总部", "金融办公", "总部办公", "总部研发",
                   "研发中心", "科技总部", "科技园", "汽车展厅", "4S店", "商业综合体",
                   "购物中心", "写字楼", "金融中心", "产业园", "厂房精装", "银行网点"],
}


def _default_directions():
    """返回一份新拷贝，避免外部修改污染模块级默认值。"""
    return {k: list(v) for k, v in DIRECTIONS_DEFAULT.items()}


def load_data():
    if KW_FILE.exists():
        try:
            d = json.loads(KW_FILE.read_text(encoding="utf-8"))
            d.setdefault("base", list(BASE_DEFAULT))
            d.setdefault("directions", _default_directions())
            d.setdefault("discovered", [])
            return d
        except Exception:
            pass
    return {"base": list(BASE_DEFAULT), "directions": _default_directions(),
            "discovered": [], "updated": ""}


def save_data(d):
    KW_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _flatten_directions(directions):
    """directions 可为 {方向名:[词,...]} 或扁平 [词,...]，统一摊平成词列表。"""
    if isinstance(directions, dict):
        out = []
        for words in directions.values():
            out += list(words or [])
        return out
    return list(directions or [])


def load(limit=None):
    """合并 base+directions(新业务方向)+discovered，去重保序。
    limit 限制总数（抓取礼貌性）。directions 让「民宿/私人投资」等新方向词进入全网搜索。"""
    d = load_data()
    pool = (list(d.get("base", []))
            + _flatten_directions(d.get("directions", {}))
            + list(d.get("discovered", [])))
    out, seen = [], set()
    for k in pool:
        k = (k or "").strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:limit] if limit else out
