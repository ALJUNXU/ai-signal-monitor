"""Detection helpers used by the floating monitor."""

import json
import time
from pathlib import Path


CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
CLAUDE_SESSION_WINDOW_SEC = 60 * 60
TAIL_BYTES = 256 * 1024


def _tail_lines(path, max_bytes=TAIL_BYTES):
    """Return complete lines from the tail of a potentially large JSONL file."""
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        offset = max(0, size - max_bytes)
        stream.seek(offset)
        data = stream.read()
    if offset:
        _, _, data = data.partition(b"\n")
    return data.decode("utf-8", errors="replace").splitlines()


def _vscode_transcript_state(path):
    """Infer one VS Code CC session state from its latest semantic record."""
    try:
        lines = _tail_lines(path)
    except OSError:
        return None

    for line in reversed(lines):
        try:
            item = json.loads(line)
        except (TypeError, ValueError):
            continue
        if item.get("entrypoint") != "claude-vscode":
            continue
        record_type = item.get("type")
        if record_type == "user":
            return "green"
        if record_type == "assistant":
            message = item.get("message") or {}
            return "green" if message.get("stop_reason") == "tool_use" else "red"
    return None


def read_vscode_cc_sessions(
    now=None,
    green_timeout_sec=5 * 60,
    projects_dir=CLAUDE_PROJECTS_DIR,
    active_window_sec=CLAUDE_SESSION_WINDOW_SEC,
):
    """Return ``session_id -> (state, mtime)`` for recent VS Code CC chats."""
    now = time.time() if now is None else now
    projects_dir = Path(projects_dir)
    sessions = {}
    if not projects_dir.exists():
        return sessions

    try:
        paths = projects_dir.rglob("*.jsonl")
        for path in paths:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            age = now - mtime
            if age < 0 or age > active_window_sec:
                continue
            state = _vscode_transcript_state(path)
            if state is None:
                continue
            if state == "green" and green_timeout_sec > 0 and age > green_timeout_sec:
                state = "red"
            sessions[path.stem] = (state, mtime)
    except OSError:
        return sessions
    return sessions


def read_hook_sessions(
    state_dir,
    now=None,
    green_timeout_sec=5 * 60,
    active_window_sec=CLAUDE_SESSION_WINDOW_SEC,
):
    """Return recent legacy hook states, keyed by CC session id."""
    now = time.time() if now is None else now
    sessions = {}
    for path in Path(state_dir).glob("claude_*.txt"):
        try:
            mtime = path.stat().st_mtime
            age = now - mtime
            if age > 24 * 60 * 60:
                path.unlink(missing_ok=True)
                continue
            if age < 0 or age > active_window_sec:
                continue
            state = path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if state == "green" and green_timeout_sec > 0 and age > green_timeout_sec:
            state = "red"
        if state in ("green", "red", "off"):
            sessions[path.stem[len("claude_"):]] = (state, mtime)
    return sessions


def read_cc_sessions(state_dir, now=None, green_timeout_sec=5 * 60, projects_dir=None):
    """Merge transcript and hook states, keeping the newest record per session."""
    now = time.time() if now is None else now
    kwargs = {"now": now, "green_timeout_sec": green_timeout_sec}
    if projects_dir is not None:
        kwargs["projects_dir"] = projects_dir
    merged = read_vscode_cc_sessions(**kwargs)
    hook_sessions = read_hook_sessions(
        state_dir, now=now, green_timeout_sec=green_timeout_sec
    )
    for session_id, record in hook_sessions.items():
        if session_id not in merged or record[1] > merged[session_id][1]:
            merged[session_id] = record
    ordered = sorted(merged.values(), key=lambda item: item[1])
    return [state for state, _mtime in ordered if state in ("green", "red")]
