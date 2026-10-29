import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QComboBox
from PySide6.QtCore import Qt

# Библиотека для управления и запуска Minecraft
import minecraft_launcher_lib
import math
import sys
import threading
import subprocess
import time
import uuid
import os
import json
import shutil
import zipfile
import hashlib
import random
from datetime import datetime
from html import escape

from PySide6.QtCore import (
    Property, QAbstractAnimation, QElapsedTimer, QEasingCurve, QPoint, QPointF,
    QPropertyAnimation, QRectF, Qt, QTimer, Signal, QSize
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPalette, QPen, QPixmap, QRadialGradient, QImage
)
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractItemView, QApplication, QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QSizePolicy, QStackedWidget, QTextEdit, QVBoxLayout, QWidget
)
import minecraft_launcher_lib

UI_FONTS = ["Segoe UI Variable", "Segoe UI", "Inter", "SF Pro Display", "Ubuntu", "Noto Sans", "DejaVu Sans"]
MONO_FONTS = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Menlo", "monospace"]
EMERALD = "#2fe0a4"

# =============================================================== хелперы
def rgba(r, g, b, a=255):
    return QColor(int(r), int(g), int(b), int(max(0, min(255, a))))

def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )

def make_anim(target, prop, duration=300, easing=QEasingCurve.Type.OutCubic):
    anim = QPropertyAnimation(target, prop, target)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve(easing))
    return anim

def run_anim(anim, start, end, duration=None):
    anim.stop()
    if duration is not None:
        anim.setDuration(max(1, int(duration)))
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.start()

def make_label(text, px, weight=QFont.Weight.Normal, color=None, spacing=0.0,
               align=Qt.AlignmentFlag.AlignCenter, wrap=False):
    label = QLabel(text)
    font = QFont(label.font())
    font.setPixelSize(px)
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    label.setFont(font)
    label.setAlignment(align)
    label.setWordWrap(wrap)
    pal = label.palette()
    pal.setColor(QPalette.ColorRole.WindowText, color or QColor("#dff7ec"))
    label.setPalette(pal)
    return label

def make_glow_pixmap(radius, color, alpha):
    size = radius * 2
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    grad = QRadialGradient(QPointF(radius, radius), radius)
    steps = 14
    for i in range(steps + 1):
        t = i / steps
        c = QColor(color)
        c.setAlpha(int(alpha * (1.0 - t) ** 2.4))
        grad.setColorAt(t, c)
    p = QPainter(pm)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawEllipse(QPointF(radius, radius), radius, radius)
    p.end()
    return pm

# ================================================================== фон
class Backdrop(QWidget):
    RADIUS = 30
    def __init__(self, parent=None):
        super().__init__(parent)
        self._clock = QElapsedTimer()
        self._clock.start()
        self._glows = [
            (make_glow_pixmap(380, QColor("#0c6e4c"), 140), 0.18, 0.24, 0.06, 0.07, 0.21, 0.17, 0.0),
            (make_glow_pixmap(420, QColor("#06402d"), 165), 0.86, 0.82, 0.05, 0.06, 0.19, 0.23, 1.7),
            (make_glow_pixmap(220, QColor("#1bc890"), 50), 0.62, 0.10, 0.09, 0.05, 0.27, 0.13, 3.1),
        ]
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    def paintEvent(self, event):
        t = self._clock.elapsed() / 1000.0
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        w, h = rect.width(), rect.height()
        clip = QPainterPath()
        clip.addRoundedRect(rect, self.RADIUS, self.RADIUS)
        p.setClipPath(clip)
        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor("#010403"))
        base.setColorAt(0.5, QColor("#030d09"))
        base.setColorAt(1.0, QColor("#010302"))
        p.fillRect(rect, base)
        for pm, bx, by, ax, ay, sx, sy, ph in self._glows:
            cx = w * (bx + ax * math.sin(t * sx + ph))
            cy = h * (by + ay * math.cos(t * sy + ph))
            r = pm.width() / 2
            p.drawPixmap(int(cx - r), int(cy - r), pm)
        p.setClipping(False)
        border = QLinearGradient(rect.topLeft(), rect.bottomRight())
        border.setColorAt(0.0, rgba(255, 255, 255, 64))
        border.setColorAt(0.5, rgba(255, 255, 255, 16))
        border.setColorAt(1.0, rgba(40, 220, 160, 52))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QBrush(border), 1))
        p.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

class GlassPanel(QFrame):
    def __init__(self, radius=26, parent=None):
        super().__init__(parent)
        self._radius = radius

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        p.fillPath(path, rgba(2, 10, 7, 120))
        fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
        fill.setColorAt(0.0, rgba(255, 255, 255, 26))
        fill.setColorAt(1.0, rgba(110, 255, 205, 5))
        p.fillPath(path, QBrush(fill))
        p.setClipPath(path)
        sheen_h = min(130.0, rect.height() / 2)
        sheen = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + sheen_h))
        sheen.setColorAt(0.0, rgba(255, 255, 255, 24))
        sheen.setColorAt(1.0, rgba(255, 255, 255, 0))
        p.fillRect(QRectF(rect.left(), rect.top(), rect.width(), sheen_h), sheen)
        p.setClipping(False)
        border = QLinearGradient(rect.topLeft(), rect.bottomRight())
        border.setColorAt(0.0, rgba(255, 255, 255, 105))
        border.setColorAt(0.45, rgba(255, 255, 255, 22))
        border.setColorAt(1.0, rgba(30, 215, 155, 85))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QBrush(border), 1.2))
        p.drawPath(path)

