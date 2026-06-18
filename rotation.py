# -*- coding: utf-8 -*-
"""推送轮换 / 下架规则
=============================================================
同一条可投商机最多连续上榜 2 天，第 3 天自动下架（不再出现在日报里），
为新商机腾位；并保证每天至少有 MIN_NEW 条「全新」商机被筛选出来。

历史记录在 data/推送历史.json：{ 项目id: [上榜日期, ...] }（按天去重）。
每天 run_radar 调 apply_rotation()：先按历史判定下架，再把今日实际上榜的写回历史。
"""
import json
import datetime
from app_paths import ROOT

DATA = ROOT / "data"
HISTORY_FILE = DATA / "推送历史.json"

MAX_DAYS = 2   # 连续上榜最多 2 天，第 3 天下架
MIN_NEW = 3    # 每天至少保证的「全新」商机条数


def _key(p):
    """项目唯一键，与 load_scraped 去重口径一致。"""
    return p.get("id") or p.get("title")


def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_history(h):
    DATA.mkdir(exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


def prior_days(history, p, today):
    """该项目在「今天之前」已上榜的不同天数。"""
    dates = {d for d in history.get(_key(p), []) if d != today}
    return len(dates)


def apply_rotation(scored, today=None):
    """对 score_all() 的结果应用轮换/下架规则。

    入参 scored: [(p, d), ...]，已按契合度降序。
    返回 (kept, dropped, stats, days_map)：
      - kept    : 今日上榜的 [(p, d), ...]，仍按契合度降序
      - dropped : 因连续上榜满 MAX_DAYS 天而被下架的 [(p, d), ...]
      - stats   : {上榜, 下架, 新增, 第2天, 保证新增满足, MIN_NEW}
      - days_map: { 项目id: 今天是第几天上榜(1 或 2) }
    同时把今日上榜写回 data/推送历史.json。
    """
    today = today or datetime.date.today().isoformat()
    history = load_history()

    kept, dropped, days_map = [], [], {}
    new_count = second_count = 0
    for p, d in scored:
        pd = prior_days(history, p, today)
        if pd >= MAX_DAYS:
            dropped.append((p, d))          # 连续上榜满 2 天 → 第 3 天下架
            continue
        kept.append((p, d))
        days_map[_key(p)] = pd + 1          # 今天是第 pd+1 天上榜
        if pd == 0:
            new_count += 1
        else:
            second_count += 1

    # 写回历史：仅记录今日实际上榜的，下架的不再续命
    for p, _ in kept:
        k = _key(p)
        ds = set(history.get(k, []))
        ds.add(today)
        history[k] = sorted(ds)
    save_history(history)

    stats = {
        "上榜": len(kept),
        "下架": len(dropped),
        "新增": new_count,
        "第2天": second_count,
        "保证新增满足": new_count >= MIN_NEW,
        "MIN_NEW": MIN_NEW,
    }
    return kept, dropped, stats, days_map
