"""Claude Code hook:按 session_id 写状态文件,支持多窗口各自跟踪。

stdin 收到 hook 事件 JSON(含 session_id、hook_event_name)。
按会话写 claude_<session_id>.txt,内容: green / red / off。
悬浮框聚合所有 claude_*.txt(有 green→green,有 red→red,全 off→off),
这样多个 Claude 窗口互不覆盖。
"""
import sys
import json
import os
import re
from pathlib import Path


EVENT_STATES = {
    "UserPromptSubmit": "green",
    "Stop": "red",
    "StopFailure": "red",
    "SessionEnd": "off",
}


def safe_session_id(value):
    """Return a filename-safe, bounded session id."""
    value = re.sub(r"[^A-Za-z0-9._-]", "_", str(value or "default"))
    value = value.strip("._")[:128]
    return value or "default"


def write_event_state(data, state_dir=None):
    """Persist only the sanitized session id and coarse traffic-light state."""
    event = data.get("hook_event_name", "")
    state = EVENT_STATES.get(event)
    if event == "Notification":
        # VSCode normally uses its own permission UI; retained for old clients.
        state = "yellow" if data.get("matcher") == "permission_prompt" else None
    if not state:
        return None

    session_id = safe_session_id(data.get("session_id"))
    out = state_dir or (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AiSignal"
    )
    try:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        target = out / f"claude_{session_id}.txt"
        target.write_text(state, encoding="utf-8")
        return target
    except OSError:
        return None


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (TypeError, ValueError):
        data = {}
    write_event_state(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
