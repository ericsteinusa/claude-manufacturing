"""bom.py — item-master extensions and shared BOM helpers.

This is PR 1 of the BOM/MRP track. The app already has a flat single-level
``bom`` table and editor (in :mod:`prod_prod_menu`):

    bom(id, product_id, component_id, qty_required, unit, notes)

— one row per "parent ``product_id`` is built from ``component_id``" edge.
That edge list is all MRP needs: multi-level explosion falls out by recursing
(a component can itself be another row's ``product_id``). Rather than add a
parallel structure, this module *builds on* that table.

PR 1 adds, without changing existing behaviour:

* **Item-master fields** on ``product`` — ``item_type`` ('make' | 'buy'),
  ``lead_time_days`` and ``uom`` — so planning can tell manufactured items
  (explode + plan a work order) from purchased ones (plan a requisition), and
  how far ahead to offset a planned order.
* **``scrap_pct``** on the existing ``bom`` table, so component requirements
  can be inflated for expected scrap.
* A small :class:`ItemSettingsDialog` to maintain the item-master fields, and
  shared helpers (:func:`get_components`, the cycle guard) used by the editor
  today and by MRP later.

All schema changes use ``ADD COLUMN IF NOT EXISTS`` and are idempotent. The
cycle guard's core, :func:`would_create_cycle`, is a pure function so it can be
unit tested without a database.
"""

import sys

import psycopg2
from PyQt6 import QtCore, QtWidgets
from .qt_theme import (
    INPUT_STYLE,
    COMBO_STYLE,
    LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette,
)


from .bom_core import would_create_cycle, explode_quantity
from .db_pg import get_db_connection
from .log_utils import get_logger

log = get_logger(__name__)

# Re-exported for callers that import them from this module. The pure
# implementations live in bom_core so they can be imported without Qt.
__all__ = ["would_create_cycle", "explode_quantity"]


ITEM_TYPES = ("make", "buy")


def get_db():
    return get_db_connection()


# ── Schema reconciliation ───────────────────────────────────────────────

def ensure_item_master_columns(conn):
    """Add the make/buy, lead-time and unit-of-measure columns to product.

    Idempotent; safe on a pre-existing ``product`` table.
    """
    conn.execute(
        "ALTER TABLE product "
        "ADD COLUMN IF NOT EXISTS item_type TEXT DEFAULT 'buy'")
    conn.execute(
        "ALTER TABLE product "
        "ADD COLUMN IF NOT EXISTS lead_time_days INTEGER DEFAULT 0")
    conn.execute(
        "ALTER TABLE product "
        "ADD COLUMN IF NOT EXISTS uom TEXT DEFAULT 'ea'")


def ensure_bom_columns(conn):
    """Add ``scrap_pct`` to the existing flat ``bom`` table. Idempotent."""
    conn.execute(
        "ALTER TABLE bom "
        "ADD COLUMN IF NOT EXISTS scrap_pct REAL DEFAULT 0.0")


def init_item_master():
    """Reconcile the product item-master and BOM columns (idempotent).

    Resilient: on a brand-new database where ``product``/``bom`` don't exist
    yet, the ALTERs are rolled back and skipped rather than crashing the
    caller — the columns get added on a later startup once those tables exist
    (created by the inventory / production modules).
    """
    conn = get_db()
    try:
        ensure_item_master_columns(conn)
        ensure_bom_columns(conn)
        conn.commit()
    except psycopg2.Error:
        conn._conn.rollback()
        log.debug("init_item_master skipped (tables not present yet)",
                  exc_info=True)
    finally:
        conn.close()


# ── Cycle protection ────────────────────────────────────────────────────

def bom_would_create_cycle(conn, parent_id, component_id):
    """DB-backed cycle check across the flat ``bom`` edge list."""
    rows = conn.execute(
        "SELECT product_id AS parent, component_id AS component FROM bom"
    ).fetchall()
    edges = [(r["parent"], r["component"]) for r in rows]
    return would_create_cycle(edges, parent_id, component_id)


# ── Shared queries ──────────────────────────────────────────────────────

def get_components(conn, product_id):
    """Return the direct components of a product (one BOM level).

    Joins the component's name and item-master fields so callers (the editor
    today, MRP/work-order explosion later) get everything in one query.
    """
    return conn.execute(
        "SELECT b.id, b.component_id, b.qty_required, "
        "COALESCE(b.scrap_pct, 0.0) AS scrap_pct, b.unit, b.notes, "
        "p.name AS component_name, p.item_type, p.lead_time_days, p.uom "
        "FROM bom b JOIN product p ON p.id = b.component_id "
        "WHERE b.product_id = %s ORDER BY p.name",
        (product_id,)
    ).fetchall()


