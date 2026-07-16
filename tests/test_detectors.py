import json
import os
import tempfile
import unittest
from pathlib import Path

from claude_hook import safe_session_id, write_event_state
from detectors import read_cc_sessions, read_vscode_cc_sessions


def write_jsonl(path, records, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    os.utime(path, (mtime, mtime))


class ClaudeCodeDetectorTests(unittest.TestCase):
    def test_vscode_user_record_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace" / "session-1.jsonl"
            write_jsonl(path, [{"type": "user", "entrypoint": "claude-vscode"}], 995)
            sessions = read_vscode_cc_sessions(now=1000, projects_dir=tmp, green_timeout_sec=60)
            self.assertEqual(sessions["session-1"][0], "green")

    def test_completed_vscode_assistant_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace" / "session-2.jsonl"
            write_jsonl(path, [{"type": "assistant", "entrypoint": "claude-vscode", "message": {"stop_reason": "end_turn"}}], 995)
            sessions = read_vscode_cc_sessions(now=1000, projects_dir=tmp)
            self.assertEqual(sessions["session-2"][0], "red")

    def test_cli_transcript_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace" / "cli-session.jsonl"
            write_jsonl(path, [{"type": "user", "entrypoint": "cli"}], 995)
            self.assertEqual(read_vscode_cc_sessions(now=1000, projects_dir=tmp), {})

    def test_hook_and_transcript_for_same_session_are_not_double_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            state_dir.mkdir()
            transcript = root / "projects" / "workspace" / "same-session.jsonl"
            write_jsonl(transcript, [{"type": "assistant", "entrypoint": "claude-vscode", "message": {"stop_reason": "end_turn"}}], 995)
            hook = state_dir / "claude_same-session.txt"
            hook.write_text("green", encoding="utf-8")
            os.utime(hook, (990, 990))
            sessions = read_cc_sessions(state_dir, now=1000, projects_dir=root / "projects", green_timeout_sec=60)
            self.assertEqual(sessions, ["red"])

    def test_newer_session_end_hook_hides_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            state_dir.mkdir()
            transcript = root / "projects" / "workspace" / "closed-session.jsonl"
            write_jsonl(
                transcript,
                [{
                    "type": "assistant",
                    "entrypoint": "claude-vscode",
                    "message": {"stop_reason": "end_turn"},
                }],
                990,
            )
            hook = state_dir / "claude_closed-session.txt"
            hook.write_text("off", encoding="utf-8")
            os.utime(hook, (995, 995))
            sessions = read_cc_sessions(
                state_dir,
                now=1000,
                projects_dir=root / "projects",
                green_timeout_sec=60,
            )
            self.assertEqual(sessions, [])


class ClaudeHookPrivacyTests(unittest.TestCase):
    def test_session_id_cannot_escape_state_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_event_state(
                {
                    "session_id": "../../private/session",
                    "hook_event_name": "UserPromptSubmit",
                },
                state_dir=tmp,
            )
            self.assertEqual(target.parent, Path(tmp))
            self.assertEqual(target.read_text(encoding="utf-8"), "green")
            self.assertNotIn("/", target.name)
            self.assertNotIn("\\", target.name)

    def test_empty_or_unsafe_session_id_uses_safe_default(self):
        self.assertEqual(safe_session_id("../../"), "default")


if __name__ == "__main__":
    unittest.main()
