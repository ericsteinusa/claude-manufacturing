"""Button-based navigation widget used in place of ``QTabWidget``.

The department menus used to present their sections as tabs. They now show a
vertical column of buttons on the left that swap the content shown in a
``QStackedWidget`` on the right (left buttons, right content).

``ButtonNav`` is a drop-in replacement for ``QtWidgets.QTabWidget``: it
implements the small slice of the tab-widget API the menus actually use
(``addTab``, ``setCurrentIndex``, ``count``, ``tabText``, plus no-op
``setStyleSheet``/``setTabPosition``), so call sites only swap the
constructor.

Like every other Qt module here it cannot be imported under CI (no libEGL);
keep logic that needs testing in ``*_core.py`` modules.
"""
from PyQt6 import QtCore, QtWidgets

# White pill button; cyan on hover and when it is the active page. Mirrors the
# BUTTON_STYLE used elsewhere in the menus, with a left-aligned label and a
# checked state so the current section is highlighted.
NAV_BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; "
    "border-radius: 10px; padding: 8px 16px; text-align: left;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); "
    "border: 2px solid rgb(85, 255, 255);}"
    "QPushButton:checked{background-color: rgb(85, 255, 255); "
    "border: 2px solid black; font-weight: bold;}"
)


class ButtonNav(QtWidgets.QWidget):
    """A left-hand button column that switches pages in a stacked area."""

    # Mirrors QTabWidget.currentChanged so menus that lazy-load on tab change
    # (``self.tabs.currentChanged.connect(...)``) keep working unchanged.
    currentChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = []
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._col = QtWidgets.QVBoxLayout()
        self._col.setSpacing(6)
        self._col.addStretch(1)
        col_host = QtWidgets.QWidget()
        col_host.setLayout(self._col)
        outer.addWidget(col_host)

        self._stack = QtWidgets.QStackedWidget()
        outer.addWidget(self._stack, 1)

    # -- QTabWidget-compatible API ---------------------------------------
    def addTab(self, widget, label):
        index = self._stack.count()
        self._stack.addWidget(widget)

        btn = QtWidgets.QPushButton(str(label))
        btn.setCheckable(True)
        btn.setStyleSheet(NAV_BUTTON_STYLE)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(
            lambda _checked=False, i=index: self.setCurrentIndex(i))

        self._group.addButton(btn, index)
        # Insert above the trailing stretch so buttons stay top-aligned.
        self._col.insertWidget(self._col.count() - 1, btn)
        self._buttons.append(btn)

        if index == 0:
            btn.setChecked(True)
        return index

    def setCurrentIndex(self, index):
        if 0 <= index < self._stack.count():
            changed = index != self._stack.currentIndex()
            self._stack.setCurrentIndex(index)
            btn = self._group.button(index)
            if btn is not None:
                btn.setChecked(True)
            if changed:
                self.currentChanged.emit(index)

    def currentIndex(self):
        return self._stack.currentIndex()

    def count(self):
        return self._stack.count()

    def widget(self, index):
        return self._stack.widget(index)

    def tabText(self, index):
        if 0 <= index < len(self._buttons):
            return self._buttons[index].text()
        return ""

    def setTabText(self, index, label):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setText(str(label))

    # The old tab CSS targeted QTabBar; it no longer applies. Accept the call
    # so existing ``setStyleSheet(TAB_STYLE)`` lines keep working as no-ops.
    def setStyleSheet(self, styleSheet: str = "") -> None:  # type: ignore[override]
        pass

    def setTabPosition(self, _position):
        pass
