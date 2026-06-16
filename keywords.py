# -*- coding: utf-8 -*-
"""共享关键词库。base=人工设定的核心词；discovered=进化引擎(evolve.py)用大模型发现的新词。
各抓取器调 load() 拿到合并去重后的检索词，于是「新词」第二天自动进入抓取范围。"""
import json
from app_paths import ROOT

KW_FILE = ROOT / "keywords.json"
BASE_DEFAULT = ["室内", "装饰", "装修", "精装", "改造"]


def load_data():
    if KW_FILE.exists():
        try:
            d = json.loads(KW_FILE.read_text(encoding="utf-8"))
            d.setdefault("base", BASE_DEFAULT)
            d.setdefault("discovered", [])
            return d
        except Exception:
            pass
    return {"base": list(BASE_DEFAULT), "discovered": [], "updated": ""}


def save_data(d):
    KW_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def load(limit=None):
    """合并 base+discovered，去重保序。limit 限制总数（抓取礼貌性）。"""
    d = load_data()
    out, seen = [], set()
    for k in list(d.get("base", [])) + list(d.get("discovered", [])):
        k = (k or "").strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:limit] if limit else out
