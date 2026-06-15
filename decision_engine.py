# -*- coding: utf-8 -*-
"""
Out Building Decision · 第二期 决策引擎
输入：一个项目的招标要求 + 公司能力档案(company_profile.json)
输出：硬门槛体检 + 契合度打分 + 决策结论(建议投/可投/放弃)

注意：项目的"资质要求/业绩要求/控制价"需来自详情页或招标文件（第二期的详情抓取负责填）。
本模块是纯逻辑，可独立用样例数据测试。
"""
import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent
QUAL_RANK = {"无": 0, "丙级": 1, "乙级": 2, "甲级": 3}
THIS_YEAR = 2026


def load_profile(path=None):
    path = path or (ROOT / "company_profile.json")
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


# ---------- 硬门槛：一票否决，回答"有没有资格" ----------
def hard_gate(project, profile):
    """返回 (是否通过, [体检明细]). 任一 fail = 不能投。"""
    checks = []
    ok = True

    # 1. 装饰设计资质等级
    req = project.get("资质要求等级", "无")
    have = profile["资质"].get("建筑装饰工程设计专项", "无")
    passed = QUAL_RANK.get(have, 0) >= QUAL_RANK.get(req, 0)
    checks.append(("资质等级", passed, f"要求{req}，我方{have}"))
    ok &= passed

    # 2. 类似业绩数量（近N年，指定类型）
    need_n = project.get("业绩要求_个数", 0)
    need_type = project.get("业绩要求_类型", "")     # 如"银行" 或 "" 表示不限类型
    within = project.get("业绩要求_近几年", 5)
    matched = [p for p in profile.get("业绩库", [])
               if (THIS_YEAR - int(p.get("完成年份", 0))) <= within
               and (not need_type or need_type in str(p.get("类型", "")))]
    passed = len(matched) >= need_n
    checks.append(("类似业绩", passed,
                   f"要求近{within}年{need_n}个[{need_type or '不限'}]，我方满足{len(matched)}个"))
    ok &= passed

    # 3. 报名/制标时间是否来得及
    deadline = project.get("报名截止")
    if deadline:
        days = (datetime.date.fromisoformat(deadline) - datetime.date(THIS_YEAR, 6, 14)).days
        passed = days >= 2
        checks.append(("时间可行", passed, f"距截止{days}天"))
        ok &= passed

    return ok, checks


# ---------- 软匹配：回答"我们多合适"(0~100) ----------
def soft_score(project, profile):
    w = profile["打分权重"]
    parts = {}

    # 业绩相似度：匹配同类型业绩越多越高（3个及以上=满分）
    need_type = project.get("业绩要求_类型", "") or project.get("项目类型", "")
    same = [p for p in profile.get("业绩库", []) if need_type and need_type in str(p.get("类型", ""))]
    parts["业绩相似度"] = min(1.0, len(same) / 3.0) if need_type else 0.5

    # 资质匹配：刚好达标=1，远超略降性价比
    req = QUAL_RANK.get(project.get("资质要求等级", "无"), 0)
    have = QUAL_RANK.get(profile["资质"].get("建筑装饰工程设计专项", "无"), 0)
    parts["资质匹配"] = 1.0 if have == max(req, 1) else (0.85 if have > req else 0.0)

    # 规模匹配：你不限规模 → 恒定较高
    parts["规模匹配"] = 0.8

    # 地域优势：你全国无偏好 → 0（权重也已置0）
    parts["地域优势"] = 0.0

    # 价格竞争力：占位（第二期接 bid-pricing-engine 后用真实测算替换）
    parts["价格竞争力"] = project.get("价格竞争力_预估", 0.6)

    # 业主关系：业绩库里做过该业主 → 加分
    owner = project.get("业主", "")
    done = any(owner and owner[:4] in str(p.get("业主", "")) for p in profile.get("业绩库", []))
    parts["业主关系"] = 1.0 if done else 0.3

    score = sum(parts[k] * w.get(k, 0) for k in parts) * 100
    return round(score, 1), parts


# ---------- 综合决策 ----------
def decide(project, profile):
    gate_ok, checks = hard_gate(project, profile)
    if not gate_ok:
        fails = [c[0] for c in checks if not c[1]]
        return {
            "决策": "放弃", "标记": "❌",
            "理由": "未过硬门槛：" + "、".join(fails),
            "硬门槛": checks, "契合度": None, "打分明细": None,
        }
    score, parts = soft_score(project, profile)
    if score >= 70:
        label, mark = "建议投", "✅"
    elif score >= 50:
        label, mark = "可投", "🟡"
    else:
        label, mark = "谨慎/放弃", "⚠️"
    return {
        "决策": label, "标记": mark,
        "理由": f"过硬门槛，契合度{score}分",
        "硬门槛": checks, "契合度": score, "打分明细": parts,
    }


if __name__ == "__main__":
    prof = load_profile()
    demo = {
        "项目名称": "XX银行四川分行营业网点装饰装修设计",
        "项目类型": "银行", "业主": "XX银行四川分行",
        "资质要求等级": "乙级", "业绩要求_个数": 2, "业绩要求_类型": "银行",
        "业绩要求_近几年": 3, "报名截止": "2026-06-25",
    }
    import pprint; pprint.pprint(decide(demo, prof))
