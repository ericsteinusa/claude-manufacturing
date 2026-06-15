"""bom_core.py — pure BOM logic, free of any GUI/DB dependency.

Kept separate from :mod:`bom` (which imports PyQt6) so the planning math can
be imported and unit tested in environments without the Qt shared libraries
(e.g. CI runners). :mod:`bom` and :mod:`mrp_core` re-use these functions.
"""


def would_create_cycle(edges, parent_id, component_id):
    """Return True if adding parent_id -> component_id would form a cycle.

    ``edges`` is an iterable of ``(parent_id, component_id)`` pairs describing
    existing "parent is built from component" relationships. A new edge closes
    a cycle when the parent is the component itself, or when the parent is
    already reachable from the component (the component transitively requires
    the parent).
    """
    if parent_id == component_id:
        return True
    adjacency = {}
    for p, c in edges:
        adjacency.setdefault(p, []).append(c)
    stack = [component_id]
    seen = set()
    while stack:
        node = stack.pop()
        if node == parent_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, []))
    return False


def explode_quantity(qty_per, wo_quantity, scrap_pct=0.0):
    """Component quantity needed for a work order, inflated for scrap.

    ``qty_per`` of the component is needed per finished unit; multiply by the
    order quantity and add the expected scrap fraction.
    """
    return qty_per * wo_quantity * (1.0 + (scrap_pct or 0.0) / 100.0)
