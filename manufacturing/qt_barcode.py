"""
Desktop barcode utilities: scan routing and PDF label printing.
Shared by all desktop modules that embed a ScanBar.
"""
from __future__ import annotations
import os
import tempfile

from .barcode_core import parse_scan
from .db_pg import get_db_connection


# ── Record lookup ─────────────────────────────────────────────────────────────

def lookup_record(raw: str) -> dict | None:
    """
    Given a raw scan string, return a dict describing the record found:
        {"type": "wo"|"po"|"inventory"|"asset"|"receiving",
         "id": int, "label": str, "record": dict}
    Returns None if not found.
    """
    result = parse_scan(raw)
    if result is None:
        return None
    rtype, key = result
    conn = get_db_connection()
    try:
        if rtype == "wo":
            row = conn.execute(
                "SELECT * FROM work_order WHERE wo_number = %s", [key]
            ).fetchone()
            if row:
                d = dict(row)
                return {"type": "wo", "id": d["id"],
                        "label": f"WO {d['wo_number']}", "record": d}

        elif rtype == "inventory":
            row = None
            if key.isdigit():
                row = conn.execute(
                    "SELECT * FROM product WHERE id = %s", [int(key)]
                ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM product WHERE UPPER(name) = %s", [key.upper()]
                ).fetchone()
            if row:
                d = dict(row)
                return {"type": "inventory", "id": d["id"],
                        "label": f"Part {d['name']}", "record": d}

        elif rtype in ("po", "receiving"):
            row = conn.execute(
                "SELECT * FROM purchase_order WHERE po_number = %s", [key]
            ).fetchone()
            if row:
                d = dict(row)
                return {"type": "po", "id": d["id"],
                        "label": f"PO {d['po_number']}", "record": d}

        elif rtype == "asset":
            row = conn.execute(
                "SELECT * FROM it_asset WHERE asset_tag = %s", [key]
            ).fetchone()
            if row:
                d = dict(row)
                return {"type": "asset", "id": d["id"],
                        "label": f"Asset {d['asset_tag']}", "record": d}
    finally:
        conn.close()
    return None


# ── PDF label printing ────────────────────────────────────────────────────────

def print_label(raw: str) -> tuple[bool, str]:
    """
    Generate and open a PDF label for the scanned code.
    Returns (success, message).
    """
    from .barcode_core import (
        wo_label_pdf, part_label_pdf, po_label_pdf, asset_label_pdf,
    )
    result = lookup_record(raw)
    if result is None:
        return False, f"No record found for: {raw}"

    rtype = result["type"]
    rec = result["record"]

    try:
        if rtype == "wo":
            pdf = wo_label_pdf(rec)
        elif rtype == "inventory":
            pdf = part_label_pdf(rec)
        elif rtype == "po":
            pdf = po_label_pdf(rec)
        elif rtype == "asset":
            pdf = asset_label_pdf(rec)
        else:
            return False, f"No label template for: {rtype}"

        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(pdf)
        os.startfile(path)   # Windows — opens in default PDF viewer
        return True, f"Label opened for {result['label']}"
    except Exception as e:
        return False, str(e)


def print_label_linux(raw: str) -> tuple[bool, str]:
    """Same as print_label but uses xdg-open for Linux."""
    import subprocess
    from .barcode_core import (
        wo_label_pdf, part_label_pdf, po_label_pdf, asset_label_pdf,
    )
    result = lookup_record(raw)
    if result is None:
        return False, f"No record found for: {raw}"

    rtype = result["type"]
    rec = result["record"]

    try:
        if rtype == "wo":
            pdf = wo_label_pdf(rec)
        elif rtype == "inventory":
            pdf = part_label_pdf(rec)
        elif rtype == "po":
            pdf = po_label_pdf(rec)
        elif rtype == "asset":
            pdf = asset_label_pdf(rec)
        else:
            return False, f"No label template for: {rtype}"

        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(pdf)
        subprocess.Popen(["xdg-open", path])
        return True, f"Label opened for {result['label']}"
    except Exception as e:
        return False, str(e)


def open_label(raw: str) -> tuple[bool, str]:
    """Cross-platform label opener."""
    import platform
    if platform.system() == "Linux":
        return print_label_linux(raw)
    return print_label(raw)
