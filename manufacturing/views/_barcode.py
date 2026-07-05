"""Barcode scan routing, label printing, and receiving scan session views."""
from django.shortcuts import render, redirect
from django.http import HttpResponse

from ..db_pg import get_db_connection
from ..barcode_core import (
    resolve_scan_url,
    wo_label_pdf, part_label_pdf, po_label_pdf,
    receiving_label_pdf, asset_label_pdf,
)
from ..work_orders_core import get_wo
from ..purchase_orders_core import get_po, get_po_items, receive_po_item
from ..inventory_core import get_product
from ..it_core import get_asset


# ── Universal scan endpoint ───────────────────────────────────────────────────

def scan_lookup(request):
    """
    GET /scan/?q=<barcode>  — redirect to the matching record page.
    POST /scan/             — same, JSON-friendly for JS scanners.
    """
    raw = (request.GET.get("q") or request.POST.get("q") or "").strip()
    if not raw:
        return render(request, "scan_home.html", _ctx(request))

    url = resolve_scan_url(raw)
    if url:
        return redirect(url)

    # Not found — re-render scan home with error
    return render(request, "scan_home.html", {
        **_ctx(request),
        "error": f"No record found for: {raw}",
        "last_scan": raw,
    })


def scan_home(request):
    return render(request, "scan_home.html", _ctx(request))


def _ctx(request):
    return {
        "email": request.session.get("email", ""),
        "user_role": request.session.get("role", ""),
    }


# ── Label PDF endpoints ───────────────────────────────────────────────────────

def label_wo(request, wo_id):
    conn = get_db_connection()
    wo = get_wo(conn, wo_id)
    if not wo:
        return HttpResponse("Not found", status=404)
    pdf = wo_label_pdf(wo)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="WO-{wo["wo_number"]}.pdf"'
    return resp


def label_part(request, product_id):
    conn = get_db_connection()
    product = get_product(conn, product_id)
    if not product:
        return HttpResponse("Not found", status=404)
    pdf = part_label_pdf(product)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="PART-{product_id}.pdf"'
    return resp


def label_po(request, po_id):
    conn = get_db_connection()
    po = get_po(conn, po_id)
    if not po:
        return HttpResponse("Not found", status=404)
    pdf = po_label_pdf(po)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="PO-{po["po_number"]}.pdf"'
    return resp


def label_receiving(request, po_id):
    conn = get_db_connection()
    po = get_po(conn, po_id)
    if not po:
        return HttpResponse("Not found", status=404)
    pdf = receiving_label_pdf(po)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="RCV-{po["po_number"]}.pdf"'
    return resp


def label_asset(request, asset_id):
    conn = get_db_connection()
    asset = get_asset(conn, asset_id)
    if not asset:
        return HttpResponse("Not found", status=404)
    pdf = asset_label_pdf(asset)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="ASSET-{asset["asset_tag"]}.pdf"'
    return resp


# ── Receiving scan session ────────────────────────────────────────────────────

def receive_scan(request):
    """
    Multi-scan receiving session.
    Step 1: Scan a PO barcode (RCV- or PO-) to open the session.
    Step 2: Scan each part (PART-) to mark it received.
    """
    conn = get_db_connection()
    ctx = _ctx(request)
    po_id = request.session.get("receive_po_id")
    po = get_po(conn, po_id) if po_id else None
    items = get_po_items(conn, po_id) if po_id else []

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "scan":
            raw = request.POST.get("q", "").strip()
            # Scan a PO to start the session
            if raw.upper().startswith("PO-") or raw.upper().startswith("RCV-"):
                prefix = "PO-" if raw.upper().startswith("PO-") else "RCV-"
                po_number = raw[len(prefix):].upper()
                row = conn.execute(
                    "SELECT id FROM purchase_order WHERE po_number = %s",
                    [po_number]
                ).fetchone()
                if row:
                    request.session["receive_po_id"] = row["id"]
                    ctx["success"] = f"PO {po_number} loaded — scan parts to receive."
                else:
                    ctx["error"] = f"PO not found: {po_number}"
            # Scan a part to receive it
            elif raw.upper().startswith("PART-") and po_id:
                sku = raw[5:].upper()
                matched = [i for i in items
                           if str(i.get("sku") or "").upper() == sku
                           or str(i.get("description") or "").upper() == sku]
                if matched:
                    item = matched[0]
                    qty_left = (item.get("qty_ordered") or 0) - (item.get("qty_received") or 0)
                    if qty_left > 0:
                        receive_po_item(conn, item["id"], qty_left, po_id=po_id)
                        items = get_po_items(conn, po_id)
                        ctx["success"] = f"Received {qty_left} × {item.get('description') or sku}"
                    else:
                        ctx["info"] = f"{sku} already fully received."
                else:
                    ctx["error"] = f"Part {sku} not on this PO."
            elif raw:
                ctx["error"] = f"Unrecognised scan: {raw}. Scan a PO- or PART- barcode."

        elif action == "clear":
            request.session.pop("receive_po_id", None)
            return redirect("/scan/receive/")

        # Refresh po/items after POST
        po_id = request.session.get("receive_po_id")
        po = get_po(conn, po_id) if po_id else None
        items = get_po_items(conn, po_id) if po_id else []

    ctx.update({"po": po, "items": items})
    return render(request, "scan_receive.html", ctx)
