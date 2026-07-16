#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 信号灯监控(竖排 + 无光晕 + 圆角 + 贴边吸附隐藏)

竖排显示 CC、ChatGPT、Hermes。绿=运行中 红=完成 灰=离线。
贴屏幕右边缘吸附隐藏(只露灯),鼠标 hover 展开(灯+标签)。
"""
import os
import json
import math
import sys
import time
import sqlite3
import subprocess
from pathlib import Path

from detectors import read_cc_sessions

from PySide6.QtWidgets import QApplication, QWidget, QMenu
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QPoint, QPropertyAnimation, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication

LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or str(Path.home())
STATE_DIR = Path(LOCALAPPDATA) / "AiSignal"
HERMES_DB = Path(LOCALAPPDATA) / "hermes" / "state.db"
CODEX_STATE = Path.home() / ".codex" / "state_5.sqlite"
CONFIG_FILE = STATE_DIR / "config.json"
CREATE_NO_WINDOW = 0x08000000


def _load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(d):
    try:
        CONFIG_FILE.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass


# ---------- Hermes ----------
def _hermes_running():
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "if(Get-Process Hermes -ErrorAction SilentlyContinue){'1'}else{'0'}"],
            text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
        return "1" in out
    except Exception:
        return False

def _state_from_db():
    db = str(HERMES_DB).replace("\\", "/")
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True, timeout=2)
        row = con.execute(
            "SELECT role, finish_reason FROM messages ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
    except Exception:
        return "off"
    if not row:
        return "off"
    role, finish = row[0], row[1]
    if role == "user":
        return "green"
    if role == "tool":
        return "green"
    if role == "assistant":
        return "red" if finish == "stop" else "green"
    return "off"


def _chatgpt_state_from_db(now, active_sec=30):
    """读 ChatGPT/Codex state_5.sqlite 的最后更新时间。"""
    if not CODEX_STATE.exists():
        return "off"
    db = str(CODEX_STATE).replace("\\", "/")
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True, timeout=2)
        row = con.execute("SELECT MAX(updated_at) FROM threads WHERE archived=0").fetchone()
        con.close()
    except Exception:
        return "off"
    last = row[0] if row and row[0] else 0
    if not last:
        return "off"
    return "green" if (now - last) < active_sec else "red"


def _check_processes():
    """一次检查 ChatGPT/Hermes；兼容仍带主窗口的旧版 Codex。"""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "$chat = Get-Process ChatGPT -ErrorAction SilentlyContinue; "
             "if(-not $chat){$chat = Get-Process Codex -ErrorAction SilentlyContinue | "
             "Where-Object {$_.MainWindowHandle -ne 0}}; "
             "if($chat){'ChatGPT'}; "
             "if(Get-Process Hermes -ErrorAction SilentlyContinue){'Hermes'}"],
            text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
        return set(l.strip() for l in out.splitlines() if l.strip())
    except Exception:
        return set()


STATE_RGB = {"green": (86, 230, 140), "red": (255, 95, 95), "off": (115, 124, 144)}
AGENT_DEFS = [("claude", "CC"), ("chatgpt", "ChatGPT"), ("hermes", "Hermes")]   # 顺序:上→下

# 右键菜单文案(中/英)
I18N = {
    "zh": {"opacity": "透明度", "clear": "清晰", "high": "高", "medium": "中", "low": "低",
           "timeout": "绿灯超时转红", "off": "关闭", "min": "分钟", "language": "语言",
           "refresh": "刷新频率", "sec": "秒", "exit": "退出"},
    "en": {"opacity": "Opacity", "clear": "Clear", "high": "High", "medium": "Medium", "low": "Low",
           "timeout": "Green timeout → Red", "off": "Off", "min": "min", "language": "Language",
           "refresh": "Refresh rate", "sec": "s", "exit": "Exit"},
}


class Monitor(QWidget):
    W_HIDDEN = 40      # 隐藏态露出宽度(灯区)
    W_FULL = 138       # 展开态宽度(灯 + 标签)
    H = 92

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(self.W_FULL, self.H)
        self.states = {k: "off" for k, _ in AGENT_DEFS}
        self._drag = None
        self._docked = True
        _cfg = _load_config()
        self._green_timeout_min = int(_cfg.get("green_timeout_min", 5))
        self._lang = _cfg.get("lang", "zh")
        self._refresh_sec = int(_cfg.get("refresh_sec", 5))   # refresh 间隔,默认 5 秒
        self._claude_sessions = []
        self._active_agents = []     # [(key,name,state,sessions)] 在跑的,动态显示
        self.show()
        g = self._screen_right()
        self.move(g - self.W_HIDDEN, 12)   # 初始:右上角贴边隐藏(露灯)

        self._t = QTimer(self); self._t.timeout.connect(self.refresh); self._t.start(self._refresh_sec * 1000)
        self._show_timer = QTimer(self); self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._dock_show)
        self._hide_timer = QTimer(self); self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._dock_hide)
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        # 状态变化时灯的淡入过渡(0→1, 280ms)
        self._fade = 1.0
        self._fade_anim = QVariantAnimation(self)
        self._fade_anim.setDuration(280)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.valueChanged.connect(
            lambda v: (setattr(self, "_fade", v), self.update()))
        self.refresh()

    def _screen_right(self):
        try:
            return QGuiApplication.primaryScreen().geometry().right()
        except Exception:
            return 1919

    def _animate_to(self, x):
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(x, self.y()))
        self._anim.start()

    def _dock_hide(self):
        g = self._screen_right()
        self._animate_to(g - self.W_HIDDEN)

    def _dock_show(self):
        g = self._screen_right()
        self._animate_to(g + 6 - self.W_FULL)

    def enterEvent(self, e):
        if self._docked:
            self._hide_timer.stop()
            self._show_timer.start(50)    # 50ms 展开(几乎即时)

    def leaveEvent(self, e):
        if self._docked:
            self._show_timer.stop()
            self._hide_timer.start(120)   # 120ms 隐藏

    def refresh(self):
        now = time.time()
        timeout = self._green_timeout_min * 60 if self._green_timeout_min > 0 else 0
        procs = _check_processes()
        # CC:优先直接读 VS Code 插件会话 JSONL,并兼容旧 hooks 状态文件。
        sessions = read_cc_sessions(STATE_DIR, now=now, green_timeout_sec=timeout)
        self._claude_sessions = sessions
        cstate = "green" if "green" in sessions else ("red" if "red" in sessions else "off")
        # 只把"在跑的"放进列表 → 灯动态增减
        active = []
        if sessions:
            active.append(("claude", "CC", cstate, sessions))
        if "ChatGPT" in procs:
            active.append(("chatgpt", "ChatGPT", _chatgpt_state_from_db(now), None))
        if "Hermes" in procs:
            active.append(("hermes", "Hermes", _state_from_db(), None))
        changed = (active != self._active_agents)
        self._active_agents = active
        new_h = max(48, len(active) * 44 + 12)      # 面板高度随灯数动态
        if new_h != self.height():
            self.resize(self.W_FULL, new_h)
        if changed:
            self._fade = 0.0
            self._fade_anim.stop()
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.start()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()

        # 圆角面板(半透深色,无 acrylic → 圆角生效)
        m = 4
        rect = QRectF(m, m, w - 2 * m, h - 2 * m)
        p.setBrush(QColor(24, 26, 32, 210))
        p.setPen(QPen(QColor(96, 106, 126, 130), 1))
        p.drawRoundedRect(rect, 16, 16)

        # 竖排灯(左侧)+ 标签(右侧)
        f = QFont("Segoe UI", 9)
        f.setBold(True)
        try:
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        except Exception:
            pass
        cx = 20
        alpha = int(255 * (0.35 + 0.65 * self._fade))   # 状态变化时从淡亮起
        for i, (key, name, state, _sess) in enumerate(self._active_agents):
            cy = 24 + i * 44
            if key == "claude":
                self._draw_claude_light(p, cx, cy, 7.5, alpha)
            else:
                r, g, b = STATE_RGB.get(state, STATE_RGB["off"])
                p.setBrush(QColor(r, g, b, alpha))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), 7.5, 7.5)
            p.setPen(QColor(224, 230, 240, 232))
            p.setFont(f)
            p.drawText(QRectF(38, cy - 9, w - 44, 18),
                       Qt.AlignVCenter | Qt.AlignLeft, name)

    def _draw_claude_light(self, p, cx, cy, r, alpha=255):
        """CC 灯:按 1 小时活跃窗口数分块(2 窗口两半、3 窗口三份 120°…)。"""
        sessions = self._claude_sessions
        if not sessions:
            p.setBrush(QColor(*STATE_RGB["off"], alpha)); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), r, r); return
        if len(sessions) == 1:
            p.setBrush(QColor(*STATE_RGB[sessions[0]], alpha)); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), r, r); return
        # 多窗口:饼图切片 + 径向分隔黑线
        n = len(sessions)
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        span = 360 * 16 / n
        for i, s in enumerate(sessions):
            p.setBrush(QColor(*STATE_RGB[s], alpha)); p.setPen(Qt.NoPen)
            p.drawPie(rect, int(-90 * 16 + i * span), int(span))
        p.setPen(QPen(QColor(20, 22, 28, alpha), 1)); p.setBrush(Qt.NoBrush)
        for i in range(n):
            ang = math.radians(-90 + i * 360 / n)
            p.drawLine(QPointF(cx, cy),
                       QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang)))
        p.setPen(QPen(QColor(110, 120, 140, min(255, alpha + 40)), 1))
        p.drawEllipse(QPointF(cx, cy), r, r)

    # ---------- 拖动 + 贴边吸附 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._docked = False
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
        # 靠近右边缘 → 吸附隐藏
        if self.x() + self.width() > self._screen_right() - 24:
            self._docked = True
            self._dock_hide()

    def _set_timeout(self, minutes):
        self._green_timeout_min = minutes
        cfg = _load_config(); cfg["green_timeout_min"] = int(minutes); _save_config(cfg)

    def _set_lang(self, lang):
        self._lang = lang
        cfg = _load_config(); cfg["lang"] = lang; _save_config(cfg)

    def _set_refresh(self, sec):
        self._refresh_sec = sec
        self._t.setInterval(sec * 1000)
        cfg = _load_config(); cfg["refresh_sec"] = int(sec); _save_config(cfg)

    def contextMenuEvent(self, e):
        t = I18N.get(self._lang, I18N["zh"])
        m = QMenu(self)
        for k, op in [("clear", 1.0), ("high", 0.88), ("medium", 0.72), ("low", 0.52)]:
            m.addAction(t["opacity"] + " · " + t[k], lambda op=op: self.setWindowOpacity(op))
        m.addSeparator()
        tm = m.addMenu(t["timeout"])
        cur = self._green_timeout_min
        for val in [0, 3, 5, 10, 20]:
            label = t["off"] if val == 0 else f"{val} {t['min']}"
            tm.addAction(("✓ " if val == cur else "    ") + label,
                         lambda val=val: self._set_timeout(val))
        m.addSeparator()
        rm = m.addMenu(t["refresh"])
        for val in [1, 5, 10, 30, 60]:
            rm.addAction(("✓ " if val == self._refresh_sec else "    ") + f"{val} {t['sec']}",
                         lambda val=val: self._set_refresh(val))
        lm = m.addMenu(t["language"])
        for label, val in [("中文", "zh"), ("English", "en")]:
            lm.addAction(("✓ " if val == self._lang else "    ") + label,
                         lambda val=val: self._set_lang(val))
        m.addSeparator()
        m.addAction(t["exit"], self.close)
        m.exec(e.globalPos())


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    Monitor()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
