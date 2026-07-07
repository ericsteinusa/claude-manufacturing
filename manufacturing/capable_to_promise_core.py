"""
capable_to_promise_core.py — Qt-free Capable-to-Promise (CTP) (P4-C).

Extends ATP (`atp_core.py`, P2-B) with a routing capacity check
(`capacity_planning_core.py`, P3-A). Both already do the hard part:
`atp_core.get_atp` answers "date when qty of material will be available,"
and the new `capacity_planning_core.earliest_capacity_date` answers "date
by which a workcenter will have N hours of free capacity." This module is
a thin combination layer — for each workcenter a product's routing
touches, compute the required hours for the requested quantity, find the
earliest date each has room, and take the latest of those (all
workcenters must be free) alongside the material date; the overall CTP
date is the later of the two. Neither `atp_core` nor
`capacity_planning_core` is modified beyond the one additive
`earliest_capacity_date` function.

Products with no routing (buy items, or make items with no routing
defined) have nothing to schedule, so capacity isn't a constraint for
them — `capacity_ready_date` is just `from_date` in that case, not
"unavailable."

Every function taking `conn` takes an open connection; the caller owns
the transaction (same convention as demand_forecast_core / shop_floor_core).
"""

from __future__ import annotations

from datetime import date

from .log_utils import get_logger
from .atp_core import get_atp
from .sales_orders_core import get_so, get_so_items
from .routing_core import get_routing
from .capacity_planning_core import earliest_capacity_date

log = get_logger(__name__)


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


def get_workcenter_hours_required(conn, product_id: int, qty: float) -> dict:
    """{workcenter_id: hours} needed to build `qty` units of `product_id`,
    from its routing's per-unit std_hours. Steps with no workcenter are
    skipped -- nothing to check capacity against."""
    hours: dict = {}
    for step in get_routing(conn, product_id):
        wc_id = step.get('workcenter_id')
        if not wc_id:
            continue
        hours[wc_id] = hours.get(wc_id, 0.0) + float(step['std_hours'] or 0.0) * qty
    return hours


def get_capacity_availability(conn, product_id: int, qty: float,
                               from_date: str | None = None) -> dict:
    """Earliest date each workcenter this product's routing touches has
    enough free capacity for `qty` units, plus the overall capacity_date
    (the max across workcenters -- all must have room). capacity_date is
    `from_date` itself when the product has no routing at all (nothing to
    schedule, not "unavailable")."""
    from_date = from_date or date.today().isoformat()
    hours_required = get_workcenter_hours_required(conn, product_id, qty)

    if not hours_required:
        return {'workcenters': [], 'capacity_date': from_date}

    workcenters = []
    dates = []
    for wc_id, hours in hours_required.items():
        wc_name_row = conn.execute(
            "SELECT name FROM workcenter WHERE id = %s", (wc_id,)
        ).fetchone()
        wc_name = wc_name_row['name'] if wc_name_row else f"Workcenter {wc_id}"
        earliest = earliest_capacity_date(conn, wc_id, hours, from_date=from_date)
        workcenters.append({
            'workcenter_id': wc_id, 'workcenter_name': wc_name,
            'hours_required': round(hours, 2), 'earliest_date': earliest,
        })
        dates.append(earliest)

    capacity_date = max(dates) if all(dates) else None
    return {'workcenters': workcenters, 'capacity_date': capacity_date}


def get_ctp(conn, product_id: int, qty: float, requested_date: str | None = None) -> dict:
    """Combined material + capacity availability for one product/qty/date.

    Returns {product_id, qty, requested_date, material_ready_date,
    material_sufficient, capacity_ready_date, capacity_workcenters,
    ctp_date, ctp_sufficient}. ctp_date is the later of the material and
    capacity dates (None if either is unachievable in-horizon);
    ctp_sufficient is True when both are on/before requested_date.
    """
    req_d = requested_date or date.today().isoformat()

    atp = get_atp(conn, product_id, qty, req_d)
    capacity = get_capacity_availability(conn, product_id, qty, req_d)

    material_date = atp['earliest_available_date']
    capacity_date = capacity['capacity_date']

    ctp_date = max(material_date, capacity_date) if (material_date and capacity_date) else None
    ctp_sufficient = bool(
        ctp_date and _as_date(ctp_date) <= _as_date(req_d)
    )

    return {
        'product_id': product_id,
        'qty': qty,
        'requested_date': req_d,
        'material_ready_date': material_date,
        'material_sufficient': atp['sufficient'],
        'capacity_ready_date': capacity_date,
        'capacity_workcenters': capacity['workcenters'],
        'ctp_date': ctp_date,
        'ctp_sufficient': ctp_sufficient,
    }


def check_so_capacity(conn, so_id: int, as_of_date: str | None = None) -> list:
    """Capacity-only shortfall list for an SO's line items, mirroring
    atp_core.check_so_atp's shape/convention exactly (empty = fully
    covered) so it plugs into the same confirm-gate check. Evaluated as of
    the SO's ship_date (falling back to today if NULL). Lines with no
    product_id, or whose product has no routing, are skipped."""
    so = get_so(conn, so_id)
    if not so:
        return []
    requested_date = as_of_date or so.get('ship_date') or date.today().isoformat()
    shortfalls = []
    for it in get_so_items(conn, so_id):
        if not it.get('product_id'):
            continue
        capacity = get_capacity_availability(conn, it['product_id'], it['qty'], requested_date)
        if not capacity['workcenters']:
            continue
        if capacity['capacity_date'] is None or _as_date(capacity['capacity_date']) > _as_date(requested_date):
            shortfalls.append({
                'item_id': it['id'],
                'product_id': it['product_id'],
                'product_name': it.get('product_name') or it.get('description'),
                'requested_qty': it['qty'],
                'requested_date': requested_date,
                'capacity_workcenters': capacity['workcenters'],
                'earliest_capacity_date': capacity['capacity_date'],
            })
    return shortfalls
