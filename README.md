# AI Signal Monitor — Claude Code & Hermes 状态信号灯

一个 Windows 桌面悬浮信号灯,实时监控 **Claude Code** 和 **Hermes Desktop** 的运行状态。看一眼就知道:哪个 AI 正在跑、哪个答完了、哪个没开。竖排两个圆点(上 Claude、下 Hermes),贴边吸附隐藏,鼠标移上去平滑展开。

> 📌 **适用版本(请先确认)**
> - **Claude Code**:VSCode 的 **官方插件版**(从 VSCode 扩展市场安装的那一个,**不是** 终端 `claude` CLI 版)
> - **Hermes**:**Hermes Desktop 桌面端**(Nous Research 出的,[官网下载](https://hermes-ai.net/zh/desktop/),双击图标打开的那种)
> - **系统**:Windows 10 / 11
>
> 其它版本(CLI 版 Claude、手机端 Hermes 等)未适配,灯可能不亮。

📖 **English**: [README_EN.md](./README_EN.md)

## 状态

| 灯 | 含义 |
|---|---|
| 🟢 绿 | 正在运行(agent 在干活) |
| 🔴 红 | 完成 / 空闲(答完了) |
| ⚫ 灰 | 离线(软件没开) |

## 原理

**Claude Code** —— 用官方 [hooks](https://code.claude.com/docs/en/hooks),在 `UserPromptSubmit` / `Stop` / `SessionEnd` 事件里把状态写到 `%LOCALAPPDATA%\AiSignal\claude.txt`(取值 `green` / `red` / `off`)。

**Hermes** —— 直接读 Hermes 的 `state.db`(SQLite,WAL 只读连接,**不会锁住 Hermes**),看 `messages` 表最后一条消息的 `role` + `finish_reason`:
- `user` / `tool` / `assistant+tool_calls` → 🟢 运行中
- `assistant+stop` → 🔴 完成
- Hermes 没开 → ⚫ 灰

> 为什么不用 Hermes 的 HTTP API?它的会话状态接口(`/api/sessions`、`/api/ws` 等)本地也锁认证(`auth_required=false` 但匿名全 401),`active_sessions` 又有几分钟保活延迟。直接读它自己写的 `state.db` 是唯一精确又即时的路子。

## 用法

```bash
pip install -r requirements.txt
python signal_monitor.py
```

或直接运行打包好的 `AiSignal.exe`(在 [Releases](../../releases) 里,无需装 Python)。

### 配置 Claude Code hooks

把下面这段合并进 `~/.claude/settings.json`(Windows: `C:\Users\<你>\.claude\settings.json`)的 `hooks` 字段:

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

Hermes 那边**不用配置**,程序自动找它的 `state.db`。

## 交互

- 🖱️ 鼠标按住 → 拖动定位
- 🧲 拖到屏幕**右边缘** → 贴边吸附隐藏(只露两个灯)
- 👆 鼠标移上去 → 平滑展开(200ms 缓动动画)
- 🖱️ 右击 → 调透明度 / 退出

## 技术

Python + PySide6(Qt6)+ QPainter 自绘。无边框透明窗口 + 圆角面板 + 抗锯齿实色圆点 + `QPropertyAnimation` 滑动动画。

## 已知限制

🟡 **黄灯(权限弹窗待确认)在 VSCode 插件下不可用** —— VSCode 的权限 UI 用 IDE 原生界面,**不走** Claude Code 的 `Notification` hook(只有终端 CLI 版才走)。所以本工具只有绿/红/灰三态。详见 [Claude Code hooks 文档](https://code.claude.com/docs/en/hooks)。

## 打包成 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed signal_monitor.py
```

产物在 `dist/AiSignal.exe`。

## License

[MIT](./LICENSE)
