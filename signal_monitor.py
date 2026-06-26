#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 信号灯监控 v6(竖排 + 无光晕 + 圆角 + 贴边吸附隐藏)

竖排两个实色圆点:Claude(上)、Hermes(下)。绿=运行中 红=完成 灰=离线。
贴屏幕右边缘吸附隐藏(只露灯),鼠标 hover 展开(灯+标签)。
"""
import os
import json
import sys
import time
import sqlite3
import threading
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget, QMenu
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication

LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or str(Path.home())
STATE_DIR = Path(LOCALAPPDATA) / "AiSignal"
STATE_FILES = {"claude": STATE_DIR / "claude.txt", "hermes": STATE_DIR / "hermes.txt"}
HERMES_DB = Path(LOCALAPPDATA) / "hermes" / "state.db"
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


STATE_RGB = {"green": (86, 230, 140), "red": (255, 95, 95), "off": (115, 124, 144)}
AGENT_DEFS = [("claude", "Claude"), ("hermes", "Hermes")]   # Claude 第一个(上)

# 右键菜单文案(中/英)
I18N = {
    "zh": {"opacity": "透明度", "clear": "清晰", "high": "高", "medium": "中", "low": "低",
           "timeout": "绿灯超时转红", "off": "关闭", "min": "分钟", "language": "语言", "exit": "退出"},
    "en": {"opacity": "Opacity", "clear": "Clear", "high": "High", "medium": "Medium", "low": "Low",
           "timeout": "Green timeout → Red", "off": "Off", "min": "min", "language": "Language", "exit": "Exit"},
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
        self.show()
        g = self._screen_right()
        self.move(g - self.W_HIDDEN, 12)   # 初始:右上角贴边隐藏(露灯)

        self._t = QTimer(self); self._t.timeout.connect(self.refresh); self._t.start(1000)
        self._show_timer = QTimer(self); self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._dock_show)
        self._hide_timer = QTimer(self); self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._dock_hide)
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.refresh()
        threading.Thread(target=self._hermes_loop, daemon=True).start()

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

    def _hermes_loop(self):
        last_proc = 0.0
        running = False
        last_written = None
        while True:
            try:
                now = time.time()
                if (not running) or (now - last_proc > 10):
                    running = _hermes_running()
                    last_proc = now
                s = _state_from_db() if running else "off"
                if s != last_written:                # 只在状态变化时写(让 mtime = 进入该状态的时刻)
                    STATE_FILES["hermes"].write_text(s, encoding="utf-8")
                    last_written = s
            except Exception:
                pass
            time.sleep(2)

    def refresh(self):
        changed = False
        now = time.time()
        timeout = self._green_timeout_min * 60 if self._green_timeout_min > 0 else 0
        for k, _ in AGENT_DEFS:
            p = STATE_FILES[k]
            try:
                v = p.read_text(encoding="utf-8").strip().lower()
                mt = p.stat().st_mtime
            except Exception:
                v, mt = "off", now
            v = v if v in STATE_RGB else "off"
            # 绿灯超时:文件是 green,但超过 N 分钟没更新 → 视为卡住,转红
            if v == "green" and timeout > 0 and (now - mt) > timeout:
                v = "red"
            if self.states[k] != v:
                self.states[k] = v
                changed = True
        if changed:
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
        for i, (key, name) in enumerate(AGENT_DEFS):
            cy = 24 + i * 44          # Claude y=24,Hermes y=68
            r, g, b = STATE_RGB[self.states[key]]
            p.setBrush(QColor(r, g, b))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), 7.5, 7.5)
            # 标签(灯右侧)
            p.setPen(QColor(224, 230, 240, 232))
            p.setFont(f)
            p.drawText(QRectF(38, cy - 9, w - 44, 18),
                       Qt.AlignVCenter | Qt.AlignLeft, name)

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
