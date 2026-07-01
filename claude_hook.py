"""Claude Code hook:按 session_id 写状态文件,支持多窗口各自跟踪。

stdin 收到 hook 事件 JSON(含 session_id、hook_event_name)。
按会话写 claude_<session_id>.txt,内容: green / red / off。
悬浮框聚合所有 claude_*.txt(有 green→green,有 red→red,全 off→off),
这样多个 Claude 窗口互不覆盖。
"""
import sys
import json
import os
from pathlib import Path

try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    data = {}

sid = data.get("session_id") or "default"
ev = data.get("hook_event_name", "")

# 事件 → 状态
table = {"UserPromptSubmit": "green", "Stop": "red", "StopFailure": "red", "SessionEnd": "off"}
state = table.get(ev)
if ev == "Notification":
    # 只认 permission_prompt(VSCode 实际不触发,保留兼容)
    state = "yellow" if data.get("matcher") == "permission_prompt" else None

if state:
    out = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AiSignal"
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / f"claude_{sid}.txt").write_text(state, encoding="utf-8")
    except Exception:
        pass

sys.exit(0)
