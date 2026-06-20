"""Shared layout helper for all department menus.

Each department menu passes a title and a list of (label, action) tuples:
  - action returns a QWidget  → shown inline in a content pane below the grid
  - action returns None       → side-effect already ran (e.g. _launch called)

Widget results are lazily created and cached: re-clicking the same button
reuses the cached widget without re-calling the factory.
Script items re-launch on every click.
"""
import traceback
from PyQt6 import QtCore, QtWidgets
from .accounts import get_current_user_email
from .qt_theme import apply_blue_palette as _apply_blue_palette

_DEPT_BTN = (
    "QPushButton{background-color:white;border:2px solid black;"
    "border-radius:10px;padding:10px 16px;font-size:15px;}"
    "QPushButton:hover{background-color:rgb(85,255,255);"
    "border-color:rgb(85,255,255);}"
    "QPushButton:checked{background-color:rgb(85,255,255);"
    "border:2px solid black;font-weight:bold;}"
)

_QSIZE_MAX = 16_777_215   # Qt's QWIDGETSIZE_MAX


class DeptMenuWidget(QtWidgets.QWidget):
    def __init__(self, title, items, cols=3, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self.setAutoFillBackground(True)
        self._factories = [action for _, action in items]
        self._page_indices = {}   # btn_idx → stack page index (widget items)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────
        toolbar = QtWidgets.QWidget()
        toolbar.setStyleSheet("background-color:rgb(0,60,180);")
        toolbar.setFixedHeight(44)
        tr = QtWidgets.QHBoxLayout(toolbar)
        tr.setContentsMargins(16, 0, 16, 0)
        tr.setSpacing(12)
        tr.addStretch()
        email = get_current_user_email()
        if email:
            lbl = QtWidgets.QLabel(f"Logged in as: {email}")
            lbl.setStyleSheet("color:white;font-size:13px;padding-right:12px;")
            tr.addWidget(lbl)
        outer.addWidget(toolbar)

        # ── Header: title + button grid ──────────────────────────
        header = QtWidgets.QWidget()
        _apply_blue_palette(header)
        header.setAutoFillBackground(True)
        hv = QtWidgets.QVBoxLayout(header)
        hv.setContentsMargins(20, 32, 20, 24)
        hv.setSpacing(0)

        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("color:white;font-size:22px;font-weight:bold;")
        hv.addWidget(title_lbl)
        hv.addSpacing(20)

        grid_wrap = QtWidgets.QWidget()
        _apply_blue_palette(grid_wrap)
        grid_wrap.setAutoFillBackground(True)
        grid = QtWidgets.QGridLayout(grid_wrap)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)

        self._btns = []
        for i, (label, _) in enumerate(items):
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(_DEPT_BTN)
            btn.setCheckable(True)
            btn.setMinimumWidth(180)
            btn.setFixedHeight(54)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: self._on_click(idx))
            grid.addWidget(btn, i // cols, i % cols)
            self._btns.append(btn)

        center_row = QtWidgets.QHBoxLayout()
        center_row.addStretch()
        center_row.addWidget(grid_wrap)
        center_row.addStretch()
        hv.addLayout(center_row)

        # Prevent the header from expanding to fill space claimed by the
        # collapsed stack; it should be exactly as tall as its content.
        header.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        outer.addWidget(header)

        # ── Content stack ─────────────────────────────────────────
        # When stack is maxH=0 (hidden), Qt would distribute unclaimed space
        # around all items (space-around) without a trailing stretch absorber.
        # addStretch(1) captures that space so toolbar stays pinned to y=0.
        # stretch=100 on the stack means it wins the space race vs the stretch
        # spacer when the stack is expanded (maxH=_QSIZE_MAX).
        self._stack = QtWidgets.QStackedWidget()
        self._stack.setMaximumHeight(0)
        outer.addWidget(self._stack, 100)
        outer.addStretch(1)

        # Auto-open single-item menus (e.g. Reports Dashboard)
        if len(items) == 1:
            self._on_click(0)

    def _on_click(self, idx):
        # Already cached as a widget — just switch to it
        if idx in self._page_indices:
            self._stack.setCurrentIndex(self._page_indices[idx])
            self._stack.setMaximumHeight(_QSIZE_MAX)
            self._set_checked(idx)
            return

        try:
            result = self._factories[idx]()
        except Exception:
            msg = traceback.format_exc()
            QtWidgets.QMessageBox.critical(self, "Error opening panel", msg)
            self._set_checked(-1)
            return

        if not isinstance(result, QtWidgets.QWidget):
            # Script launched — collapse stack, clear highlights
            self._stack.setMaximumHeight(0)
            self._set_checked(-1)
            return

        page_idx = self._stack.count()
        self._stack.addWidget(result)
        self._page_indices[idx] = page_idx
        self._stack.setCurrentIndex(page_idx)
        self._stack.setMaximumHeight(_QSIZE_MAX)
        self._set_checked(idx)

    def _set_checked(self, active_idx):
        for i, btn in enumerate(self._btns):
            btn.setChecked(i == active_idx)
