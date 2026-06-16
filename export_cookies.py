# -*- coding: utf-8 -*-
"""
采招网 Cookie 导出小助手（Windows / 本机运行）
================================================
把你浏览器里登录采招网(bidcenter.com.cn)后的 Cookie 取出来，存到 bidcenter_cookies.txt，
之后 fetch_detail.py / enrich.py 就能抓采招网那些「需登录」的详情页(银行/证券项目)。

两种用法：

  ① 自动从浏览器读取（推荐，免手动）：
       python export_cookies.py                 # 自动扫 Edge + Chrome 所有 profile
       python export_cookies.py --browser edge  # 只读 Edge
       python export_cookies.py --browser chrome
     依赖本机已装的 cryptography + pywin32（无需额外安装）。
     ⚠️ 读取前最好【完全退出浏览器】，否则 Cookie 数据库被占用、且最新版可能解密失败。

  ② 手动粘贴（自动失败时的兜底，最稳）：
       python export_cookies.py --paste
     然后按提示：在浏览器里打开采招网并登录 → F12 → Network/网络 → 刷新页面 →
     点任意一条请求 → 复制「请求标头」里 Cookie: 后面那一整串 → 粘贴回来回车。

  验证是否可用：
       python export_cookies.py --test          # 用现有 cookie 抓一条采招网详情页看通不通
"""
import os, sys, json, base64, shutil, sqlite3, argparse, tempfile, pathlib

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app_paths import ROOT  # 打包后指向 exe 目录

# 支持多个需登录站点：采招网(默认) 与 上海建设工程交易平台(ciac)
SITES = {
    "bidcenter": {"domain": "bidcenter.com.cn", "file": "bidcenter_cookies.txt"},
    "ciac": {"domain": "ciac.zjw.sh.gov.cn", "file": "shcpe_cookies.txt"},
}
SITE = "bidcenter"
COOKIE_FILE = ROOT / SITES[SITE]["file"]
DOMAIN_MATCH = SITES[SITE]["domain"]
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")

BROWSERS = {
    "edge": pathlib.Path(LOCALAPPDATA) / "Microsoft" / "Edge" / "User Data",
    "chrome": pathlib.Path(LOCALAPPDATA) / "Google" / "Chrome" / "User Data",
}

# 一条用于自检的采招网详情页（hash 路由，登录后才有正文）
TEST_URL = ("https://user.bidcenter.com.cn/v2023/#/des/customDesBx/"
            "424333903?currentid=650780&paymail")


# ---------------- 自动读取浏览器 Cookie ----------------
def _get_aes_key(user_data_dir):
    """从 Local State 取 os_crypt 主密钥（DPAPI 解密）。"""
    import win32crypt
    local_state = user_data_dir / "Local State"
    if not local_state.exists():
        return None
    data = json.loads(local_state.read_text(encoding="utf-8"))
    enc_key = data.get("os_crypt", {}).get("encrypted_key")
    if not enc_key:
        return None
    blob = base64.b64decode(enc_key)
    if blob[:5] == b"DPAPI":
        blob = blob[5:]
    return win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1]