# ── Work-order explosion ────────────────────────────────────────────────

def explode_bom_to_wo(conn, wo_id, product_id, wo_quantity):
    """Populate ``wo_material`` from the finished good's single-level BOM.

    Returns the number of component lines created. A no-op (returns 0) when
    the product has no BOM, so a work order for an item without a BOM keeps
    its hand-entered material list working exactly as before. Issued
    quantities start at zero; only the required quantity is seeded.

    Runs on the caller's connection and does not commit, so it composes into
    the same transaction that inserts the work order.
    """
    components = get_components(conn, product_id)
    for c in components:
        qty = explode_quantity(
            c["qty_required"], wo_quantity, c["scrap_pct"])
        note = c["notes"] or "from BOM"
        conn.execute(
            "INSERT INTO wo_material (wo_id, product_id, qty_required, notes) "
            "VALUES (%s, %s, %s, %s)",
            (wo_id, c["component_id"], qty, note))
    return len(components)


# ── Item-master editor ──────────────────────────────────────────────────


def _lbl(t):
    w = QtWidgets.QLabel(t)
    w.setStyleSheet(LABEL_STYLE)
    return w


class ItemSettingsDialog(QtWidgets.QDialog):
    """Maintain make/buy, lead-time and unit-of-measure for any product.

    Self-contained: it picks the product from a combo, so it can be opened
    from anywhere without a pre-selected item. Each ``Save`` persists the
    fields for the currently selected product.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Item Settings")
        self.resize(420, 220)
        _apply_blue_palette(self)
        init_item_master()
        self._build_ui()
        self._reload_products()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        self.product = QtWidgets.QComboBox()
        self.product.setStyleSheet(COMBO_STYLE)
        self.product.setMinimumWidth(220)
        self.product.currentIndexChanged.connect(self._load_selected)
        layout.addRow(_lbl("Product:"), self.product)

        self.item_type = QtWidgets.QComboBox()
        self.item_type.setStyleSheet(COMBO_STYLE)
        for t in ITEM_TYPES:
            self.item_type.addItem(t.capitalize(), t)
        layout.addRow(_lbl("Item Type:"), self.item_type)

        self.lead_time = QtWidgets.QSpinBox()
        self.lead_time.setRange(0, 3650)
        self.lead_time.setSuffix(" days")
        self.lead_time.setStyleSheet(INPUT_STYLE)
        layout.addRow(_lbl("Lead Time:"), self.lead_time)

        self.uom = QtWidgets.QLineEdit()
        self.uom.setStyleSheet(INPUT_STYLE)
        self.uom.setPlaceholderText("ea, kg, m, …")
        layout.addRow(_lbl("Unit of Measure:"), self.uom)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save |
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        btns.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save
        ).clicked.connect(self._on_save)
        btns.button(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        ).clicked.connect(self.accept)
        layout.addRow(btns)

    def _reload_products(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT id, name FROM product ORDER BY name").fetchall()
        conn.close()
        self.product.blockSignals(True)
        self.product.clear()
        for r in rows:
            self.product.addItem(r["name"], r["id"])
        self.product.blockSignals(False)
        self._load_selected()

    def _load_selected(self):
        pid = self.product.currentData()
        if pid is None:
            return
        conn = get_db()
        rec = conn.execute(
            "SELECT item_type, lead_time_days, uom FROM product WHERE id = %s",
            (pid,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        idx = self.item_type.findData(rec["item_type"] or "buy")
        self.item_type.setCurrentIndex(idx if idx >= 0 else 0)
        self.lead_time.setValue(rec["lead_time_days"] or 0)
        self.uom.setText(rec["uom"] or "ea")

    def _on_save(self):
        pid = self.product.currentData()
        if pid is None:
            return
        uom = self.uom.text().strip() or "ea"
        conn = get_db()
        conn.execute(
            "UPDATE product SET item_type = %s, lead_time_days = %s, "
            "uom = %s WHERE id = %s",
            (self.item_type.currentData(), self.lead_time.value(), uom, pid)
        )
        conn.commit()
        conn.close()
        QtWidgets.QMessageBox.information(
            self, "Saved", "Item settings saved.")


def main():
    init_item_master()
    app = QtWidgets.QApplication(sys.argv)
    dlg = ItemSettingsDialog()
    dlg.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
