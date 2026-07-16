# AI Signal Monitor — CC / ChatGPT / Hermes Status Light

A Windows desktop floating signal light that monitors **Claude Code (CC)**, the **ChatGPT desktop app (formerly Codex)**, and **Hermes Desktop** in real time.

**Dynamic lights**: only shows the Agents currently running (one light per running app; panel height grows with the count). **When multiple CC windows are active, its light auto-splits** (2 windows → halves, 3 → thirds at 120°… each slice colored by that window's status). Docks to the right edge and hides; smoothly expands on hover.

> 📌 **Supported versions**
> - **CC**: the official **Claude Code VSCode extension** (not the terminal `claude` CLI)
> - **ChatGPT**: the **ChatGPT desktop app** (formerly the Codex desktop client)
> - **Hermes**: **Hermes Desktop** (Nous Research, [download](https://hermes-ai.net/zh/desktop/))
> - **OS**: Windows 10 / 11
>
> Other versions (terminal CC, mobile ChatGPT, etc.) are not supported.

📖 **中文**: [README.md](./README.md)

## Status

| Light | Meaning |
|---|---|
| 🟢 Green | Running (agent working) |
| 🔴 Red | Done / idle (finished) |
| ⚫ Gray | Offline (app not running) |

## How it works

| Agent | How status is detected |
|---|---|
| **CC** | Reads the official VSCode extension's `~/.claude/projects/**/*.jsonl` files and only accepts `entrypoint=claude-vscode` sessions. No hooks required. |
| **ChatGPT** | Detects the `ChatGPT` process (with legacy Codex-window compatibility) and reads `~/.codex/state_5.sqlite`: updated within 30s → 🟢, else 🔴. |
| **Hermes** | Reads `state.db` (read-only SQLite), checks the last message's `role` + `finish_reason`. |

> CC, ChatGPT, and Hermes need **no configuration**. The monitor discovers their local session files and sqlite databases automatically.

## Dynamic lights + splitting

- **Dynamic**: only shows Agents that are running (no CC light if CC isn't running); panel height adjusts to the number of lights.
- **CC splitting**: when multiple VSCode CC sessions are active within the last hour, its light auto-splits (2 windows → halves, 3 → thirds at 120°…), each slice colored by that session's status (green/red).

## Usage

```bash
pip install -r requirements.txt
python signal_monitor.py
```

Or run the prebuilt `AiSignal.exe` (from [Releases](../../releases), no Python needed).

### CC hooks (optional compatibility)

Current releases read VSCode CC's JSONL sessions directly, so **hooks are not required**. For older CC releases, the following can still be merged into `~/.claude/settings.json` as a compatibility channel:

Merge this into the `hooks` field of `~/.claude/settings.json` (Windows: `C:\Users\<you>\.claude\settings.json`). **Replace `<project-path>` with your actual clone path** (e.g. `D:/code/ai-signal`):

```json
{
  "hooks": {
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "python \"<project-path>/claude_hook.py\"" }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "python \"<project-path>/claude_hook.py\"" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": "python \"<project-path>/claude_hook.py\"" }] }]
  }
}
```

## Interaction / Settings (right-click)

- 🖱️ Drag to move
- 🧲 Drag to the **right edge** → dock & hide (only lights show)
- 👆 Hover → smooth expand (animated)
- 🖱️ Right-click menu:
  - **Opacity** (Clear / High / Medium / Low)
  - **Green timeout → Red** (Off / 3 / 5 / 10 / 20 min: green turns red if no completion within this time)
  - **Refresh rate** (1 / 5 / 10 / 30 / 60 s)
  - **Language** (中文 / English)
  - Exit

Settings persist in `%LOCALAPPDATA%\AiSignal\config.json`.

## Privacy & Security

- **Fully local**: the monitor makes no network requests and uploads no telemetry, prompts, responses, or session files.
- CC detection only uses status metadata (`entrypoint`, `type`, and `stop_reason`) from recent JSONL records; message content is never logged, copied, or persisted by AiSignal.
- ChatGPT and Hermes databases are read-only, and only fields needed to infer busy/idle state are used.
- The optional hook writes only a filename-safe session id and a `green/red/off` state; it never stores prompts or responses.
- `.gitignore` excludes `.env` files, keys, databases, logs, and session JSONL by default to reduce accidental disclosure.

## Tech

Python + PySide6 (Qt6) + QPainter. Frameless translucent rounded panel + antialiased dots + pie splitting + animation (`QPropertyAnimation` + `QVariantAnimation`).

## Known limitations

🟡 **Yellow (permission prompt) is unavailable in the VSCode extension** — VSCode's permission UI is native and doesn't go through Claude Code's `Notification` hook. So only green/red/gray.

## Build the exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed signal_monitor.py
```

Output in `dist/AiSignal.exe`.

## License

[MIT](./LICENSE)
