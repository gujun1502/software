# -*- coding: utf-8 -*-
"""把文字摘要推送到个人微信（PushPlus / Server酱）。发不了文件，只发文字/markdown。"""
import json, pathlib, requests

ROOT = pathlib.Path(__file__).resolve().parent
_CFGP = ROOT / "push_config.json"


def _cfg():
    if _CFGP.exists():
        try:
            return json.loads(_CFGP.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def push(title, content):
    """推送一条消息到微信。未启用则跳过。返回是否成功。"""
    c = _cfg()
    if not c.get("enabled"):
        print("  （微信推送未启用，跳过；填好 push_config.json 并 enabled=true 即可）")
        return False
    svc = c.get("service", "pushplus")
    try:
        if svc == "pushplus":
            r = requests.post("http://www.pushplus.plus/send", json={
                "token": str(c.get("token", "")).strip(),
                "title": title, "content": content, "template": "markdown",
            }, timeout=20)
            ok = (r.json().get("code") == 200)
        elif svc == "serverchan":
            r = requests.post(
                f"https://sctapi.ftqq.com/{str(c.get('sendkey','')).strip()}.send",
                data={"title": title, "desp": content}, timeout=20)
            ok = (r.json().get("code") == 0)
        else:
            print("  未知推送服务:", svc)
            return False
        print("  微信推送:", "成功 ✓" if ok else f"失败：{r.text[:160]}")
        return ok
    except Exception as e:
        print("  微信推送异常:", e)
        return False


if __name__ == "__main__":
    # 自测：发一条测试消息
    ok = push("商机雷达·推送测试", "# 测试成功\n如果你在微信收到这条，说明推送通了。")
    print("结果:", ok)
