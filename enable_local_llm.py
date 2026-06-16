# -*- coding: utf-8 -*-
"""把 llm_config.json 迁移成「本地 Ollama 优先 + 原有云端兜底」的多 provider 链并启用。
安装本地大模型.bat 装好 Ollama 后调它，保证本地模型真正进入 provider 链（而不仅启用旧的单云端）。
幂等：重复运行不会重复插入 Ollama。"""
import sys, json
from app_paths import ROOT

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CFG = ROOT / "llm_config.json"
EXAMPLE = ROOT / "llm_config.example.json"
OLLAMA = {"name": "本地Ollama", "base_url": "http://localhost:11434/v1",
          "api_key": "ollama", "model": "qwen2.5:7b", "timeout": 120}


def _is_local(p):
    u = (p.get("base_url") or "").lower()
    return "localhost" in u or "127.0.0.1" in u


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b"
    OLLAMA["model"] = model

    if CFG.exists():
        try:
            cfg = json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    elif EXAMPLE.exists():
        cfg = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    else:
        cfg = {}

    provs = cfg.get("providers")
    if not isinstance(provs, list) or not provs:
        # 旧单 provider 格式 → 转成列表保留为云端兜底
        old = []
        if cfg.get("base_url") or cfg.get("model"):
            old = [{"name": cfg.get("model") or "云端兜底", "base_url": cfg.get("base_url", ""),
                    "api_key": cfg.get("api_key", ""), "model": cfg.get("model", ""), "timeout": 60}]
        provs = old

    if not any(_is_local(p) for p in provs):
        provs = [OLLAMA] + provs          # 本地排第一
    else:
        for p in provs:                   # 已有本地条目：更新模型名
            if _is_local(p):
                p["model"] = model

    new = {"enabled": True, "providers": provs}
    if "_说明" in cfg:
        new["_说明"] = cfg["_说明"]
    CFG.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    chain = " → ".join(f"{p['name']}({p['model']})" for p in provs)
    print(f"  已启用大模型链：{chain}")


if __name__ == "__main__":
    main()
