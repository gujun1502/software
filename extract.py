# -*- coding: utf-8 -*-
"""
从「标题」或「详情页正文」里提取 设计面积 / 设计造价 / 关键词。
全项目共用同一套口径：run_radar.py（只有标题时）和 enrich.py（拿到详情页正文时）都调它。

设计原则：
  - 「带标签」的优先（如 控制价/最高限价/建筑面积），再退化到「裸数字+单位」。
  - 拿不到一律返回 "—"，绝不编造（面积/造价多在详情页，标题层大概率是 —）。
"""
import re

# ---------- 面积 ----------
# 优先级：装修/装饰/室内/改造/施工 面积 > 建筑面积 > 总(用地)面积 > 裸「数字+平方米」
_AREA_LABEL = re.compile(
    r"(?:装修|装饰|室内|改造|施工|建筑|总|用地|占地|绿化)\s*面积"
    r"[^\d]{0,8}(?:约|共)?\s*([\d][\d,，\.]*)\s*(万)?\s*(?:平方米|平米|㎡|m²|m2)")
_AREA_BARE = re.compile(r"(?:约|共)?\s*([\d][\d,，\.]*)\s*(万)?\s*(?:平方米|平米|㎡|m²|m2)")
_AREA_MU = re.compile(r"([\d][\d,，\.]*)\s*亩")


def _fmt_num(num, wan):
    num = num.replace("，", ",")
    return f"{num}{'万' if wan else ''}"


def extract_area(text):
    if not text:
        return "—"
    m = _AREA_LABEL.search(text)
    if m:
        return _fmt_num(m.group(1), m.group(2)) + "㎡"
    m = _AREA_BARE.search(text)
    if m:
        return _fmt_num(m.group(1), m.group(2)) + "㎡"
    m = _AREA_MU.search(text)
    return (m.group(1).replace("，", ",") + "亩") if m else "—"


# ---------- 造价 / 控制价 ----------
# 优先：控制价/最高限价/招标控制价/预算/投资/限价/合同估算/中标价 后面跟金额；再退化到裸「数字+万元/亿元」
_COST_LABEL = re.compile(
    r"(?:招标控制价|最高限价|控制价|预算金额|项目预算|投资(?:额|总额|估算)?|限价|"
    r"合同(?:估算|金额)?|成交价|中标价|金额)"
    r"[^\d￥¥]{0,10}(?:￥|¥)?\s*([\d][\d,，\.]*)\s*(万元|亿元|万|亿|元)")
_COST_BARE = re.compile(r"([\d][\d,，\.]*)\s*(万元|亿元)")


def _fmt_cost(num, unit):
    num = num.replace("，", ",")
    unit = {"万": "万元", "亿": "亿元"}.get(unit, unit)
    return f"{num}{unit}"


def extract_cost(text):
    if not text:
        return "—"
    m = _COST_LABEL.search(text)
    if m:
        return _fmt_cost(m.group(1), m.group(2))
    m = _COST_BARE.search(text)
    return _fmt_cost(m.group(1), m.group(2)) if m else "—"


# ---------- 关键词标签（顺序=优先级，最多取前 n 个）----------
KEYWORD_TAGS = [
    ("EPC", ["EPC", "设计施工", "施工总承包", "一体化"]),
    ("竞争性磋商", ["竞争性磋商"]),
    ("询比/询价", ["询比", "询价"]),
    ("单一来源", ["单一来源"]),
    ("公开招标", ["公开招标"]),
    ("迁址", ["迁址"]),
    ("精装修", ["精装修", "精装"]),
    ("室内装饰", ["室内装饰", "装饰装修", "室内设计", "装修设计"]),
    ("改造", ["改造", "提升改造", "整治"]),
    ("施工图", ["施工图设计", "施工图"]),
    ("方案设计", ["方案设计"]),
    ("流标", ["流标"]),
    ("终止", ["终止"]),
    ("重发/二次", ["重发", "二次", "第二次", "三次", "再次"]),
    ("候选人公示", ["候选人公示"]),
    ("结果公示", ["结果公示", "成交结果", "中标结果", "中选结果"]),
    ("限价公示", ["最高限价公示", "限价公示"]),
    ("资格后审", ["资格后审", "资格预审"]),
    ("答疑/补疑", ["答疑", "补疑", "澄清"]),
]


# ---------- 截标时间（投标/响应文件递交截止 > 投标截止 > 开标 > 报名截止）----------
_DATE = (r"([12]\d{3}\s*[-/年\.]\s*\d{1,2}\s*[-/月\.]\s*\d{1,2}\s*日?"
         r"(?:\s*\d{1,2}\s*[:：时]\s*\d{2}\s*分?)?)")
_DEADLINE_PATS = [
    re.compile(r"(?:投标|响应)文件(?:的)?(?:递交|提交|接收)?(?:截止|截至)(?:时间|日期)?"
               r"[^0-9]{0,8}" + _DATE),
    re.compile(r"(?:投标|响应)(?:递交|提交)?(?:截止|截至)(?:时间|日期)?[^0-9]{0,8}" + _DATE),
    re.compile(r"(?:递交|提交)(?:投标|响应)?文件(?:的)?(?:截止|截至)(?:时间|日期)?[^0-9]{0,8}" + _DATE),
    re.compile(r"开标(?:时间|日期)[^0-9]{0,8}" + _DATE),
    re.compile(r"(?:报名|获取(?:招标)?文件)(?:截止|截至)(?:时间|日期)?[^0-9]{0,8}" + _DATE),
]


def _norm_date(s):
    s = s.replace("年", "-").replace("月", "-").replace("日", " ")\
        .replace("时", ":").replace("分", "").replace("：", ":").replace("/", "-")
    s = re.sub(r"\s*-\s*", "-", s)          # 去掉分隔符两侧空格
    s = re.sub(r"\s*:\s*", ":", s)
    s = re.sub(r"\s+", " ", s).strip()      # 仅保留日期与时间之间的一个空格
    s = re.sub(r"^(\d{4})-(\d{1,2})-(\d{1,2})",
               lambda m: f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}", s)
    return s.rstrip("-: ")


def extract_deadline(text):
    """截标(投标截止)时间。按优先级匹配，取不到返回 —。"""
    if not text:
        return "—"
    for pat in _DEADLINE_PATS:
        m = pat.search(text)
        if m:
            return _norm_date(m.group(1))
    return "—"


def extract_keywords(text, n=3):
    if not text:
        return "—"
    tags = []
    for tag, kws in KEYWORD_TAGS:
        if any(k in text for k in kws) and tag not in tags:
            tags.append(tag)
        if len(tags) >= n:
            break
    return "·".join(tags) if tags else "—"
