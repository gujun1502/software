# -*- coding: utf-8 -*-
"""
上海建设工程招标商机 抓取（shcpe.cn → ciac.zjw.sh.gov.cn 交易平台）
====================================================================
上海的招标公告在 ciac.zjw.sh.gov.cn（JGBAppZtbInterWeb）这个【需登录(SSO)】的平台上，
接口 POST /JGBAppZtbInterWeb/rest/jygg/list （params: gglx=zbgg, pageNo, pageSize），
未登录会返回 {code:401, 认证失败}。

所以本抓取需要你的登录态 Cookie（xc_ciacsso 等）：
  1) 浏览器登录 https://ciac.zjw.sh.gov.cn 后，运行：python export_cookies.py --site ciac
     （把 cookie 存到 shcpe_cookies.txt）
  2) python fetch_shcpe.py --test     # 先验证 cookie 能不能过认证
  3) python fetch_shcpe.py            # 抓招标公告 → data/shcpe_projects.json

⚠️ 该平台可能对接口做 SM2/SM4 签名校验；仅凭 cookie 不一定能过。--test 会当场告诉你行不行。
抓不到不影响主流程（run_radar 会照常出报告，只是没有上海这一路数据）。
"""
import re, sys, json, argparse, datetime
import requests

import parse_email as PE        # 复用 classify / is_design，全项目同口径
from app_paths import ROOT      # 打包后指向 exe 目录

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
requests.packages.urllib3.disable_warnings()

DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
COOKIE_FILE = ROOT / "shcpe_cookies.txt"
TODAY = datetime.date.today().isoformat()

HOST = "https://ciac.zjw.sh.gov.cn"
API = HOST + "/JGBAppZtbInterWeb/rest/jygg/list"
PORTAL = HOST + "/JGBAppZtbInterWeb/pc/"
# gglx：招标公告=zbgg；如需中标可加 zbjggs/zbhxrgs 等（平台代码，可用 --gglx 覆盖）
DEFAULT_GGLX = ["zbgg"]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": PORTAL,
}


def _load_cookie():
    if COOKIE_FILE.exists():
        s = COOKIE_FILE.read_text(encoding="utf-8").strip()
        if s:
            return s
    return ""


def _pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return ""


def call_list(cookie, gglx="zbgg", pageNo=1, pageSize=20):
    """调列表接口，返回 (rows, total, note)。note 非空表示出问题。"""
    headers = dict(HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    params = {"gglx": gglx, "pageNo": pageNo, "pageSize": pageSize}
    try:
        r = requests.post(API, params=params, headers=headers, timeout=25, verify=False)
    except Exception as e:
        return [], 0, f"请求异常: {str(e)[:100]}"
    try:
        data = r.json()
    except Exception:
        return [], 0, f"非JSON响应(HTTP {r.status_code}): {r.text[:80]}"
    if isinstance(data, dict) and data.get("code") in (401, 403):
        return [], 0, "认证失败(401)：需要有效登录 Cookie，或平台要求签名"
    # 兼容多种返回结构
    rows = (data.get("rows") or data.get("records") or data.get("data")
            or (data.get("result") or {}).get("rows") if isinstance(data, dict) else None) or []
    total = data.get("total") or len(rows) if isinstance(data, dict) else 0
    if not rows and isinstance(data, dict):
        return [], 0, f"返回无 rows：{json.dumps(data, ensure_ascii=False)[:120]}"
    return rows, total, ""


def row_to_project(rec):
    title = PE_clean(_pick(rec, "title", "ggmc", "ggbt", "projectName", "xmmc"))
    if not title:
        return None
    gid = _pick(rec, "ggid", "infoid", "id", "rowguid", "ggrowid", "uuid")
    gglx = _pick(rec, "gglx") or "zbgg"
    date = str(_pick(rec, "fbsj", "createDate", "infodate", "ggfbsj", "publishDate"))[:10]
    detail = (f"{PORTAL}#/jyggDetail?ggid={gid}&gglx={gglx}" if gid else PORTAL + "#/jyggList?gglx=zbgg")
    return {
        "id": "shcpe_" + (str(gid) or re.sub(r"\W+", "", title)[:24]),
        "title": title,
        "region": "上海市",
        "category": "招标公告",
        "pub_date": date,
        "detail_url": detail,
        "业务类型": PE.classify(title),
        "是否设计": PE.is_design(title),
        "来源": "shcpe",
    }


def PE_clean(t):
    return re.sub(r"\s+", " ", re.sub(r"</?[^>]+>", "", t or "")).strip()


def crawl(cookie, gglx_list, pages, page_size):
    seen, out = set(), []
    for gglx in gglx_list:
        for pg in range(1, pages + 1):
            rows, total, note = call_list(cookie, gglx, pg, page_size)
            if note:
                print(f"   [{gglx} 第{pg}页] {note}")
                break
            fresh = 0
            for rec in rows:
                p = row_to_project(rec)
                if not p or p["id"] in seen:
                    continue
                seen.add(p["id"]); out.append(p); fresh += 1
            print(f"   [{gglx} 第{pg}页] 返回{len(rows)}条，新增{fresh}（total≈{total}）")
            if len(rows) < page_size:
                break
    return out


def test_cookie():
    cookie = _load_cookie()
    print(f"=== 上海 ciac 连通自检 ===  cookie: {'有' if cookie else '无（先跑 export_cookies.py --site ciac）'}")
    rows, total, note = call_list(cookie, "zbgg", 1, 5)
    if note:
        print("✗ 失败：", note)
        print("  → 若是401：在浏览器登录 ciac.zjw.sh.gov.cn 后 `python export_cookies.py --site ciac` 导cookie再试。")
    else:
        print(f"✓ 成功！拿到 {len(rows)} 条（total≈{total}）。可以直接 `python fetch_shcpe.py` 抓取。")
        for rec in rows[:3]:
            p = row_to_project(rec)
            if p:
                print("   样例:", p["title"][:40])


def main():
    ap = argparse.ArgumentParser(description="上海建设工程招标抓取（需 ciac 登录 cookie）")
    ap.add_argument("--test", action="store_true", help="只测 cookie 能否过认证")
    ap.add_argument("--gglx", nargs="*", default=None, help="公告类型代码，默认 zbgg(招标公告)")
    ap.add_argument("--pages", type=int, default=3, help="每类翻页数")
    ap.add_argument("--page-size", type=int, default=20)
    args = ap.parse_args()

    if args.test:
        test_cookie(); return

    cookie = _load_cookie()
    print(f"=== 上海建设工程抓取 {TODAY} ===  源：{HOST}")
    if not cookie:
        print("⚠️ 没有 shcpe_cookies.txt（登录态）。上海平台需登录，先：")
        print("   ① 浏览器登录 https://ciac.zjw.sh.gov.cn")
        print("   ② python export_cookies.py --site ciac")
        print("   本次跳过上海，不影响其他来源。")
        return
    projects = crawl(cookie, args.gglx or DEFAULT_GGLX, args.pages, args.page_size)
    design = [p for p in projects if p["是否设计"]]
    out = DATA / "shcpe_projects.json"
    out.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 完成 ===  共抓 {len(projects)} 条；其中设计类 {len(design)} 条 → {out}")
    if projects and not design:
        print("（提示：抓到了公告但没有设计类，可能这几页没有装修/装饰/室内设计项目）")


if __name__ == "__main__":
    main()