# ========================================================= кнопки окна
class WinButton(QAbstractButton):
    def __init__(self, kind, size=(34, 30), parent=None):
        super().__init__(parent)
        self._kind = kind
        self._hover = 0.0
        self.setFixedSize(*size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = make_anim(self, b"hoverAmount", 260)

    def _get_hover(self): return self._hover
    def _set_hover(self, v):
        self._hover = v
        self.update()
    hoverAmount = Property(float, _get_hover, _set_hover)

    def enterEvent(self, event):
        run_anim(self._anim, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        run_anim(self._anim, self._hover, 0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hover_bg = rgba(230, 70, 85, 175) if self._kind == "close" else rgba(30, 200, 140, 75)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mix(rgba(255, 255, 255, 12), hover_bg, self._hover))
        p.drawRoundedRect(rect, 9, 9)
        col = mix(rgba(255, 255, 255, 165), rgba(255, 255, 255, 255), self._hover)
        p.setPen(QPen(col, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx, cy = self.width() / 2, self.height() / 2
        if self._kind == "min":
            p.drawLine(QPointF(cx - 5, cy + 1), QPointF(cx + 5, cy + 1))
        elif self._kind == "close":
            d = 4.5
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
        else:
            p.drawLine(QPointF(cx - 2, cy - 5), QPointF(cx + 3, cy))
            p.drawLine(QPointF(cx + 3, cy), QPointF(cx - 2, cy + 5))

class ResizeGrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and hasattr(handle, "startSystemResize"):
                handle.startSystemResize(Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
            event.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(rgba(180, 240, 215, 70))
        for ix, iy in ((2, 0), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2)):
            p.drawEllipse(QPointF(self.width() - 6 - (2 - ix) * 4.5, self.height() - 6 - (2 - iy) * 4.5), 1.1, 1.1)

# ============================================================ навигация
class NavMenu(QWidget):
    changed = Signal(int)
    ITEM_H = 46
    GAP = 6

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = list(items)
        self._index = 0
        self._slide = 0.0
        self._hover_idx = -1
        self._hover_y = 0.0
        self._hover_a = 0.0
        self._ha_target = 0.0
        n = len(self._items)
        self.setFixedHeight(n * self.ITEM_H + (n - 1) * self.GAP)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._a_slide = make_anim(self, b"slideAmount", 560, QEasingCurve.Type.OutQuart)
        self._a_hy = make_anim(self, b"hoverY", 360, QEasingCurve.Type.OutCubic)
        self._a_ha = make_anim(self, b"hoverA", 300, QEasingCurve.Type.OutCubic)

    def _get_slide(self): return self._slide
    def _set_slide(self, v):
        self._slide = v
        self.update()
    def _get_hy(self): return self._hover_y
    def _set_hy(self, v):
        self._hover_y = v
        self.update()
    def _get_ha(self): return self._hover_a
    def _set_ha(self, v):
        self._hover_a = v
        self.update()

    slideAmount = Property(float, _get_slide, _set_slide)
    hoverY = Property(float, _get_hy, _set_hy)
    hoverA = Property(float, _get_ha, _set_ha)

    def _index_at(self, y):
        step = self.ITEM_H + self.GAP
        return int(max(0, min(len(self._items) - 1, y // step)))

    def _hover_to(self, idx):
        if idx < 0:
            if self._ha_target != 0.0:
                self._ha_target = 0.0
                run_anim(self._a_ha, self._hover_a, 0.0)
            self._hover_idx = -1
            return
        if idx != self._hover_idx:
            if self._hover_a < 0.05:
                self._a_hy.stop()
                self._set_hy(float(idx))
            else:
                run_anim(self._a_hy, self._hover_y, float(idx))
            self._hover_idx = idx
        if self._ha_target != 1.0:
            self._ha_target = 1.0
            run_anim(self._a_ha, self._hover_a, 1.0)

    def mouseMoveEvent(self, event):
        self._hover_to(self._index_at(event.position().y()))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_to(-1)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at(event.position().y())
            if idx != self._index:
                self._index = idx
                run_anim(self._a_slide, self._slide, float(idx))
                self.changed.emit(idx)
            event.accept()
        else:
            super().mousePressEvent(event)

    def _draw_icon(self, p, kind, cx, cy, color):
        p.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if kind == "home":
            roof = QPainterPath()
            roof.moveTo(cx - 8, cy)
            roof.lineTo(cx, cy - 7.5)
            roof.lineTo(cx + 8, cy)
            p.drawPath(roof)
            body = QPainterPath()
            body.moveTo(cx - 5.5, cy - 2.5)
            body.lineTo(cx - 5.5, cy + 7)
            body.lineTo(cx + 5.5, cy + 7)
            body.lineTo(cx + 5.5, cy - 2.5)
            p.drawPath(body)
        else:
            for dy, kx in ((-5.5, -3.0), (0.0, 3.5), (5.5, -1.0)):
                p.drawLine(QPointF(cx - 8, cy + dy), QPointF(cx + 8, cy + dy))
                p.setBrush(color)
                p.drawEllipse(QPointF(cx + kx, cy + dy), 2.3, 2.3)
                p.setBrush(Qt.BrushStyle.NoBrush)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        step = self.ITEM_H + self.GAP
        W = self.width()
        if self._hover_a > 0.01:
            r = QRectF(0, self._hover_y * step, W, self.ITEM_H)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(rgba(255, 255, 255, 15 * self._hover_a))
            p.drawRoundedRect(r, 14, 14)
        sel = QRectF(0.5, self._slide * step + 0.5, W - 1, self.ITEM_H - 1)
        grad = QLinearGradient(sel.topLeft(), sel.bottomLeft())
        grad.setColorAt(0.0, rgba(24, 190, 135, 225))
        grad.setColorAt(1.0, rgba(8, 105, 74, 235))
        p.setPen(QPen(rgba(120, 255, 210, 105), 1))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(sel, 14, 14)
        path = QPainterPath()
        path.addRoundedRect(sel, 14, 14)
        p.setClipPath(path)
        sheen = QLinearGradient(sel.topLeft(), QPointF(sel.left(), sel.center().y()))
        sheen.setColorAt(0.0, rgba(255, 255, 255, 58))
        sheen.setColorAt(1.0, rgba(255, 255, 255, 0))
        p.fillRect(QRectF(sel.left(), sel.top(), sel.width(), sel.height() / 2), sheen)
        p.setClipping(False)
        font = QFont(self.font())
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        muted = rgba(170, 205, 192, 175)
        lit = rgba(235, 255, 247, 255)
        white = rgba(255, 255, 255, 255)
        for i, (text, icon) in enumerate(self._items):
            near_sel = 1.0 - min(1.0, abs(i - self._slide))
            near_hov = self._hover_a * max(0.0, 1.0 - abs(i - self._hover_y))
            col = mix(mix(muted, lit, near_hov), white, near_sel)
            cy = i * step + self.ITEM_H / 2
            self._draw_icon(p, icon, 30, cy, col)
            p.setPen(col)
            p.drawText(QRectF(54, i * step, W - 54, self.ITEM_H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

# ========================================================= поле ввода
class GlassLineEdit(QLineEdit):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._focus = 0.0
        self._hover = 0.0
        self.setFixedHeight(50)
        self.setTextMargins(12, 0, 12, 0)
        self.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #eafff6;"
            " selection-background-color: rgba(25, 200, 140, 120); selection-color: #ffffff; }"
        )
        font = QFont(self.font())
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, rgba(170, 215, 198, 90))
        self.setPalette(pal)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._a_focus = make_anim(self, b"focusAmount", 380, QEasingCurve.Type.OutCubic)
        self._a_hover = make_anim(self, b"hoverAmount", 300, QEasingCurve.Type.OutCubic)

    def _get_focus(self): return self._focus
    def _set_focus(self, v):
        self._focus = v
        self.update()
    def _get_hover(self): return self._hover
    def _set_hover(self, v):
        self._hover = v
        self.update()

    focusAmount = Property(float, _get_focus, _set_focus)
    hoverAmount = Property(float, _get_hover, _set_hover)

    def focusInEvent(self, event):
        run_anim(self._a_focus, self._focus, 1.0)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        run_anim(self._a_focus, self._focus, 0.0)
        super().focusOutEvent(event)

    def enterEvent(self, event):
        run_anim(self._a_hover, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        run_anim(self._a_hover, self._hover, 0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mul = 1.0 if self.isEnabled() else 0.5
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        f = self._focus
        h = self._hover * (1.0 - f)
        bg = mix(rgba(0, 0, 0, 105), rgba(8, 48, 34, 150), max(f, h * 0.5))
        bg.setAlpha(int(bg.alpha() * mul))
        border = mix(mix(rgba(255, 255, 255, 34), rgba(60, 230, 170, 120), h), rgba(60, 235, 175, 215), f)
        border.setAlpha(int(border.alpha() * mul))
        p.setBrush(bg)
        p.setPen(QPen(border, 1.0 + 0.3 * f))
        p.drawRoundedRect(r, 15, 15)
        p.end()
        super().paintEvent(event)

# ======================================================= выбор версии
class PickerPopup(QWidget):
    picked = Signal(int)
    closed = Signal()
    ROW = 40
    PAD = 8
    MAX_ROWS = 6

    def __init__(self, owner):
        super().__init__(
            owner,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._reveal = 0.0
        self._base = QPoint()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(self.PAD, self.PAD, self.PAD, self.PAD)
        lay.setSpacing(0)
        self.list = QListWidget()
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setMouseTracking(True)
        font = QFont(self.list.font())
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.Medium)
        self.list.setFont(font)
        self.list.setStyleSheet(
            """
            QListWidget { background: transparent; border: none; outline: 0; }
            QListWidget::item { padding-left: 14px; margin: 1px 0; border-radius: 10px; color: #cdeee1; }
            QListWidget::item:hover { background: rgba(255, 255, 255, 18); color: #ffffff; }
            QListWidget::item:selected { background: rgba(20, 170, 120, 140); color: #ffffff; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 2px 0; }
            QScrollBar::handle:vertical { background: rgba(60, 220, 160, 80); border-radius: 3px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: rgba(60, 220, 160, 160); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """
        )
        self.list.itemClicked.connect(lambda item: self.picked.emit(self.list.row(item)))
        lay.addWidget(self.list)
        self._anim = make_anim(self, b"revealAmount", 260, QEasingCurve.Type.OutCubic)

    def _get_reveal(self): return self._reveal
    def _set_reveal(self, v):
        self._reveal = v
        self.setWindowOpacity(v)
        self.move(self._base.x(), self._base.y() - int(round((1.0 - v) * 10)))
    revealAmount = Property(float, _get_reveal, _set_reveal)

    def set_items(self, items):
        self.list.clear()
        for text in items:
            item = QListWidgetItem(text)
            item.setSizeHint(QSize(0, self.ROW))
            self.list.addItem(item)

    def popup_below(self, owner, current):
        rows = max(1, min(self.list.count(), self.MAX_ROWS))
        h = rows * self.ROW + 2 * self.PAD + 2
        self.setFixedSize(owner.width(), h)
        below = owner.mapToGlobal(QPoint(0, owner.height() + 6))
        screen = owner.screen()
        if screen is not None and below.y() + h > screen.availableGeometry().bottom():
            below = owner.mapToGlobal(QPoint(0, -h - 6))
        self._base = below
        if 0 <= current < self.list.count():
            self.list.setCurrentRow(current)
            self.list.scrollToItem(self.list.item(current), QAbstractItemView.ScrollHint.PositionAtCenter)
        self._set_reveal(0.0)
        self.show()
        run_anim(self._anim, 0.0, 1.0)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._anim.stop()
        self.closed.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        p.fillPath(path, rgba(3, 14, 10, 245))
        fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
        fill.setColorAt(0.0, rgba(255, 255, 255, 22))
        fill.setColorAt(1.0, rgba(110, 255, 205, 6))
        p.fillPath(path, QBrush(fill))
        border = QLinearGradient(rect.topLeft(), rect.bottomRight())
        border.setColorAt(0.0, rgba(255, 255, 255, 85))
        border.setColorAt(0.5, rgba(255, 255, 255, 22))
        border.setColorAt(1.0, rgba(30, 215, 155, 95))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QBrush(border), 1.1))
        p.drawPath(path)

class VersionPicker(QWidget):
    changed = Signal(str)
    def __init__(self, placeholder="Загрузка версий…", parent=None):
        super().__init__(parent)
        self._items = []
        self._index = -1
        self._placeholder = placeholder
        self._hover = 0.0
        self._open = 0.0
        self._closed_at = 0.0
        self.setFixedHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._popup = PickerPopup(self)
        self._popup.picked.connect(self._on_picked)
        self._popup.closed.connect(self._on_closed)
        self._a_hover = make_anim(self, b"hoverAmount", 300)
        self._a_open = make_anim(self, b"openAmount", 380, QEasingCurve.Type.OutCubic)

    def _get_hover(self): return self._hover
    def _set_hover(self, v):
        self._hover = v
        self.update()
    def _get_open(self): return self._open
    def _set_open(self, v):
        self._open = v
        self.update()

    hoverAmount = Property(float, _get_hover, _set_hover)
    openAmount = Property(float, _get_open, _set_open)

    def currentText(self):
        return self._items[self._index] if 0 <= self._index < len(self._items) else ""

    def set_items(self, items):
        old = self.currentText()
        self._items = list(items)
        self._popup.set_items(self._items)
        if not self._items:
            self._index = -1
        elif old in self._items:
            self._index = self._items.index(old)
        else:
            self._index = 0
        self.update()
        if self.currentText() != old:
            self.changed.emit(self.currentText())

    def set_placeholder(self, text):
        self._placeholder = text
        self.update()

    def _on_picked(self, idx):
        if 0 <= idx < len(self._items) and idx != self._index:
            self._index = idx
            self.update()
            self.changed.emit(self._items[idx])
        self._popup.hide()

    def _on_closed(self):
        self._closed_at = time.monotonic()
        run_anim(self._a_open, self._open, 0.0, 320)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled() and self._items:
            if time.monotonic() - self._closed_at < 0.25:
                event.accept()
                return
            run_anim(self._a_open, self._open, 1.0, 380)
            self._popup.popup_below(self, self._index)
            event.accept()
        else:
            super().mousePressEvent(event)

    def enterEvent(self, event):
        run_anim(self._a_hover, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        run_anim(self._a_hover, self._hover, 0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        mul = 1.0 if self.isEnabled() else 0.5
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        o = self._open
        h = self._hover * (1.0 - o)
        bg = mix(rgba(0, 0, 0, 105), rgba(8, 48, 34, 150), max(o, h * 0.5))
        bg.setAlpha(int(bg.alpha() * mul))
        border = mix(mix(rgba(255, 255, 255, 34), rgba(60, 230, 170, 120), h), rgba(60, 235, 175, 215), o)
        border.setAlpha(int(border.alpha() * mul))
        p.setBrush(bg)
        p.setPen(QPen(border, 1.0 + 0.3 * o))
        p.drawRoundedRect(r, 15, 15)
        font = QFont(self.font())
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        text = self.currentText() or self._placeholder
        col = rgba(255, 255, 255, 255 * mul) if self.currentText() else rgba(170, 215, 198, 110 * mul)
        p.setPen(col)
        p.drawText(QRectF(r.left() + 20, r.top(), r.width() - 60, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        p.save()
        p.translate(r.right() - 26, r.center().y())
        p.rotate(180.0 * o)
        p.setPen(QPen(rgba(60, 235, 175, 235 * mul), 1.8, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(-5, -2.5), QPointF(0, 2.5))
        p.drawLine(QPointF(0, 2.5), QPointF(5, -2.5))
        p.restore()

# ================================================== кнопка «Запустить»
class GlowButton(QAbstractButton):
    PAD = 16
    RADIUS = 20.0
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setFixedHeight(60 + 2 * self.PAD)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = 0.0
        self._press = 0.0
        self._busy = 0.0
        self._shimmer = 0.0
        self._busy_flag = False
        self._a_hover = make_anim(self, b"hoverAmount", 320)
        self._a_press = make_anim(self, b"pressAmount", 170)
        self._a_busy = make_anim(self, b"busyAmount", 650, QEasingCurve.Type.InOutCubic)
        self._a_shim = make_anim(self, b"shimmerAmount", 1700, QEasingCurve.Type.InOutSine)
        self._a_shim.setStartValue(0.0)
        self._a_shim.setEndValue(1.0)
        self._a_shim.setLoopCount(-1)
        self.pressed.connect(self._on_pressed)
        self.released.connect(self._on_released)

    def _get_hover(self): return self._hover
    def _set_hover(self, v):
        self._hover = v
        self.update()
    def _get_press(self): return self._press
    def _set_press(self, v):
        self._press = v
        self.update()
    def _get_busy(self): return self._busy
    def _set_busy(self, v):
        self._busy = v
        self.update()
    def _get_shimmer(self): return self._shimmer
    def _set_shimmer(self, v):
        self._shimmer = v
        self.update()

    hoverAmount = Property(float, _get_hover, _set_hover)
    pressAmount = Property(float, _get_press, _set_press)
    busyAmount = Property(float, _get_busy, _set_busy)
    shimmerAmount = Property(float, _get_shimmer, _set_shimmer)

    def set_busy(self, flag):
        self._busy_flag = flag
        run_anim(self._a_busy, self._busy, 1.0 if flag else 0.0)
        if flag:
            run_anim(self._a_hover, self._hover, 0.0)
            run_anim(self._a_press, self._press, 0.0)
            if self._a_shim.state() != QAbstractAnimation.State.Running:
                self._a_shim.start()
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            QTimer.singleShot(700, self._stop_shimmer)

    def _stop_shimmer(self):
        if not self._busy_flag:
            self._a_shim.stop()
            self._set_shimmer(0.0)

    def _pill_rect(self):
        return QRectF(self.PAD, self.PAD, self.width() - 2 * self.PAD, self.height() - 2 * self.PAD)

    def hitButton(self, pos):
        return self._pill_rect().contains(QPointF(pos))

    def _on_pressed(self):
        if not self._busy_flag:
            run_anim(self._a_press, self._press, 1.0)

    def _on_released(self):
        run_anim(self._a_press, self._press, 0.0)

    def enterEvent(self, event):
        if not self._busy_flag:
            run_anim(self._a_hover, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        run_anim(self._a_hover, self._hover, 0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        pill = self._pill_rect()
        radius = self.RADIUS
        busy = self._busy
        h = self._hover * (1.0 - busy)
        pulse = 0.5 + 0.5 * math.sin(self._shimmer * 2 * math.pi)
        strength = 0.55 + 0.55 * h - 0.2 * busy + 0.35 * busy * pulse
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(12, 0, -1):
            grow = i * 1.2
            p.setBrush(rgba(25, 225, 160, 7.0 * strength))
            r = pill.adjusted(-grow, -grow + 3, grow, grow + 3)
            p.drawRoundedRect(r, radius + grow, radius + grow)
        s = 1.0 - 0.03 * self._press
        c = pill.center()
        p.translate(c)
        p.scale(s, s)
        p.translate(-c)
        top = mix(mix(QColor("#34e3ab"), QColor("#62f5c8"), h), QColor("#0d3f2e"), busy)
        bot = mix(mix(QColor("#0c9a6e"), QColor("#13b886"), h), QColor("#062a1e"), busy)
        grad = QLinearGradient(pill.topLeft(), pill.bottomLeft())
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bot)
        path = QPainterPath()
        path.addRoundedRect(pill, radius, radius)
        p.fillPath(path, QBrush(grad))
        p.setClipPath(path)
        sheen = QLinearGradient(pill.topLeft(), QPointF(pill.left(), pill.center().y()))
        sheen.setColorAt(0.0, rgba(255, 255, 255, 80 * (1.0 - 0.6 * busy)))
        sheen.setColorAt(1.0, rgba(255, 255, 255, 0))
        p.fillRect(QRectF(pill.left(), pill.top(), pill.width(), pill.height() / 2), sheen)
        if busy > 0.01:
            band_w = pill.width() * 0.45
            x = pill.left() - band_w + (pill.width() + 2 * band_w) * self._shimmer
            sg = QLinearGradient(x, 0, x + band_w, 0)
            sg.setColorAt(0.0, rgba(120, 255, 205, 0))
            sg.setColorAt(0.5, rgba(120, 255, 205, 60 * busy))
            sg.setColorAt(1.0, rgba(120, 255, 205, 0))
            p.fillRect(QRectF(x, pill.top(), band_w, pill.height()), sg)
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(mix(rgba(255, 255, 255, 115), rgba(60, 230, 170, 110), busy), 1))
        p.drawPath(path)
        font = QFont(self.font())
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.ExtraBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.0)
        p.setFont(font)
        p.setPen(mix(QColor("#03150e"), QColor("#a8f0d4"), busy))
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, self.text())

# ===================================================== прогресс и статус
class ProgressLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = 0.0
        self._phase = 0.0
        self._flag = False
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._a_act = make_anim(self, b"activeAmount", 450, QEasingCurve.Type.InOutCubic)
        self._a_phase = make_anim(self, b"phaseAmount", 1500, QEasingCurve.Type.InOutSine)
        self._a_phase.setStartValue(0.0)
        self._a_phase.setEndValue(1.0)
        self._a_phase.setLoopCount(-1)

    def _get_active(self): return self._active
    def _set_active(self, v):
        self._active = v
        self.update()
    def _get_phase(self): return self._phase
    def _set_phase(self, v):
        self._phase = v
        self.update()

    activeAmount = Property(float, _get_active, _set_active)
    phaseAmount = Property(float, _get_phase, _set_phase)

    def set_active(self, flag):
        self._flag = flag
        run_anim(self._a_act, self._active, 1.0 if flag else 0.0)
        if flag:
            if self._a_phase.state() != QAbstractAnimation.State.Running:
                self._a_phase.start()
        else:
            QTimer.singleShot(550, self._stop_phase)

    def _stop_phase(self):
        if not self._flag:
            self._a_phase.stop()
            self._set_phase(0.0)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar_h = 5.0
        y = (self.height() - bar_h) / 2
        track = QRectF(0, y, self.width(), bar_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(rgba(255, 255, 255, 20))
        p.drawRoundedRect(track, 2.5, 2.5)
        if self._active > 0.01:
            clip = QPainterPath()
            clip.addRoundedRect(track, 2.5, 2.5)
            p.setClipPath(clip)
            seg = self.width() * 0.38
            x = -seg + (self.width() + seg) * self._phase
            grad = QLinearGradient(x, 0, x + seg, 0)
            grad.setColorAt(0.0, rgba(8, 100, 70, 0))
            grad.setColorAt(0.7, rgba(60, 245, 185, 230 * self._active))
            grad.setColorAt(1.0, rgba(150, 255, 220, 0))
            p.setBrush(QBrush(grad))
            p.drawRect(QRectF(x, y, seg, bar_h))

class StatusLine(QWidget):
    DOT = {
        "idle": (110, 200, 170), "busy": (60, 245, 185),
        "ok": (60, 245, 185), "error": (255, 110, 120),
    }
    TEXT = {
        "idle": (190, 235, 216, 140), "busy": (205, 245, 230, 190),
        "ok": (215, 255, 238, 215), "error": (255, 170, 176, 225),
    }

    def __init__(self, text="Готов к работе", kind="idle", parent=None):
        super().__init__(parent)
        self._text = text
        self._kind = kind
        self._pending = None
        self._phase = ""
        self._fade = 1.0
        self._pulse = 0.0
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._a_fade = make_anim(self, b"fadeAmount", 160, QEasingCurve.Type.OutCubic)
        self._a_fade.finished.connect(self._on_fade_done)
        self._a_pulse = make_anim(self, b"pulseAmount", 1400, QEasingCurve.Type.InOutSine)
        self._a_pulse.setStartValue(0.0)
        self._a_pulse.setEndValue(1.0)
        self._a_pulse.setLoopCount(-1)

    def _get_fade(self): return self._fade
    def _set_fade(self, v):
        self._fade = v
        self.update()
    def _get_pulse(self): return self._pulse
    def _set_pulse(self, v):
        self._pulse = v
        self.update()

    fadeAmount = Property(float, _get_fade, _set_fade)
    pulseAmount = Property(float, _get_pulse, _set_pulse)

    def set_status(self, text, kind="idle"):
        if self._pending is None and text == self._text and kind == self._kind:
            return
        self._pending = (text, kind)
        if self._phase != "out":
            run_anim(self._a_fade, self._fade, 0.0, 140)
            self._phase = "out"

    def _on_fade_done(self):
        if self._phase == "out":
            if self._pending is not None:
                self._text, self._kind = self._pending
                self._pending = None
            self._phase = "in"
            if self._kind == "busy":
                if self._a_pulse.state() != QAbstractAnimation.State.Running:
                    self._a_pulse.start()
            else:
                self._a_pulse.stop()
                self._set_pulse(0.0)
            run_anim(self._a_fade, 0.0, 1.0, 260)
        elif self._phase == "in":
            self._phase = ""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setOpacity(max(0.0, min(1.0, self._fade)))
        font = QFont(self.font())
        font.setPixelSize(12)
        p.setFont(font)
        fm = p.fontMetrics()
        text = fm.elidedText(self._text, Qt.TextElideMode.ElideRight, max(40, self.width() - 40))
        tw = fm.horizontalAdvance(text)
        gap, dot_d = 9, 8
        total = dot_d + gap + tw
        x0 = (self.width() - total) / 2
        cy = self.height() / 2
        dr, dg, db = self.DOT.get(self._kind, self.DOT["idle"])
        center = QPointF(x0 + dot_d / 2, cy)
        glow_r = 7 + 4 * self._pulse
        glow = QRadialGradient(center, glow_r)
        glow.setColorAt(0.0, rgba(dr, dg, db, 120 - 50 * self._pulse))
        glow.setColorAt(1.0, rgba(dr, dg, db, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(center, glow_r, glow_r)
        p.setBrush(rgba(dr, dg, db, 255))
        p.drawEllipse(center, dot_d / 2, dot_d / 2)
        tr, tg, tb, ta = self.TEXT.get(self._kind, self.TEXT["idle"])
        p.setPen(rgba(tr, tg, tb, ta))
        p.drawText(QRectF(x0 + dot_d + gap, 0, tw + 4, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

# ============================================================ панель логов
class LogPanel(QFrame):
    GAP = 14
    WIDTH = 300
    FULL = GAP + WIDTH
    LEVEL_COLORS = {
        "INFO": "#6fd8b3", "WARN": "#e2c26b", "OK": "#3df5b0", "ERR": "#ff7b86",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reveal = 0.0
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self.inner = QWidget(self)
        lay = QVBoxLayout(self.inner)
        lay.setContentsMargins(18, 16, 12, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title = make_label("ЖУРНАЛ", 10, QFont.Weight.Bold, rgba(150, 230, 200, 205), 2.6,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(title)
        head.addStretch(1)
        self.hide_btn = WinButton("chevron", size=(28, 22))
        self.hide_btn.clicked.connect(self.hide_panel)
        head.addWidget(self.hide_btn)
        lay.addLayout(head)
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        mono = QFont()
        mono.setFamilies(MONO_FONTS)
        mono.setPixelSize(11)
        self.view.setFont(mono)
        self.view.document().setDefaultFont(mono)
        self.view.setStyleSheet(
            """
            QTextEdit { background: transparent; border: none;
                        selection-background-color: rgba(25, 200, 140, 90); }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 2px 0; }
            QScrollBar::handle:vertical { background: rgba(60, 220, 160, 70);
                                          border-radius: 3px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: rgba(60, 220, 160, 150); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """
        )
        lay.addWidget(self.view, 1)
        self._anim = make_anim(self, b"revealAmount", 780)
        self._scroll = QPropertyAnimation(self.view.verticalScrollBar(), b"value", self)
        self._scroll.setDuration(260)
        self._scroll.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        self.setFixedWidth(1)
        self.hide()

    def _get_reveal(self): return self._reveal
    def _set_reveal(self, v):
        self._reveal = v
        if v <= 0.001:
            self.hide()
            return
        if self.isHidden():
            self.show()
        self.setFixedWidth(max(1, int(round(self.FULL * v))))
        self._fx.setOpacity(min(1.0, v * 1.4))
        self._fx.setEnabled(v < 0.999)
    revealAmount = Property(float, _get_reveal, _set_reveal)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.inner.setGeometry(self.GAP, 0, self.WIDTH, self.height())

    def show_panel(self):
        if self._reveal >= 0.999 and self._anim.state() != QAbstractAnimation.State.Running:
            return
        self._anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        run_anim(self._anim, self._reveal, 1.0, 780)

    def hide_panel(self):
        self._anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.InOutCubic))
        run_anim(self._anim, self._reveal, 0.0, 520)

    def add_line(self, level, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        color = self.LEVEL_COLORS.get(level, "#6fd8b3")
        tag = escape(level.ljust(4)).replace(" ", "&nbsp;")
        self.view.append(
            f'<span style="color:#4b7767">{stamp}</span>&nbsp;&nbsp;'
            f'<span style="color:{color}; font-weight:600">{tag}</span>&nbsp;&nbsp;'
            f'<span style="color:#cdeee1">{escape(text)}</span>'
        )
        QTimer.singleShot(0, self._scroll_to_end)

    def _scroll_to_end(self):
        sb = self.view.verticalScrollBar()
        run_anim(self._scroll, sb.value(), sb.maximum())

    def paintEvent(self, event):
        body = QRectF(self.GAP + 0.5, 0.5, self.width() - self.GAP - 1, self.height() - 1)
        if body.width() < 6:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(body, 24, 24)
        p.fillPath(path, rgba(1, 7, 5, 175))
        fill = QLinearGradient(body.topLeft(), body.bottomRight())
        fill.setColorAt(0.0, rgba(255, 255, 255, 18))
        fill.setColorAt(1.0, rgba(110, 255, 205, 4))
        p.fillPath(path, QBrush(fill))
        border = QLinearGradient(body.topLeft(), body.bottomRight())
        border.setColorAt(0.0, rgba(255, 255, 255, 70))
        border.setColorAt(0.5, rgba(255, 255, 255, 16))
        border.setColorAt(1.0, rgba(30, 215, 155, 70))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QBrush(border), 1))
        p.drawPath(path)

# ============================================================ страницы
class PageStack(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._o = 1.0
        self._target = 0
        self._phase = ""
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(1.0)
        self._fx.setEnabled(False)
        self.setGraphicsEffect(self._fx)
        self._anim = make_anim(self, b"fadeAmount", 160, QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_done)

    def _get_o(self): return self._o
    def _set_o(self, v):
        self._o = v
        self._fx.setEnabled(v < 0.999)
        self._fx.setOpacity(max(0.0, min(1.0, v)))
    fadeAmount = Property(float, _get_o, _set_o)

    def fade_to(self, index):
        self._target = index
        if self._phase == "out":
            return
        if index == self.currentIndex() and self._phase == "":
            return
        run_anim(self._anim, self._o, 0.0, 150)
        self._phase = "out"

    def _on_done(self):
        if self._phase == "out":
            self.setCurrentIndex(self._target)
            self._phase = "in"
            run_anim(self._anim, 0.0, 1.0, 320)
        elif self._phase == "in":
            self._phase = ""

# ========================================================= главное окно
class AutonomousMinecraftLauncher(QMainWindow):
    sig_status = Signal(str, str)
    sig_versions = Signal(list)
    sig_busy = Signal(bool)
    # НОВЫЙ СИГНАЛ ДЛЯ ПЕРЕНОСА ОТРИСОВКИ В GUI-ПОТОК
    sig_generate_textures = Signal(str, str) 

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Autonomous Minecraft Launcher (Offline)")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1100, 660)
        self.setMinimumSize(1040, 600)
        self.minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        self._drag_pos = None
        self._busy = False
        self._intro_started = False
        self._fading = False
        self._close_ready = False
        self._pack_done = threading.Event()
        self._pack_error = None
        
        self.init_ui()
        
        self.sig_status.connect(self._on_status)
        self.sig_versions.connect(self._on_versions)
        self.sig_busy.connect(self._on_busy)
        # ПОДКЛЮЧАЕМ НОВЫЙ СИГНАЛ К СЛОТУ В GUI-ПОТОКЕ
        self.sig_generate_textures.connect(self._do_generate_textures_in_gui)
        
        self.setWindowOpacity(0.0)
        self.load_versions()

    def init_ui(self):
        self.backdrop = Backdrop()
        self.setCentralWidget(self.backdrop)
        root = QHBoxLayout(self.backdrop)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)
        sidebar_frame = GlassPanel(22)
        sidebar_frame.setFixedWidth(220)
        sidebar = QVBoxLayout(sidebar_frame)
        sidebar.setContentsMargins(18, 24, 18, 20)
        sidebar.setSpacing(0)
        logo = make_label("◆  MINECRAFT", 17, QFont.Weight.ExtraBold, QColor(EMERALD), 2.0,
                          Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        sidebar.addWidget(logo)
        sidebar.addSpacing(30)
        self.nav = NavMenu([("Главная", "home"), ("Настройки", "settings")])
        self.nav.changed.connect(lambda i: self.pages.fade_to(i))
        sidebar.addWidget(self.nav)
        sidebar.addStretch(1)
        version_label = make_label("Autonomous v1.0", 12, QFont.Weight.Normal,
                                   rgba(190, 235, 216, 110), 0.5,
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        sidebar.addWidget(version_label)
        root.addWidget(sidebar_frame)
        right = QVBoxLayout()
        right.setSpacing(0)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addStretch(1)
        btn_min = WinButton("min")
        btn_min.clicked.connect(self.showMinimized)
        btn_close = WinButton("close")
        btn_close.clicked.connect(self.close)
        bar.addWidget(btn_min)
        bar.addWidget(btn_close)
        right.addLayout(bar)
        self.pages = PageStack()
        self.pages.addWidget(self._build_home_page())
        self.pages.addWidget(self._build_settings_page())
        right.addWidget(self.pages, 1)
        footer = make_label("PySide6 + minecraft-launcher-lib", 11, QFont.Weight.Normal,
                            rgba(190, 235, 216, 75), 0.8)
        right.addWidget(footer)
        root.addLayout(right, 1)
        self.grip = ResizeGrip(self)
        self.grip.raise_()

    def _build_home_page(self):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        self.card = GlassPanel(26)
        self.card.setFixedWidth(440)
        content = QVBoxLayout(self.card)
        content.setContentsMargins(38, 32, 38, 22)
        content.setSpacing(0)
        greeting = make_label("Автономный лаунчер", 30, QFont.Weight.ExtraBold, QColor("#f2fff9"), 0.5)
        description = make_label(
            "Введите никнейм для офлайн-режима, выберите версию и запустите игру.", 13,
            QFont.Weight.Normal, rgba(190, 235, 216, 150), wrap=True,
        )
        content.addWidget(greeting)
        content.addSpacing(6)
        content.addWidget(description)
        content.addSpacing(24)
        username_title = make_label("НИКНЕЙМ ИГРОКА", 10, QFont.Weight.Bold, QColor(EMERALD), 2.8,
                                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content.addWidget(username_title)
        content.addSpacing(8)
        self.username_input = GlassLineEdit("StekloPlayer")
        self.username_input.returnPressed.connect(self.start_launch_thread)
        content.addWidget(self.username_input)
        content.addSpacing(18)
        version_title = make_label("ВЕРСИЯ ИГРЫ", 10, QFont.Weight.Bold, QColor(EMERALD), 2.8,
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content.addWidget(version_title)
        content.addSpacing(8)
        self.version_box = VersionPicker()
        content.addWidget(self.version_box)
        content.addSpacing(8)
        self.play_button = GlowButton("ЗАПУСТИТЬ ИГРУ")
        self.play_button.clicked.connect(self.start_launch_thread)
        content.addWidget(self.play_button)
        self.progress = ProgressLine()
        content.addWidget(self.progress)
        content.addSpacing(4)
        self.status = StatusLine("Готов к работе", "idle")
        content.addWidget(self.status)
        self.log = LogPanel()
        row.addWidget(self.card)
        row.addWidget(self.log)
        row.addStretch(1)
        return page

    def _build_settings_page(self):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        card = GlassPanel(26)
        card.setFixedWidth(440)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(38, 32, 38, 30)
        lay.setSpacing(0)
        lay.addWidget(make_label("Настройки", 30, QFont.Weight.ExtraBold, QColor("#f2fff9"), 0.5))
        lay.addSpacing(6)
        lay.addWidget(make_label("Параметры автономного лаунчера.", 13, QFont.Weight.Normal,
                                 rgba(190, 235, 216, 150), wrap=True))
        lay.addSpacing(26)
        lay.addWidget(make_label("ПАПКА ИГРЫ", 10, QFont.Weight.Bold, QColor(EMERALD), 2.8,
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        lay.addSpacing(8)
        path_view = GlassLineEdit(str(self.minecraft_directory))
        path_view.setReadOnly(True)
        path_view.setCursorPosition(0)
        lay.addWidget(path_view)
        lay.addSpacing(18)
        lay.addWidget(make_label("Остальные параметры появятся позже.", 12, QFont.Weight.Normal,
                                 rgba(190, 235, 216, 100)))
        row.addWidget(card)
        row.addStretch(1)
        return page

    def _on_status(self, text, kind):
        self.status.set_status(text, kind)
        level = {"ok": "OK", "error": "ERR"}.get(kind, "INFO")
        self.log.add_line(level, text)
        if kind == "error":
            self.log.show_panel()

    def _on_versions(self, version_ids):
        self.version_box.set_items(version_ids)
        if not version_ids:
            self.version_box.set_placeholder("Нет списка версий")

    def _on_busy(self, flag):
        self._busy = flag
        self.play_button.set_busy(flag)
        self.play_button.setText("ЗАПУСК…" if flag else "ЗАПУСТИТЬ ИГРУ")
        self.version_box.setEnabled(not flag)
        self.username_input.setEnabled(not flag)
        self.progress.set_active(flag)
        if flag:
            self.log.show_panel()

    def load_versions(self):
        allowed_versions = ["1.21.1", "1.21.4", "1.20.4", "1.16.5"]
        self.sig_versions.emit(allowed_versions)
        self.sig_status.emit("Список версий успешно загружен (ограничен)", "ok")

    # ------------------------------------------------------------ ресурс-пак
    PACK_FORMATS = {
        "1.16.5": 6, "1.20.4": 22, "1.21.1": 34, "1.21.4": 46,
    }
    RP_NAME = "MinecraftOS_Theme"
    LEGACY_VERSIONS = {"1.16.5"}
    C_BLACK = "#010403"
    C_DARK = "#030d09"
    C_DEEP = "#06261b"
    C_EMERALD = "#2fe0a4"
    C_MINT = "#eafff6"

    @staticmethod
    def _save_png(img, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not img.save(path, "PNG"):
            raise RuntimeError(f"Не удалось сохранить текстуру: {path}")

    @staticmethod
    def _blank(w, h):
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        return img

    @staticmethod
    def _solid_tile(size, base, border=None):
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(QColor(base))
        if border is not None:
            p = QPainter(img)
            p.setPen(QColor(border))
            p.drawRect(0, 0, size - 1, size - 1)
            p.end()
        return img

    def _draw_button(self, state, t=0.5):
        fill = QColor("#000000")
        if state == "hover":
            edge = mix(QColor("#0a5a40"), QColor("#17a278"), t)
        elif state == "disabled":
            edge = QColor("#3b3b3b")
        else:
            edge = QColor("#e6e6e6")
        img = self._blank(200, 20)
        p = QPainter(img)
        p.fillRect(1, 1, 198, 18, fill)
        p.fillRect(1, 0, 198, 1, edge)
        p.fillRect(1, 19, 198, 1, edge)
        p.fillRect(0, 1, 1, 18, edge)
        p.fillRect(199, 1, 1, 18, edge)
        p.end()
        return img

    def _hover_strip(self):
        phases = (0.0, 0.5, 1.0, 0.5)
        strip = self._blank(200, 20 * len(phases))
        p = QPainter(strip)
        for i, t in enumerate(phases):
            p.drawImage(0, 20 * i, self._draw_button("hover", t))
        p.end()
        return strip

    def _text_logo(self, w, h, text="MINECRAFT"):
        img = self._blank(w, h)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = QFont()
        font.setFamilies(UI_FONTS)
        font.setWeight(QFont.Weight.DemiBold)
        px = int(h * 0.60)
        spacing = 0.0
        while px > 8:
            font.setPixelSize(px)
            spacing = px * 0.28
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
            if QFontMetrics(font).horizontalAdvance(text) <= w * 0.9:
                break
            px -= 2
        p.setFont(font)
        p.setPen(QColor(self.C_MINT))
        rect = QRectF(-spacing / 2, 0, w, h * 0.80)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        lw, lh = w * 0.12, max(2.0, h * 0.03)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.C_EMERALD))
        p.drawRoundedRect(QRectF((w - lw) / 2, h * 0.90, lw, lh), lh / 2, lh / 2)
        p.end()
        return img

    def _neon_logo(self, w, h):
        img = self._blank(w, h)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bold = QFont()
        bold.setFamilies(UI_FONTS)
        bold.setWeight(QFont.Weight.Black)
        light = QFont()
        light.setFamilies(UI_FONTS)
        light.setWeight(QFont.Weight.Light)
        neon, gap, rest = "NEON", " ", "Launcher"
        px = int(h * 0.62)
        while px > 8:
            bold.setPixelSize(px)
            light.setPixelSize(px)
            total = (QFontMetrics(bold).horizontalAdvance(neon + gap)
                     + QFontMetrics(light).horizontalAdvance(rest))
            if total <= w * 0.88:
                break
            px -= 2
        fm_b, fm_l = QFontMetrics(bold), QFontMetrics(light)
        x0 = (w - total) / 2
        base = (h + fm_b.ascent() - fm_b.descent()) / 2
        path_a = QPainterPath()
        path_a.addText(QPointF(x0, base), bold, neon)
        path_b = QPainterPath()
        path_b.addText(QPointF(x0 + fm_b.horizontalAdvance(neon + gap), base), light, rest)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, alpha in ((px * 0.34, 14), (px * 0.22, 26), (px * 0.12, 48)):
            pen = QPen(QColor(47, 224, 164, alpha), width, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPath(path_a)
            p.drawPath(path_b)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(path_a, QColor(self.C_EMERALD))
        p.fillPath(path_b, QColor(self.C_MINT))
        p.end()
        return img

    def _generate_logos(self, rp_dir, legacy):
        title_dir = os.path.join(rp_dir, "assets", "minecraft", "textures", "gui", "title")
        if legacy:
            full = self._text_logo(1240, 176)
            logo = self._blank(1024, 1024)
            p = QPainter(logo)
            p.drawImage(0, 0, full.copy(0, 0, 620, 176))
            p.drawImage(0, 180, full.copy(620, 0, 620, 176))
            p.end()
        else:
            logo = self._blank(1024, 256)
            p = QPainter(logo)
            p.drawImage(0, 0, self._text_logo(1024, 176))
            p.end()
        self._save_png(logo, os.path.join(title_dir, "minecraft.png"))
        self._save_png(self._blank(512, 64), os.path.join(title_dir, "edition.png"))
        mj = self._neon_logo(1024, 256)
        tex = self._blank(512, 512)
        p = QPainter(tex)
        p.drawImage(0, 0, mj.copy(0, 0, 512, 256))
        p.drawImage(0, 256, mj.copy(512, 0, 512, 256))
        p.end()
        self._save_png(tex, os.path.join(title_dir, "mojangstudios.png"))

    def _generate_buttons(self, rp_dir, version_id, legacy):
        gui_dir = os.path.join(rp_dir, "assets", "minecraft", "textures", "gui")
        states = {"normal": "button", "hover": "button_highlighted", "disabled": "button_disabled"}
        if legacy:
            jar = os.path.join(self.minecraft_directory, "versions", version_id, f"{version_id}.jar")
            try:
                with zipfile.ZipFile(jar) as z:
                    data = z.read("assets/minecraft/textures/gui/widgets.png")
            except Exception as e:
                print(f"widgets.png не найден в {jar}: {e}")
                return
            img = QImage.fromData(data)
            if img.isNull(): return
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
            p = QPainter(img)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            for y, st in ((46, "disabled"), (66, "normal"), (86, "hover")):
                p.drawImage(0, y, self._draw_button(st))
            p.end()
            self._save_png(img, os.path.join(gui_dir, "widgets.png"))
            return
        sprites = os.path.join(gui_dir, "sprites", "widget")
        meta = {"gui": {"scaling": {"type": "nine_slice", "width": 200, "height": 20, "border": 3}}}
        anim_meta = {
            "animation": {"frametime": 7, "interpolate": True, "width": 200, "height": 20},
            "gui": meta["gui"],
        }
        for st, name in states.items():
            if st == "hover":
                img, m = self._hover_strip(), anim_meta
            else:
                img, m = self._draw_button(st), meta
            self._save_png(img, os.path.join(sprites, f"{name}.png"))
            with open(os.path.join(sprites, f"{name}.png.mcmeta"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(m, f)

    def _generate_panorama(self, out_dir, size=512):
        top_c, mid_c, bot_c = QColor("#000000"), QColor("#000000"), QColor("#000000")
        side = QImage(size, size, QImage.Format.Format_ARGB32)
        side.fill(top_c)
        p = QPainter(side)
        grad = QLinearGradient(0, 0, 0, size)
        grad.setColorAt(0.0, top_c)
        grad.setColorAt(0.5, mid_c)
        grad.setColorAt(1.0, bot_c)
        p.fillRect(0, 0, size, size, grad)
        p.end()
        flat_top = QImage(size, size, QImage.Format.Format_ARGB32)
        flat_top.fill(top_c)
        flat_bot = QImage(size, size, QImage.Format.Format_ARGB32)
        flat_bot.fill(bot_c)
        for i, face in enumerate([side, side, side, side, flat_top, flat_bot]):
            self._save_png(face, os.path.join(out_dir, f"panorama_{i}.png"))

    def generate_custom_textures(self, rp_dir, version_id="1.21.1"):
        legacy = version_id in self.LEGACY_VERSIONS
        gui_dir = os.path.join(rp_dir, "assets", "minecraft", "textures", "gui")
        icon = self._blank(64, 64)
        icon.fill(QColor(self.C_DARK))
        p = QPainter(icon)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(self.C_EMERALD), 3))
        p.setBrush(QBrush(QColor("#062a1e")))
        p.drawRoundedRect(4, 4, 56, 56, 12, 12)
        gem = QPainterPath()
        gem.moveTo(32, 16)
        gem.lineTo(46, 32)
        gem.lineTo(32, 48)
        gem.lineTo(18, 32)
        gem.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(self.C_EMERALD)))
        p.drawPath(gem)
        p.end()
        self._save_png(icon, os.path.join(rp_dir, "pack.png"))
        tile = self._solid_tile(16, self.C_DARK, "#062a1e")
        for name in ("options_background.png", "menu_background.png", "menu_list_background.png",
                     "inworld_menu_background.png", "inworld_menu_list_background.png"):
            self._save_png(tile, os.path.join(gui_dir, name))
        sep = self._blank(32, 2)
        sp = QPainter(sep)
        sp.fillRect(0, 0, 32, 1, QColor("#14573f"))
        sp.fillRect(0, 1, 32, 1, QColor("#020a07"))
        sp.end()
        for name in ("header_separator.png", "footer_separator.png",
                     "inworld_header_separator.png", "inworld_footer_separator.png"):
            self._save_png(sep, os.path.join(gui_dir, name))
        self._generate_panorama(os.path.join(gui_dir, "title", "background"))
        self._generate_logos(rp_dir, legacy)
        self._generate_buttons(rp_dir, version_id, legacy)
        lang_dir = os.path.join(rp_dir, "assets", "minecraft", "lang")
        os.makedirs(lang_dir, exist_ok=True)
        labels = {
            "menu.singleplayer": "Играть офлайн", "menu.multiplayer": "Играть онлайн",
            "menu.options": "Настройки", "menu.quit": "Выход",
        }
        for code in ("en_us", "ru_ru"):
            with open(os.path.join(lang_dir, f"{code}.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(labels, f, ensure_ascii=False, indent=2)
        texts_dir = os.path.join(rp_dir, "assets", "minecraft", "texts")
        os.makedirs(texts_dir, exist_ok=True)
        splashes = ["MinecraftOS Active!", "Dark Theme Enabled!", "PySide6 Power!",
                    "Autonomous Launcher!", "Изумрудный интерфейс!"]
        with open(os.path.join(texts_dir, "splashes.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(splashes) + "\n")

    LOGO_ENTRY = "assets/minecraft/textures/gui/title/mojangstudios.png"

    def _patch_loading_logo(self, version_id, rp_dir):
        png_path = os.path.join(rp_dir, *self.LOGO_ENTRY.split("/"))
        with open(png_path, "rb") as f:
            png = f.read()
        jar = os.path.join(self.minecraft_directory, "versions", version_id, f"{version_id}.jar")
        if not os.path.isfile(jar):
            return "jar версии не найден"
        marker = jar + ".neon"
        stamp = hashlib.sha1(png).hexdigest()
        try:
            with open(marker, "r", encoding="utf-8") as f:
                old_stamp, old_size = f.read().split(":")
            if old_stamp == stamp and int(old_size) == os.path.getsize(jar):
                return None
        except Exception:
            pass
        backup = jar + ".orig"
        if not os.path.exists(backup):
            shutil.copy2(jar, backup)
        tmp = jar + ".tmp"
        found = False
        with zipfile.ZipFile(jar) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == self.LOGO_ENTRY:
                    zout.writestr(item, png)
                    found = True
                else:
                    zout.writestr(item, zin.read(item.filename))
        if not found:
            os.remove(tmp)
            return "в jar нет mojangstudios.png"
        os.replace(tmp, jar)
        with open(marker, "w", encoding="utf-8") as f:
            f.write(f"{stamp}:{os.path.getsize(jar)}")
        return None

    def _do_generate_textures_in_gui(self, rp_dir, version_id):
        """Слот, выполняющийся строго в главном (GUI) потоке."""
        try:
            self.generate_custom_textures(rp_dir, version_id)
            problem = self._patch_loading_logo(version_id, rp_dir)
            if problem:
                self.log.add_line("WARN", f"Логотип загрузки не заменён: {problem}")
        except Exception as e:
            self._pack_error = e
        finally:
            # Разблокируем фоновый поток
            self._pack_done.set()

    def setup_resource_pack(self, version_id="1.21.1"):
        rp_dir = os.path.join(self.minecraft_directory, "resourcepacks", self.RP_NAME)
        if os.path.isdir(rp_dir):
            shutil.rmtree(rp_dir, ignore_errors=True)
        os.makedirs(rp_dir, exist_ok=True)
        
        # --- ИСПРАВЛЕНИЕ: Передаем генерацию в главный поток и ждем ---
        self._pack_error = None
        self._pack_done = threading.Event()
        self.sig_generate_textures.emit(rp_dir, version_id)
        
        if not self._pack_done.wait(60):
            raise RuntimeError("не удалось подготовить ресурс-пак (таймаут)")
        if self._pack_error is not None:
            raise self._pack_error
        # --------------------------------------------------------------

        pack_format = self.PACK_FORMATS.get(version_id, 34)
        mcmeta = {"pack": {"pack_format": pack_format,
                           "description": f"MinecraftOS Custom Theme ({version_id})"}}
        with open(os.path.join(rp_dir, "pack.mcmeta"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(mcmeta, f, ensure_ascii=False, indent=4)
            
        forced = {
            "resourcePacks": '["vanilla","file/%s"]' % self.RP_NAME,
            "incompatibleResourcePacks": "[]",
            "darkMojangStudiosBackground": "true",
        }
        options_path = os.path.join(self.minecraft_directory, "options.txt")
        lines = []
        if os.path.exists(options_path):
            try:
                with open(options_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except Exception:
                lines = []
        seen = set()
        out = []
        for line in lines:
            key = line.split(":", 1)[0]
            if key in forced:
                out.append(f"{key}:{forced[key]}")
                seen.add(key)
            else:
                out.append(line)
        for key, val in forced.items():
            if key not in seen:
                out.append(f"{key}:{val}")
        with open(options_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")

    def start_launch_thread(self):
        if self._busy:
            return
        version_id = self.version_box.currentText()
        username = self.username_input.text().strip() or "Player"
        if not version_id:
            self.sig_status.emit("Выберите версию игры!", "error")
            return
        self.sig_busy.emit(True)
        threading.Thread(target=self.launch_game, args=(version_id, username), daemon=True).start()

    def launch_game(self, version_id, username):
        try:
            installed_versions = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_directory)
            installed_ids = [v["id"] for v in installed_versions]
            if version_id not in installed_ids:
                self.sig_status.emit(f"Скачивание файлов версии {version_id}...", "busy")
                minecraft_launcher_lib.install.install_minecraft_version(version_id, self.minecraft_directory)
            
            self.sig_status.emit(f"Настройка темы MinecraftOS (версия {version_id})...", "busy")
            self.setup_resource_pack(version_id)
            
            self.sig_status.emit("Подготовка к запуску...", "busy")
            player_uuid = str(uuid.uuid4())
            options = {
                "username": username,
                "uuid": player_uuid,
                "token": "",
            }
            minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
                version_id, self.minecraft_directory, options
            )
            subprocess.Popen(minecraft_command, cwd=self.minecraft_directory)
            self.sig_status.emit(f"Игра запущена! (Игрок: {username})", "ok")
        except Exception as e:
            self.sig_status.emit(f"Ошибка запуска: {str(e)}", "error")
        finally:
            self.sig_busy.emit(False)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._intro_started:
            self._intro_started = True
            QTimer.singleShot(40, self._play_intro)

    def _play_intro(self):
        end = self.pos()
        self.move(end + QPoint(0, 26))
        self._a_pos = make_anim(self, b"pos", 1000, QEasingCurve.Type.OutCubic)
        run_anim(self._a_pos, end + QPoint(0, 26), end)
        self._a_fade = make_anim(self, b"windowOpacity", 800, QEasingCurve.Type.OutCubic)
        run_anim(self._a_fade, 0.0, 1.0)

    def closeEvent(self, event):
        if self._close_ready:
            event.accept()
            return
        event.ignore()
        if self._fading:
            return
        self._fading = True
        self._a_out = make_anim(self, b"windowOpacity", 280, QEasingCurve.Type.InCubic)
        self._a_out.finished.connect(self._finish_close)
        run_anim(self._a_out, self.windowOpacity(), 0.0)

    def _finish_close(self):
        self._close_ready = True
        self.close()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width() - 6, self.height() - self.grip.height() - 6)
        self.grip.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None and hasattr(handle, "startSystemMove"):
                if handle.startSystemMove():
                    event.accept()
                    return
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

# ======================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont()
    font.setFamilies(UI_FONTS)
    font.setPointSize(10)
    app.setFont(font)
    window = AutonomousMinecraftLauncher()
    window.show()
    sys.exit(app.exec())