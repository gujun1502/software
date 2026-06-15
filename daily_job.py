# -*- coding: utf-8 -*-
"""
每日自动任务（供 9:30/9:45/10:00 三个定时触发点调用）。
带"当天只跑一次"保护：最早开机的那个触发点干活，之后的触发看到标记就跳过。
流程：读采招网邮件 → 决策打分 → 出排序日报。
"""
import sys, pathlib, datetime, traceback

ROOT = pathlib.Path(__file__).resolve().parent
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
    print("步骤1/2：读取采招网邮件 …")
    fetch_email.fetch()
    print("步骤2/2：决策打分并生成日报 …")
    run_radar.main()
    MARKER.write_text(TODAY, encoding="utf-8")
    print(f"[{TODAY}] ✓ 全部完成，已写当天完成标记。")
except Exception:
    print("!!! 自动任务出错（不写完成标记，下一个触发点会自动重试）!!!")
    traceback.print_exc()
finally:
    logf.flush(); logf.close()
