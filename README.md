# AI Signal Monitor — Claude Code / Codex / Hermes 状态信号灯

一个 Windows 桌面悬浮信号灯,实时监控 **Claude Code**、**Codex**、**Hermes Desktop** 的运行状态。看一眼就知道:哪个 AI 在跑、哪个答完了、哪个没开。

**动态灯**:只显示正在运行的 Agent(跑几个亮几个,面板高度跟着变)。**Claude 多窗口时,灯会自动分块**(2 窗口两半、3 窗口三份 120°…每块颜色对应该窗口状态)。贴屏幕右边缘吸附隐藏,鼠标移上去平滑展开。

> 📌 **适用版本(请先确认)**
> - **Claude Code**:VSCode 的 **官方插件版**(扩展市场装,**不是** 终端 `claude` CLI 版)
> - **Codex**:**Codex 桌面客户端**(Windows,有界面的那个)
> - **Hermes**:**Hermes Desktop 桌面端**(Nous Research,[官网](https://hermes-ai.net/zh/desktop/))
> - **系统**:Windows 10 / 11
>
> 其它版本(CLI 版 Claude/Codex、手机端等)未适配。

📖 **English**: [README_EN.md](./README_EN.md)

## 状态

| 灯 | 含义 |
|---|---|
| 🟢 绿 | 正在运行(agent 在干活) |
| 🔴 红 | 完成 / 空闲(答完了) |
| ⚫ 灰 | 离线(软件没开) |

## 原理

| Agent | 怎么判断状态 |
|---|---|
| **Claude Code** | 用官方 [hooks](https://code.claude.com/docs/en/hooks)(`claude_hook.py`),按**会话**写 `claude_<session>.txt`。多个 Claude 窗口互不覆盖。 |
| **Codex** | 直接读 `~/.codex/state_5.sqlite`(SQLite 只读),看 `threads` 表最后 `updated_at`:30 秒内有更新 → 🟢,否则 🔴。 |
| **Hermes** | 直接读 `state.db`(SQLite 只读),看最后一条消息的 `role` + `finish_reason`。 |

> Codex / Hermes 都**不用配置**,程序自动找它们的 sqlite。为什么不用 HTTP API?本地都锁认证(匿名 401),sqlite 直读是唯一精确又即时的路子。

## 动态灯 + 分块

- **动态**:只显示正在运行的 Agent(Claude 没跑就不显示 Claude 灯),面板高度随灯数变化。
- **Claude 分块**:1 小时内活跃的 Claude 窗口有多个时,灯自动分块(2 窗口→两半、3→三份 120°…),每块颜色对应该窗口状态(绿/红)。只算活跃窗口(green/red),已关闭(off)不计。

## 用法

```bash
pip install -r requirements.txt
python signal_monitor.py
```

或运行打包好的 `AiSignal.exe`(在 [Releases](../../releases),无需 Python)。

### 配置 Claude Code hooks

**Codex / Hermes 不用配置**。只有 Claude Code 要(它没有可读的状态文件,靠 hooks):

把下面合并进 `~/.claude/settings.json`(Windows: `C:\Users\<你>\.claude\settings.json`)的 `hooks` 字段(**`<项目路径>` 换成你 clone 的实际路径**,如 `D:/code/ai-signal`):

```json
{
  "hooks": {
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "python \"<项目路径>/claude_hook.py\"" }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "python \"<项目路径>/claude_hook.py\"" }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": "python \"<项目路径>/claude_hook.py\"" }] }]
  }
}
```

## 交互 / 设置(右键)

- 🖱️ 鼠标按住 → 拖动定位
- 🧲 拖到屏幕**右边缘** → 贴边吸附隐藏(只露灯)
- 👆 鼠标移上去 → 平滑展开(动画)
- 🖱️ 右击菜单:
  - **透明度**(清晰 / 高 / 中 / 低)
  - **绿灯超时转红**(关闭 / 3 / 5 / 10 / 20 分钟:绿灯这么久没完成自动转红)
  - **刷新频率**(1 / 5 / 10 / 30 / 60 秒)
  - **语言**(中文 / English)
  - 退出

设置存 `%LOCALAPPDATA%\AiSignal\config.json`,重启保留。

## 技术

Python + PySide6(Qt6)+ QPainter 自绘。无边框透明圆角面板 + 抗锯齿圆点 + 饼图分块 + 动画(`QPropertyAnimation` + `QVariantAnimation`)。

## 已知限制

🟡 **黄灯(权限弹窗待确认)在 VSCode 插件下不可用** —— VSCode 权限 UI 用 IDE 原生界面,不走 Claude Code 的 `Notification` hook。所以只有绿/红/灰。

## 打包成 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed signal_monitor.py
```

产物 `dist/AiSignal.exe`。

## License

[MIT](./LICENSE)
