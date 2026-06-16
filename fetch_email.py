# -*- coding: utf-8 -*-
"""
通过 IMAP 自动读取采招网每日商机邮件，把正文HTML存到 inbox/ 供解析。
配置在 email_config.json。可独立运行（双击 读邮件测试.bat）。
"""
import json, imaplib, email, pathlib, datetime, re
from email.header import decode_header

from app_paths import ROOT  # 打包后指向 exe 目录
INBOX = ROOT / "inbox"
INBOX.mkdir(exist_ok=True)
CFG = json.loads((ROOT / "email_config.json").read_text(encoding="utf-8"))

# 让 imaplib 认识网易邮箱要求的 ID 命令（在已登录AUTH状态下可用），否则报
# "SEARCH/SELECT illegal in state AUTH"
imaplib.Commands["ID"] = ("AUTH",)


def _send_netease_id(M):
    """网易(126/163)邮箱：登录后必须发ID命令标识客户端，否则拒绝后续操作。"""
    args = ("name", "OutBuildingDecision", "version", "1.0",
            "vendor", "obd", "contact", "user")
    typ, dat = M._simple_command("ID", '("' + '" "'.join(args) + '")')
    M._untagged_response(typ, dat, "ID")


def _dec(s):
    """解码邮件头（主题/发件人）。"""
    if not s:
        return ""
    out = []
    for txt, enc in decode_header(s):
        if isinstance(txt, bytes):
            try:
                out.append(txt.decode(enc or "utf-8", "ignore"))
            except Exception:
                out.append(txt.decode("utf-8", "ignore"))
        else:
            out.append(txt)
    return "".join(out)


def _html_of(msg):
    """取邮件的 text/html 正文。"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, "ignore")
        # 没html就退而取text
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", "ignore")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "ignore")


def fetch(save=True):
    """连接IMAP，找采招网邮件，存HTML，返回 [(主题, 文件路径)]。"""
    print(f"连接 {CFG['imap_server']} …")
    M = imaplib.IMAP4_SSL(CFG["imap_server"], CFG.get("imap_port", 993))
    M.login(CFG["email"], CFG["auth_code"])
    print("  登录成功，发送客户端ID（网易邮箱要求）…")
    try:
        _send_netease_id(M)
    except Exception as e:
        print("  (ID命令提示，可忽略:", e, ")")
    M.select("INBOX")
    typ, data = M.search(None, "ALL")
    ids = data[0].split()
    recent = ids[-CFG.get("scan_recent", 30):]
    print(f"收件箱共 {len(ids)} 封，扫描最近 {len(recent)} 封 …")

    kws = CFG.get("filter_keywords", ["采招网"])
    found = []
    for num in reversed(recent):
        typ, d = M.fetch(num, "(RFC822)")
        if typ != "OK" or not d or not d[0]:
            continue
        msg = email.message_from_bytes(d[0][1])
        subj = _dec(msg.get("Subject"))
        frm = _dec(msg.get("From"))
        if not any(k in subj or k in frm for k in kws):
            continue
        date = msg.get("Date", "")
        print(f"  ✓ 命中: {subj[:40]}  | {frm[:30]}")
        if save:
            safe = re.sub(r'[\\/:*?"<>|]', "_", subj)[:40] or "采招网邮件"
            stamp = datetime.date.today().isoformat()
            fp = INBOX / f"{stamp}_{safe}.html"
            fp.write_text(_html_of(msg), encoding="utf-8")
            found.append((subj, fp))
    M.logout()
    print(f"\n共保存 {len(found)} 封采招网邮件到 inbox/")
    for s, fp in found:
        print("   -", fp.name)
    return found


if __name__ == "__main__":
    try:
        fetch()
    except imaplib.IMAP4.error as e:
        print("\n[IMAP登录/操作失败]", e)
        print("常见原因：① 授权码填错（不是登录密码）② IMAP服务没开 ③ 邮箱地址写错")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("\n出错了，请把以上信息发我。")
