# -*- coding: utf-8 -*-
"""
每日自动任务（供 9:30/9:45/10:00 三个定时触发点调用）。
带"当天只跑一次"保护：最早开机的那个触发点干活，之后的触发看到标记就跳过。
流程：读采招网邮件 → 决策打分 → 出排序日报。
"""
import sys, pathlib, datetime, traceback

from app_paths import ROOT  # 打包后指向 exe 目录
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
MARKER = DATA / "last_run.txt"
LOG = DATA / "daily_log.txt"
TODAY = datetime.date.today().isoformat()
NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

logf = open(LOG, "a", encoding="utf-8")


class _Tee:
    def __init__(self, *s): self.s = s
    def write(self, x):
        for st in self.s:
            try: st.write(x); st.flush()
            except Exception: pass
    def flush(self):
        for st in self.s:
            try: st.flush()
            except Exception: pass


sys.stdout = sys.stderr = _Tee(sys.__stdout__, logf)
print(f"\n===== 自动任务触发 {NOW} =====")

# 当天已成功跑过 → 跳过（实现 9:30/9:45/10:00 只执行一次）
if MARKER.exists() and MARKER.read_text(encoding="utf-8-sig").strip() == TODAY:
    print(f"[{TODAY}] 今日已成功运行过，本次跳过。")
    sys.exit(0)

try:
    import fetch_email
    import run_radar
    print("步骤1/4：读取采招网邮件 …")
    fetch_email.fetch()

    # 关键修复(2026-07-07)：以前每日任务只读邮件、从不重抓省级源，
    # data/reg_*.json 会永远停在最后一次手动抓取的那天，时间窗一过日报就空了。
    # 现在每天自动重抓所有 verified 源最近一周的公告（失败只提示，不影响日报）。
    print("步骤2/4：重抓各省公共资源交易网（最近7天新公告）…")
    for mod_name, run in [
        ("fetch_registry", lambda m: m.crawl_all(days=7, pages=2)),
        ("fetch_jiangsu",  lambda m: m.main()),
        ("fetch_ahjyztb",  lambda m: m.main()),
        ("fetch_intention", lambda m: m.main()),
    ]:
        try:
            sys.argv = [sys.argv[0]]          # 各抓取器用 argparse，避免继承本进程参数
            mod = __import__(mod_name)
            run(mod)
        except Exception as e:
            print(f"  （{mod_name} 抓取失败跳过，不影响日报；若在用VPN请关闭：{e}）")

    print("步骤3/4：关键词进化（每日扩词，新词次日进入抓取范围）…")
    try:
        import evolve
        sys.argv = [sys.argv[0]]      # evolve 用 argparse，避免继承本进程参数
        evolve.main()
    except Exception as e:
        print(f"  （关键词进化跳过，不影响日报：{e}）")
    print("步骤4/4：决策打分并生成日报 …")
    run_radar.main()
    MARKER.write_text(TODAY, encoding="utf-8")
    print(f"[{TODAY}] ✓ 全部完成，已写当天完成标记。")
except Exception:
    print("!!! 自动任务出错（不写完成标记，下一个触发点会自动重试）!!!")
    traceback.print_exc()
finally:
    logf.flush(); logf.close()
