#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 信号灯监控 v6(竖排 + 无光晕 + 圆角 + 贴边吸附隐藏)

竖排两个实色圆点:Claude(上)、Hermes(下)。绿=运行中 红=完成 灰=离线。
贴屏幕右边缘吸附隐藏(只露灯),鼠标 hover 展开(灯+标签)。
"""
import os
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
CREATE_NO_WINDOW = 0x08000000


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
        while True:
            try:
                now = time.time()
                if (not running) or (now - last_proc > 10):
                    running = _hermes_running()
                    last_proc = now
                s = _state_from_db() if running else "off"
                STATE_FILES["hermes"].write_text(s, encoding="utf-8")
            except Exception:
                pass
            time.sleep(2)

    def refresh(self):
        changed = False
        for k, _ in AGENT_DEFS:
            try:
                v = STATE_FILES[k].read_text(encoding="utf-8").strip().lower()
            except Exception:
                v = "off"
            v = v if v in STATE_RGB else "off"
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

    def contextMenuEvent(self, e):
        m = QMenu(self)
        for label, op in [("清晰", 1.0), ("高", 0.88), ("中", 0.72), ("低", 0.52)]:
            m.addAction("透明度 · " + label, lambda op=op: self.setWindowOpacity(op))
        m.addSeparator()
        m.addAction("退出", self.close)
        m.exec(e.globalPos())


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    Monitor()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
