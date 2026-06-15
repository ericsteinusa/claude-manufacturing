"""mrp_core.py — pure MRP planning math, free of any GUI/DB dependency.

Kept separate from :mod:`mrp` (which imports PyQt6 and talks to the database)
so the planning logic can be imported and unit tested without the Qt shared
libraries. :mod:`mrp` imports :func:`compute_levels` and :func:`plan_orders`
from here.
"""

from collections import defaultdict

from .bom_core import explode_quantity


def next_sequence_number(existing, prefix):
    """Return the next ``<prefix><NNNN>`` after the ones in ``existing``.

    Uses the maximum numeric suffix + 1 (not a count), so it is robust to gaps
    left by deleted rows. Malformed entries are ignored. When the caller passes
    the numbers from its *open transaction's* connection, sequential calls
    within one uncommitted transaction keep producing distinct numbers — which
    a COUNT(*) on a separate connection cannot do.
    """
    highest = 0
    for value in existing:
        if value and value.startswith(prefix):
            try:
                highest = max(highest, int(value[len(prefix):]))
            except ValueError:
                continue
    return f"{prefix}{highest + 1:04d}"


def compute_levels(product_ids, edges):
    """Low-level codes for the BOM graph.

    ``edges`` is an iterable of ``(parent, component)`` pairs. Returns
    ``{product_id: level}`` where a top-level item (never a component) is 0 and
    each component sits at least one level below every parent that uses it.
    Processing items in ascending level guarantees a parent's dependent demand
    is known before the component is planned. The cycle guard in
    :mod:`bom_core` keeps this graph acyclic, so the relaxation terminates.
    """
    level = {pid: 0 for pid in product_ids}
    for p, c in edges:
        level.setdefault(p, 0)
        level.setdefault(c, 0)
    changed = True
    while changed:
        changed = False
        for p, c in edges:
            if level[c] < level[p] + 1:
                level[c] = level[p] + 1
                changed = True
    return level


def plan_orders(products, bom_lines, demand, on_hand,
                scheduled_receipts, safety):
    """Net requirements and explode BOMs level by level (pure).

    Parameters
    ----------
    products : dict
        ``{pid: {'item_type': str, 'lead_time_days': int}}``.
    bom_lines : dict
        ``{parent_pid: [(component_pid, qty_per, scrap_pct), ...]}``.
    demand, on_hand, scheduled_receipts, safety : dict
        ``{pid: number}`` lookups (missing keys treated as 0).

    Returns
    -------
    list of dict
        ``{'product_id', 'order_type', 'qty', 'lead_time_days'}``, ordered
        parents-first. ``order_type`` is 'make' when the item has a BOM (or is
        flagged make) else 'buy'. Lot-for-lot: the planned quantity is exactly
        the net requirement.
    """
    edges = [(p, c) for p, lines in bom_lines.items()
             for (c, _qty, _scrap) in lines]
    all_ids = set(products) | set(demand) | set(on_hand) \
        | set(scheduled_receipts) | set(safety)
    for p, c in edges:
        all_ids.add(p)
        all_ids.add(c)

    level = compute_levels(all_ids, edges)
    gross = defaultdict(float)
    for pid, qty in demand.items():
        gross[pid] += qty

    planned = []
    eps = 1e-9
    for pid in sorted(all_ids, key=lambda x: (level.get(x, 0), x)):
        required = gross.get(pid, 0.0) + safety.get(pid, 0.0)
        available = on_hand.get(pid, 0.0) + scheduled_receipts.get(pid, 0.0)
        net = required - available
        if net <= eps:
            continue
        has_bom = bool(bom_lines.get(pid))
        item_type = (products.get(pid, {}).get("item_type") or "buy")
        order_type = "make" if (has_bom or item_type == "make") else "buy"
        planned.append({
            "product_id": pid,
            "order_type": order_type,
            "qty": net,
            "lead_time_days":
                products.get(pid, {}).get("lead_time_days", 0) or 0,
        })
        if has_bom:
            for component, qty_per, scrap in bom_lines[pid]:
                gross[component] += explode_quantity(qty_per, net, scrap)
    return planned
