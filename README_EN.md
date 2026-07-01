# AI Signal Monitor — Claude Code / Codex / Hermes Status Light

A Windows desktop floating signal light that monitors **Claude Code**, **Codex**, and **Hermes Desktop** in real time. Glance and know: which AI is running, which is done, which is off.

**Dynamic lights**: only shows the Agents currently running (one light per running app; panel height grows with the count). **When multiple Claude windows are active, its light auto-splits** (2 windows → halves, 3 → thirds at 120°… each slice colored by that window's status). Docks to the right edge and hides; smoothly expands on hover.

> 📌 **Supported versions**
> - **Claude Code**: the **official VSCode extension** (from the marketplace — *not* the terminal `claude` CLI)
> - **Codex**: the **Codex desktop client** (Windows, the one with a GUI)
> - **Hermes**: **Hermes Desktop** (Nous Research, [download](https://hermes-ai.net/zh/desktop/))
> - **OS**: Windows 10 / 11
>
> Other versions (CLI Claude/Codex, mobile, etc.) are not supported.

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
| **Claude Code** | Official [hooks](https://code.claude.com/docs/en/hooks) via `claude_hook.py`, writing per-session `claude_<session>.txt`. Multiple Claude windows don't overwrite each other. |
| **Codex** | Reads `~/.codex/state_5.sqlite` (read-only SQLite), checks the last `updated_at` of the `threads` table: updated within 30s → 🟢, else 🔴. |
| **Hermes** | Reads `state.db` (read-only SQLite), checks the last message's `role` + `finish_reason`. |

> Codex/Hermes need **no configuration** — the app finds their sqlite automatically. Why not the HTTP API? It's auth-locked locally (anonymous → 401); reading the sqlite directly is the only accurate, real-time path.

## Dynamic lights + splitting

- **Dynamic**: only shows Agents that are running (no Claude light if Claude isn't running); panel height adjusts to the number of lights.
- **Claude splitting**: when multiple Claude windows are active within the last hour, its light auto-splits (2 windows → halves, 3 → thirds at 120°…), each slice colored by that window's status (green/red). Only active windows (green/red) count; closed ones (off) don't.

## Usage

```bash
pip install -r requirements.txt
python signal_monitor.py
```

Or run the prebuilt `AiSignal.exe` (from [Releases](../../releases), no Python needed).

### Configure Claude Code hooks

**Codex / Hermes need no config.** Only Claude Code does (it has no readable state file, so we use hooks):

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
