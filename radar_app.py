# -*- coding: utf-8 -*-
"""
商机雷达 · 单一入口（PyInstaller 打成一个 exe）
================================================
双击 exe = 直接出日报并打开；也可带子命令：

  商机雷达.exe                生成日报并自动打开（用现有数据，秒出，不联网也行）
  商机雷达.exe update         全量刷新：收邮件 + 抓省级站 + 抓详情页(含大模型) + 出日报
  商机雷达.exe enrich [参数]   仅抓详情页增强（面积/造价/截标/关键词）
  商机雷达.exe cookies [参数]  采招网 Cookie 助手（自动读浏览器 / --paste / --test）
  商机雷达.exe email          仅收邮件

全程不需要 VPN，不依赖 Claude。大模型（如 MiniMax）按 llm_config.json 配置自动启用。
"""
import sys


def _safe(label, fn):
    try:
        fn()
    except SystemExit:
        pass
    except Exception as e:
        print(f"  （{label} 跳过：{e}）")


def main():
    argv0 = sys.argv[0]
    args = sys.argv[1:]
    has_cmd = bool(args) and not args[0].startswith("-")
    cmd = args[0].lower() if has_cmd else "report"
    rest = args[1:] if has_cmd else args

    if cmd in ("report", "radar", "daily", "日报"):
        sys.argv = [argv0, "--open"]
        import run_radar
        run_radar.main()

    elif cmd == "update":
        print("=== 全量刷新（建议关 VPN / 国内直连）===\n")
        def _email():
            import fetch_email; fetch_email.fetch()
        def _js():
            sys.argv = [argv0]; import fetch_jiangsu; fetch_jiangsu.main()
        def _ah():
            sys.argv = [argv0]; import fetch_ahjyztb; fetch_ahjyztb.main()
        def _sh():
            sys.argv = [argv0]; import fetch_shcpe; fetch_shcpe.main()
        def _enrich():
            sys.argv = [argv0]; import enrich; enrich.main()
        _safe("收邮件", _email)
        _safe("江苏抓取", _js)
        _safe("安徽抓取", _ah)
        _safe("上海抓取", _sh)
        _safe("详情页增强", _enrich)
        sys.argv = [argv0, "--open"]
        import run_radar
        run_radar.main()

    elif cmd == "enrich":
        sys.argv = [argv0] + rest
        import enrich; enrich.main()

    elif cmd == "cookies":
        sys.argv = [argv0] + rest
        import export_cookies; export_cookies.main()

    elif cmd == "email":
        import fetch_email; fetch_email.fetch()

    else:
        print(f"未知命令：{cmd}")
        print(__doc__)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
