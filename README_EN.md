# AI Signal Monitor — Claude Code & Hermes Status Light

A Windows desktop floating signal light that monitors **Claude Code** and **Hermes Desktop** in real time. Glance and know: which AI is running, which is done, which is off. Two vertical dots (Claude on top, Hermes below); docks to the screen edge and hides; smoothly expands on hover.

> 📌 **Supported versions**
> - **Claude Code**: the **official VSCode extension** (from the VSCode marketplace — *not* the terminal `claude` CLI)
> - **Hermes**: **Hermes Desktop** (by Nous Research, [download](https://hermes-ai.net/zh/desktop/))
> - **OS**: Windows 10 / 11
>
> Other versions (CLI Claude, mobile Hermes, etc.) are not supported.

📖 **中文**: [README.md](./README.md)

## Status

| Light | Meaning |
|---|---|
| 🟢 Green | Running (agent working) |
| 🔴 Red | Done / idle (finished) |
| ⚫ Gray | Offline (app not running) |

## How it works

**Claude Code** — uses official [hooks](https://code.claude.com/docs/en/hooks) to write status to `%LOCALAPPDATA%\AiSignal\claude.txt` on `UserPromptSubmit` / `Stop` / `SessionEnd` (values: `green` / `red` / `off`).

**Hermes** — reads Hermes's `state.db` (SQLite, read-only WAL, **won't lock Hermes**) and checks the last message's `role` + `finish_reason`:
- `user` / `tool` / `assistant+tool_calls` → 🟢 running
- `assistant+stop` → 🔴 done
- Hermes not running → ⚫ gray

> Why not the HTTP API? The session-state endpoints (`/api/sessions`, `/api/ws`) are auth-locked (anonymous → 401 even locally), and `active_sessions` has a multi-minute keepalive delay. Reading the `state.db` Hermes writes itself is the only accurate, real-time path.

## Usage

```bash
pip install -r requirements.txt
python signal_monitor.py
```

Or run the prebuilt `AiSignal.exe` (from [Releases](../../releases), no Python needed).

### Configure Claude Code hooks

Merge this into the `hooks` field of `~/.claude/settings.json` (Windows: `C:\Users\<you>\.claude\settings.json`):

```json
{
  "hooks": {
    "UserPromptSubmit": [{ "hooks": [{ "type": "command",
      "command": "mkdir -p \"$HOME/AppData/Local/AiSignal\" && echo green > \"$HOME/AppData/Local/AiSignal/claude.txt\"" }] }],
    "Stop": [{ "hooks": [{ "type": "command",
      "command": "mkdir -p \"$HOME/AppData/Local/AiSignal\" && echo red > \"$HOME/AppData/Local/AiSignal/claude.txt\"" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command",
      "command": "mkdir -p \"$HOME/AppData/Local/AiSignal\" && echo off > \"$HOME/AppData/Local/AiSignal/claude.txt\"" }] }]
  }
}
```

Hermes needs **no configuration** — the app finds its `state.db` automatically.

## Interaction

- 🖱️ Drag to move
- 🧲 Drag to the **right edge** → dock & hide (only the two lights show)
- 👆 Hover → smooth expand (200ms eased)
- 🖱️ Right-click → **opacity / green-timeout / language / exit**

## Tech

Python + PySide6 (Qt6) + QPainter. Frameless translucent window + rounded panel + antialiased solid dots + `QPropertyAnimation` slide.

## Known limitations

🟡 **Yellow (permission prompt) is unavailable in the VSCode extension** — VSCode's permission UI is native and **doesn't go through** Claude Code's `Notification` hook (only the terminal CLI does). So this tool has only green/red/gray. See [Claude Code hooks docs](https://code.claude.com/docs/en/hooks).

## Build the exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed signal_monitor.py
```

Output in `dist/AiSignal.exe`.

## License

[MIT](./LICENSE)