def _decrypt_value(enc, key):
    """解密单条 cookie 值。支持 v10(AES-GCM) / 旧版(DPAPI)；v20(应用绑定)本助手无法解，返回 None。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import win32crypt
    if not enc:
        return ""
    prefix = enc[:3]
    if prefix in (b"v10", b"v20"):
        try:
            nonce, payload = enc[3:15], enc[15:]
            dec = AESGCM(key).decrypt(nonce, payload, None)
            if prefix == b"v20":           # 应用绑定加密会在明文前加 32 字节域名哈希
                dec = dec[32:]
            return dec.decode("utf-8", "replace")
        except Exception:
            return None                    # v20 用 os_crypt 密钥解不开 → 交给手动粘贴兜底
    try:
        return win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1].decode("utf-8", "replace")
    except Exception:
        return None


def _copy_locked(src, dst):
    """复制被浏览器独占的文件：用 Win32 CreateFile 以共享读写删模式打开，绕开占用锁。
    连带复制 -wal/-shm 旁文件，保证 sqlite 读到最新数据。失败时退回 shutil。"""
    import win32file
    def _one(s, d):
        h = win32file.CreateFile(
            str(s), win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE | win32file.FILE_SHARE_DELETE,
            None, win32file.OPEN_EXISTING, 0, None)
        try:
            buf = bytearray()
            while True:
                hr, chunk = win32file.ReadFile(h, 1 << 20)
                if not chunk:
                    break
                buf += chunk
        finally:
            win32file.CloseHandle(h)
        pathlib.Path(d).write_bytes(bytes(buf))
    _one(src, dst)
    for ext in ("-wal", "-shm"):
        side = pathlib.Path(str(src) + ext)
        if side.exists():
            try:
                _one(side, pathlib.Path(str(dst) + ext))
            except Exception:
                pass


def _profiles(user_data_dir):
    """枚举 Default / Profile* 下的 Cookies 数据库。"""
    out = []
    if not user_data_dir.exists():
        return out
    for prof in user_data_dir.iterdir():
        if prof.is_dir() and (prof.name == "Default" or prof.name.startswith("Profile")):
            for sub in ("Network/Cookies", "Cookies"):
                db = prof / sub
                if db.exists():
                    out.append((prof.name, db))
                    break
    return out


def extract_from_browser(name, user_data_dir):
    """返回 (cookie_str, 统计文本)。失败返回 ("", 原因)。"""
    if not user_data_dir.exists():
        return "", f"未找到 {name} 用户数据目录"
    try:
        key = _get_aes_key(user_data_dir)
    except Exception as e:
        return "", f"{name} 主密钥读取失败: {str(e)[:80]}"
    if not key:
        return "", f"{name} 未找到 os_crypt 主密钥"

    pairs, total, undecryptable, v20 = {}, 0, 0, 0
    for prof_name, db in _profiles(user_data_dir):
        tmp = pathlib.Path(tempfile.gettempdir()) / f"_ck_{name}_{prof_name}.db"
        try:
            _copy_locked(db, tmp)          # 浏览器开着也能复制（Win32 共享模式）
        except Exception:
            try:
                shutil.copy2(db, tmp)      # 退回普通复制
            except Exception:
                return "", (f"{name}/{prof_name} 的 Cookies 被占用，复制失败 —— "
                            f"请【完全退出浏览器】后重试，或用 --paste 手动粘贴。")
        try:
            con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT host_key,name,encrypted_value FROM cookies WHERE host_key LIKE ?",
                (f"%{DOMAIN_MATCH}%",)).fetchall()
            con.close()
        except Exception as e:
            return "", f"{name}/{prof_name} 读取数据库失败: {str(e)[:80]}"
        finally:
            for ext in ("", "-wal", "-shm"):
                try: pathlib.Path(str(tmp) + ext).unlink()
                except Exception: pass
        for host, cname, enc in rows:
            total += 1
            val = _decrypt_value(enc, key)
            if val is None:
                undecryptable += 1
                if enc[:3] == b"v20":
                    v20 += 1
                continue
            if val:
                pairs[cname] = val         # 同名后者覆盖
    if not pairs:
        why = "（多为最新版应用绑定加密 v20，本助手解不开，请用 --paste）" if v20 else ""
        return "", (f"{name}: 命中 {total} 条 {DOMAIN_MATCH} cookie，但成功解密 0 条{why}")
    cookie_str = "; ".join(f"{k}={v}" for k, v in pairs.items())
    note = f"{name}: 命中{total}条，成功{len(pairs)}条" + (f"，无法解密{undecryptable}条(v20:{v20})" if undecryptable else "")
    return cookie_str, note


# ---------------- 手动粘贴 ----------------
def paste_mode():
    login_url = "https://ciac.zjw.sh.gov.cn" if SITE == "ciac" else "https://www.bidcenter.com.cn"
    print("【手动粘贴模式】")
    print(f"1) 浏览器打开 {login_url} 并确认已登录")
    print("2) 按 F12 → 选 Network/网络 标签 → 刷新页面")
    print("3) 点列表里任意一条请求 → Headers/标头 → 找到 Request Headers 里的  Cookie:")
    print("4) 复制 Cookie: 后面那一整行，粘贴到下面，回车：\n")
    try:
        raw = input("Cookie> ").strip()
    except EOFError:
        raw = ""
    raw = raw[7:].strip() if raw.lower().startswith("cookie:") else raw
    if len(raw) < 20 or "=" not in raw:
        print("✗ 看起来不是有效的 Cookie 串，未保存。")
        return False
    save(raw)
    return True


# ---------------- 保存 / 自检 ----------------
def save(cookie_str):
    COOKIE_FILE.write_text(cookie_str, encoding="utf-8")
    n = cookie_str.count("=")
    print(f"✓ 已保存 {n} 个 cookie 到 {COOKIE_FILE.name}")
    print("  现在可以跑：python enrich.py            （会带上采招网登录态抓详情页）")


def test_cookie():
    if SITE == "ciac":          # 上海平台自检交给 fetch_shcpe（调它的列表接口）
        import fetch_shcpe
        fetch_shcpe.test_cookie()
        return
    if not COOKIE_FILE.exists() or not COOKIE_FILE.read_text(encoding="utf-8").strip():
        print("✗ 还没有 cookie，先运行 python export_cookies.py 或 --paste")
        return
    from fetch_detail import fetch_detail
    print(f"用现有 cookie 抓一条采招网详情页自检……\n  {TEST_URL}")
    res = fetch_detail(TEST_URL)
    print(f"  ok={res['ok']}  note={res['note']}")
    if res["ok"]:
        print("  正文片段：", res["text"][:160].replace("\n", " "))
        print("✓ cookie 可用。")
    else:
        print("✗ 仍未取到正文。采招网是前端渲染(hash 路由)，即便带 cookie 也可能抓不到完整正文；"
              "若如此，这些项目的面积/造价仍需人工打开详情页确认。")


def main():
    global SITE, COOKIE_FILE, DOMAIN_MATCH
    ap = argparse.ArgumentParser(description="登录态 Cookie 导出小助手（采招网 / 上海ciac）")
    ap.add_argument("--site", choices=list(SITES), default="bidcenter",
                    help="采招网=bidcenter（默认）；上海建设工程平台=ciac")
    ap.add_argument("--browser", choices=["edge", "chrome"], help="只读指定浏览器，默认两者都扫")
    ap.add_argument("--paste", action="store_true", help="手动粘贴 Cookie（自动失败时用）")
    ap.add_argument("--test", action="store_true", help="用现有 cookie 自检能否过站点认证")
    args = ap.parse_args()

    # 按 --site 切换目标域名与输出文件
    SITE = args.site
    COOKIE_FILE = ROOT / SITES[SITE]["file"]
    DOMAIN_MATCH = SITES[SITE]["domain"]
    print(f"目标站点：{SITE}（域 {DOMAIN_MATCH} → {COOKIE_FILE.name}）")

    if args.test:
        test_cookie(); return
    if args.paste:
        paste_mode(); return

    targets = [args.browser] if args.browser else ["edge", "chrome"]
    best, notes = "", []
    for b in targets:
        cs, note = extract_from_browser(b, BROWSERS[b])
        notes.append("  " + note)
        if cs and len(cs) > len(best):
            best = cs
    print("浏览器读取结果：")
    print("\n".join(notes))
    if best:
        save(best)
        print("\n建议接着跑：python export_cookies.py --test  验证一下。")
    else:
        print("\n自动读取没拿到可用 cookie。请改用手动粘贴：python export_cookies.py --paste")
        print("（提示：先【完全退出浏览器】再试自动读取；最新版 Edge/Chrome 的 v20 加密只能走手动粘贴。）")


if __name__ == "__main__":
    main()
