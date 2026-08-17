"""
maintenance_core.py — Qt-free data layer for Maintenance web views.

Tables: maint_work_order, maint_equipment, maint_schedule, maint_inspection,
        maint_downtime, maint_part, maint_mechanic
No PyQt6, no commit inside any function.
"""

import datetime

from .notify_core import create_notifications_for_dept, ensure_notification_table

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WO_STATUSES        = ('Open', 'Assigned', 'In Progress', 'On Hold', 'Completed', 'Cancelled')
WORK_TYPES         = ('Repair', 'Inspection', 'Installation', 'Calibration',
                      'Cleaning', 'Replacement', 'Preventive', 'Other')
PRIORITIES         = ('Low', 'Medium', 'High', 'Critical')

EQUIPMENT_STATUSES = ('Operational', 'Needs Service', 'Under Repair', 'Down', 'Retired')

SCHEDULE_STATUSES  = ('Scheduled', 'Due', 'Overdue', 'Completed', 'Skipped')
FREQUENCIES        = ('Daily', 'Weekly', 'Monthly', 'Quarterly', 'Semi-Annual', 'Annual')

INSPECTION_STATUSES = ('Scheduled', 'In Progress', 'Passed', 'Failed', 'Follow-up')
INSPECTION_TYPES    = ('Fire Safety', 'Electrical', 'Machine Guarding', 'PPE',
                       'Lockout/Tagout', 'Environmental', 'General')

DOWNTIME_STATUSES   = ('Ongoing', 'Investigating', 'Resolved', 'Recurring')
DOWNTIME_CATEGORIES = ('Breakdown', 'Planned', 'Setup', 'Material Shortage',
                       'Quality', 'Changeover', 'Other')

PART_STATUSES    = ('In Stock', 'Low Stock', 'On Order', 'Out of Stock', 'Discontinued')
PART_CATEGORIES  = ('Belts', 'Bearings', 'Filters', 'Motors', 'Electrical',
                    'Hydraulics', 'Fasteners', 'Lubricants', 'Other')

MECHANIC_STATUSES = ('Active', 'On Leave', 'Inactive')
MECHANIC_TRADES   = ('Mechanical', 'Electrical', 'HVAC', 'Hydraulics', 'Welding', 'General')
MECHANIC_SHIFTS   = ('Day', 'Swing', 'Night')


def _today() -> str:
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_dashboard_counts(conn) -> dict:
    row = conn.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM maint_work_order WHERE status NOT IN ('Completed','Cancelled')) AS open_wos, "
        "(SELECT COUNT(*) FROM maint_work_order WHERE priority='Critical' "
        "  AND status NOT IN ('Completed','Cancelled')) AS critical_wos, "
        "(SELECT COUNT(*) FROM maint_equipment "
        "  WHERE status IN ('Needs Service','Under Repair','Down')) AS equip_issues, "
        "(SELECT COUNT(*) FROM maint_schedule WHERE status IN ('Due','Overdue')) AS due_schedules, "
        "(SELECT COUNT(*) FROM maint_inspection WHERE status='Scheduled') AS pending_inspections, "
        "(SELECT COUNT(*) FROM maint_downtime WHERE status IN ('Ongoing','Investigating')) AS active_downtime, "
        "(SELECT COUNT(*) FROM maint_work_order WHERE due_date != '' AND due_date < %s "
        "  AND status NOT IN ('Completed','Cancelled')) AS overdue_wos",
        (_today(),),
    ).fetchone()
    return dict(row) if row else {
        'open_wos': 0, 'critical_wos': 0, 'equip_issues': 0,
        'due_schedules': 0, 'pending_inspections': 0,
        'active_downtime': 0, 'overdue_wos': 0,
    }


def get_schedule_status_breakdown(conn) -> list[dict]:
    """Return [{status, cnt}] — PM schedule task count by status
    (Scheduled/Due/Overdue/Completed/Skipped), for a PM completion chart."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM maint_schedule "
        "GROUP BY status ORDER BY status"
    ).fetchall()
    return [dict(r) for r in rows]


def get_wo_status_breakdown(conn) -> list[dict]:
    """Return [{status, cnt}] — maint work order count by status."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM maint_work_order "
        "GROUP BY status ORDER BY cnt DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_downtime_by_category(conn, months: int = 3) -> list[dict]:
    """Return [{category, hours}] — total downtime hours by category
    for the last ``months`` months, descending."""
    rows = conn.execute(
        "SELECT COALESCE(category, 'Uncategorized') AS category, "
        "COALESCE(SUM(hours::numeric), 0)::float AS hours "
        "FROM maint_downtime "
        "WHERE down_date >= (CURRENT_DATE - INTERVAL '%s months')::text "
        "GROUP BY category ORDER BY hours DESC LIMIT 8" % months
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Mechanic loader (for dropdowns)
# ---------------------------------------------------------------------------

def load_mechanics(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name FROM maint_mechanic WHERE status='Active' ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Work Orders (maint_work_order)
# ---------------------------------------------------------------------------

def _annotate_wo(d: dict) -> dict:
    today = _today()
    d['is_overdue'] = (
        (d.get('due_date') or '') < today
        and d.get('status') not in ('Completed', 'Cancelled')
        and (d.get('due_date') or '') != ''
    )
    return d


def list_work_orders(conn, status: str | None = None,
                     priority: str | None = None,
                     search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if priority:
        conditions.append("priority = %s")
        params.append(priority)
    if search:
        conditions.append("(title ILIKE %s OR equipment ILIKE %s OR assigned_to ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM maint_work_order {where} "
        f"ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 "
        f"WHEN 'Medium' THEN 3 ELSE 4 END, "
        f"CASE WHEN due_date='' THEN '9999' ELSE due_date END",
        params,
    ).fetchall()
    return [_annotate_wo(dict(r)) for r in rows]


def get_work_order(conn, wo_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM maint_work_order WHERE id = %s", (wo_id,)
    ).fetchone()
    return _annotate_wo(dict(row)) if row else None


def _notify_maint_wo_assigned(conn, wo_id: int, title: str, assigned_to: str) -> None:
    # maint_mechanic has no people_id/login link (it's a standalone roster,
    # unlike Production WO assignees which are `people` rows) — so we can't
    # target an individual's in-app inbox. Notify the whole Maintenance dept
    # instead, same fallback pattern as inventory_core's low-stock alert.
    ensure_notification_table(conn)
    create_notifications_for_dept(
        conn, 'Maintenance', 'wo_assigned',
        f"Maintenance Work Order #{wo_id} ({title}) assigned to {assigned_to}.",
        entity_type='maint_work_order', entity_id=wo_id,
    )


def create_work_order(conn, title: str, equipment: str, work_type: str,
                      priority: str, assigned_to: str, requested_date: str,
                      due_date: str, notes: str, created_by: str,
                      estimated_hours: float | None = None) -> int:
    if not title.strip():
        raise ValueError("Title is required.")
    title = title.strip()
    assigned_to = assigned_to.strip()
    row = conn.execute(
        "INSERT INTO maint_work_order "
        "(title, equipment, work_type, priority, assigned_to, "
        "requested_date, due_date, status, notes, created_by, "
        "estimated_hours) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,'Open',%s,%s,%s) RETURNING id",
        (title, equipment.strip(), work_type,
         priority if priority in PRIORITIES else 'Medium',
         assigned_to, requested_date or _today(),
         due_date, notes.strip(), created_by, estimated_hours),
    ).fetchone()
    wo_id = row['id']
    if assigned_to:
        _notify_maint_wo_assigned(conn, wo_id, title, assigned_to)
    return wo_id


def update_work_order(conn, wo_id: int, title: str, equipment: str,
                      work_type: str, priority: str, assigned_to: str,
                      requested_date: str, due_date: str, completed_date: str,
                      status: str, notes: str,
                      estimated_hours: float | None = None) -> None:
    if not title.strip():
        raise ValueError("Title is required.")
    title = title.strip()
    assigned_to = assigned_to.strip()
    old = conn.execute(
        "SELECT assigned_to FROM maint_work_order WHERE id=%s", (wo_id,)
    ).fetchone()
    conn.execute(
        "UPDATE maint_work_order SET title=%s, equipment=%s, work_type=%s, "
        "priority=%s, assigned_to=%s, requested_date=%s, due_date=%s, "
        "completed_date=%s, status=%s, notes=%s, "
        "estimated_hours=COALESCE(%s, estimated_hours) "
        "WHERE id=%s",
        (title, equipment.strip(), work_type, priority,
         assigned_to, requested_date, due_date, completed_date,
         status, notes.strip(), estimated_hours, wo_id),
    )
    old_assignee = (old['assigned_to'] if old else '') or ''
    if assigned_to and assigned_to != old_assignee:
        _notify_maint_wo_assigned(conn, wo_id, title, assigned_to)


def complete_work_order(conn, wo_id: int,
                        actual_hours: float | None = None) -> None:
    conn.execute(
        "UPDATE maint_work_order SET status='Completed', completed_date=%s, "
        "actual_hours=COALESCE(%s, actual_hours) WHERE id=%s",
        (_today(), actual_hours, wo_id),
    )


# ---------------------------------------------------------------------------
# Equipment (maint_equipment)
# ---------------------------------------------------------------------------

def list_equipment(conn, status: str | None = None,
                   search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(name ILIKE %s OR asset_tag ILIKE %s OR location ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM maint_equipment {where} ORDER BY name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_equipment(conn, eq_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM maint_equipment WHERE id = %s", (eq_id,)
    ).fetchone()
    return dict(row) if row else None


def create_equipment(conn, name: str, asset_tag: str, location: str,
                     manufacturer: str, install_date: str, last_service: str,
                     status: str, notes: str, created_by: str) -> int:
    if not name.strip():
        raise ValueError("Name is required.")
    row = conn.execute(
        "INSERT INTO maint_equipment "
        "(name, asset_tag, location, manufacturer, install_date, "
        "last_service, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), asset_tag.strip(), location.strip(),
         manufacturer.strip(), install_date, last_service,
         status if status in EQUIPMENT_STATUSES else 'Operational',
         notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_equipment(conn, eq_id: int, name: str, asset_tag: str,
                     location: str, manufacturer: str, install_date: str,
                     last_service: str, status: str, notes: str) -> None:
    if not name.strip():
        raise ValueError("Name is required.")
    conn.execute(
        "UPDATE maint_equipment SET name=%s, asset_tag=%s, location=%s, "
        "manufacturer=%s, install_date=%s, last_service=%s, "
        "status=%s, notes=%s WHERE id=%s",
        (name.strip(), asset_tag.strip(), location.strip(),
         manufacturer.strip(), install_date, last_service,
         status, notes.strip(), eq_id),
    )


# ---------------------------------------------------------------------------
# PM Schedules (maint_schedule)
# ---------------------------------------------------------------------------

def _annotate_schedule(d: dict) -> dict:
    today = _today()
    d['is_overdue'] = (
        (d.get('next_due') or '') < today
        and (d.get('next_due') or '') != ''
        and d.get('status') not in ('Completed', 'Skipped')
    )
    return d


def list_schedules(conn, status: str | None = None,
                   search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(task ILIKE %s OR equipment ILIKE %s OR assigned_to ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM maint_schedule {where} "
        f"ORDER BY CASE WHEN next_due='' THEN '9999' ELSE next_due END",
        params,
    ).fetchall()
    return [_annotate_schedule(dict(r)) for r in rows]


def get_schedule(conn, sched_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM maint_schedule WHERE id = %s", (sched_id,)
    ).fetchone()
    return _annotate_schedule(dict(row)) if row else None


def create_schedule(conn, task: str, equipment: str, frequency: str,
                    assigned_to: str, last_done: str, next_due: str,
                    notes: str, created_by: str) -> int:
    if not task.strip():
        raise ValueError("Task is required.")
    row = conn.execute(
        "INSERT INTO maint_schedule "
        "(task, equipment, frequency, assigned_to, last_done, next_due, "
        "status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,'Scheduled',%s,%s) RETURNING id",
        (task.strip(), equipment.strip(), frequency, assigned_to.strip(),
         last_done, next_due, notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_schedule(conn, sched_id: int, task: str, equipment: str,
                    frequency: str, assigned_to: str, last_done: str,
                    next_due: str, status: str, notes: str) -> None:
    if not task.strip():
        raise ValueError("Task is required.")
    conn.execute(
        "UPDATE maint_schedule SET task=%s, equipment=%s, frequency=%s, "
        "assigned_to=%s, last_done=%s, next_due=%s, status=%s, notes=%s "
        "WHERE id=%s",
        (task.strip(), equipment.strip(), frequency, assigned_to.strip(),
         last_done, next_due, status, notes.strip(), sched_id),
    )


def complete_schedule(conn, sched_id: int) -> None:
    conn.execute(
        "UPDATE maint_schedule SET status='Completed', last_done=%s WHERE id=%s",
        (_today(), sched_id),
    )


# ---------------------------------------------------------------------------
# Inspections (maint_inspection)
# ---------------------------------------------------------------------------

def list_inspections(conn, status: str | None = None,
                     search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(area ILIKE %s OR inspector ILIKE %s OR inspection_type ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM maint_inspection {where} "
        f"ORDER BY CASE WHEN scheduled_date='' THEN '9999' ELSE scheduled_date END",
        params,
    ).fetchall()
    today = _today()
    result = []
    for r in rows:
        d = dict(r)
        d['is_overdue'] = (
            (d.get('scheduled_date') or '') < today
            and (d.get('scheduled_date') or '') != ''
            and d.get('status') not in ('Passed', 'Failed', 'Follow-up')
        )
        result.append(d)
    return result


def get_inspection(conn, insp_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM maint_inspection WHERE id = %s", (insp_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    today = _today()
    d['is_overdue'] = (
        (d.get('scheduled_date') or '') < today
        and (d.get('scheduled_date') or '') != ''
        and d.get('status') not in ('Passed', 'Failed', 'Follow-up')
    )
    return d


def create_inspection(conn, area: str, inspection_type: str, inspector: str,
                      scheduled_date: str, notes: str, created_by: str) -> int:
    if not area.strip():
        raise ValueError("Area is required.")
    row = conn.execute(
        "INSERT INTO maint_inspection "
        "(area, inspection_type, inspector, scheduled_date, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,'Scheduled',%s,%s) RETURNING id",
        (area.strip(), inspection_type, inspector.strip(),
         scheduled_date, notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_inspection(conn, insp_id: int, area: str, inspection_type: str,
                      inspector: str, scheduled_date: str, completed_date: str,
                      result: str, status: str, notes: str) -> None:
    if not area.strip():
        raise ValueError("Area is required.")
    conn.execute(
        "UPDATE maint_inspection SET area=%s, inspection_type=%s, inspector=%s, "
        "scheduled_date=%s, completed_date=%s, result=%s, status=%s, notes=%s "
        "WHERE id=%s",
        (area.strip(), inspection_type, inspector.strip(), scheduled_date,
         completed_date, result.strip(), status, notes.strip(), insp_id),
    )


def complete_inspection(conn, insp_id: int, result: str, notes: str) -> None:
    conn.execute(
        "UPDATE maint_inspection SET status=%s, completed_date=%s, "
        "result=%s, notes=%s WHERE id=%s",
        ('Passed' if result.lower() in ('pass', 'passed', '') else 'Failed',
         _today(), result.strip(), notes.strip(), insp_id),
    )


# ---------------------------------------------------------------------------
# Downtime (maint_downtime)
# ---------------------------------------------------------------------------

def list_downtime(conn, status: str | None = None,
                  search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(equipment ILIKE %s OR reason ILIKE %s OR category ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM maint_downtime {where} ORDER BY down_date DESC, id DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_downtime(conn, dt_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM maint_downtime WHERE id = %s", (dt_id,)
    ).fetchone()
    return dict(row) if row else None


def create_downtime(conn, equipment: str, reason: str, category: str,
                    down_date: str, hours: str, cost: str,
                    notes: str, created_by: str) -> int:
    if not equipment.strip():
        raise ValueError("Equipment is required.")
    row = conn.execute(
        "INSERT INTO maint_downtime "
        "(equipment, reason, category, down_date, hours, cost, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,'Ongoing',%s,%s) RETURNING id",
        (equipment.strip(), reason.strip(), category,
         down_date or _today(), hours.strip(),
         float(cost) if cost else 0.0,
         notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_downtime(conn, dt_id: int, equipment: str, reason: str,
                    category: str, down_date: str, hours: str, cost: str,
                    status: str, notes: str) -> None:
    if not equipment.strip():
        raise ValueError("Equipment is required.")
    conn.execute(
        "UPDATE maint_downtime SET equipment=%s, reason=%s, category=%s, "
        "down_date=%s, hours=%s, cost=%s, status=%s, notes=%s WHERE id=%s",
        (equipment.strip(), reason.strip(), category, down_date,
         hours.strip(), float(cost) if cost else 0.0,
         status, notes.strip(), dt_id),
    )


def resolve_downtime(conn, dt_id: int) -> None:
    conn.execute(
        "UPDATE maint_downtime SET status='Resolved' WHERE id=%s", (dt_id,)
    )


# ---------------------------------------------------------------------------
# Parts (maint_part)
# ---------------------------------------------------------------------------

def list_parts(conn, status: str | None = None,
               search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(name ILIKE %s OR part_number ILIKE %s OR category ILIKE %s)")
        params += [f'%{search}%'] * 3
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM maint_part {where} ORDER BY name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_part(conn, part_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM maint_part WHERE id = %s", (part_id,)
    ).fetchone()
    return dict(row) if row else None


def create_part(conn, name: str, part_number: str, category: str,
                location: str, quantity: str, reorder_level: str,
                unit_cost: str, status: str, notes: str,
                created_by: str) -> int:
    if not name.strip():
        raise ValueError("Name is required.")
    row = conn.execute(
        "INSERT INTO maint_part "
        "(name, part_number, category, location, quantity, reorder_level, "
        "unit_cost, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), part_number.strip(), category, location.strip(),
         quantity.strip(), reorder_level.strip(),
         float(unit_cost) if unit_cost else 0.0,
         status if status in PART_STATUSES else 'In Stock',
         notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_part(conn, part_id: int, name: str, part_number: str,
                category: str, location: str, quantity: str,
                reorder_level: str, unit_cost: str, status: str,
                notes: str) -> None:
    if not name.strip():
        raise ValueError("Name is required.")
    conn.execute(
        "UPDATE maint_part SET name=%s, part_number=%s, category=%s, "
        "location=%s, quantity=%s, reorder_level=%s, unit_cost=%s, "
        "status=%s, notes=%s WHERE id=%s",
        (name.strip(), part_number.strip(), category, location.strip(),
         quantity.strip(), reorder_level.strip(),
         float(unit_cost) if unit_cost else 0.0,
         status, notes.strip(), part_id),
    )


# ---------------------------------------------------------------------------
# Mechanics (maint_mechanic)
# ---------------------------------------------------------------------------

def list_mechanics(conn, status: str | None = None,
                   search: str | None = None) -> list[dict]:
    conditions, params = [], []
    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(name ILIKE %s OR trade ILIKE %s)")
        params += [f'%{search}%'] * 2
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM maint_mechanic {where} ORDER BY name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_mechanic(conn, mech_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM maint_mechanic WHERE id = %s", (mech_id,)
    ).fetchone()
    return dict(row) if row else None


def create_mechanic(conn, name: str, trade: str, shift: str, phone: str,
                    status: str, notes: str, created_by: str,
                    hourly_rate: float = 0.0) -> int:
    if not name.strip():
        raise ValueError("Name is required.")
    row = conn.execute(
        "INSERT INTO maint_mechanic "
        "(name, trade, shift, phone, status, notes, created_by, hourly_rate) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), trade, shift,
         phone.strip(),
         status if status in MECHANIC_STATUSES else 'Active',
         notes.strip(), created_by, max(0.0, hourly_rate)),
    ).fetchone()
    return row['id']


def update_mechanic(conn, mech_id: int, name: str, trade: str, shift: str,
                    phone: str, status: str, notes: str,
                    hourly_rate: float | None = None) -> None:
    if not name.strip():
        raise ValueError("Name is required.")
    if hourly_rate is not None:
        hourly_rate = max(0.0, hourly_rate)
    conn.execute(
        "UPDATE maint_mechanic SET name=%s, trade=%s, shift=%s, "
        "phone=%s, status=%s, notes=%s, "
        "hourly_rate=COALESCE(%s, hourly_rate) WHERE id=%s",
        (name.strip(), trade, shift, phone.strip(),
         status, notes.strip(), hourly_rate, mech_id),
    )


# ---------------------------------------------------------------------------
# Phase 6B — Asset Hierarchy
# ---------------------------------------------------------------------------

def set_equipment_parent(conn, eq_id: int,
                         parent_id: int | None) -> None:
    """Assign a parent to a piece of equipment (plant → line → machine).

    Pass parent_id=None to make the equipment a root node.
    Raises ValueError if eq_id == parent_id (self-reference).
    Does not commit.
    """
    if parent_id is not None and int(parent_id) == int(eq_id):
        raise ValueError("Equipment cannot be its own parent.")
    conn.execute(
        "UPDATE maint_equipment SET parent_id = %s WHERE id = %s",
        (parent_id, eq_id),
    )


def get_equipment_children(conn, parent_id: int) -> list[dict]:
    """Return the direct children of *parent_id*."""
    rows = conn.execute(
        "SELECT * FROM maint_equipment WHERE parent_id = %s ORDER BY name",
        (parent_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_equipment_roots(conn) -> list[dict]:
    """Return all equipment with no parent (top of hierarchy)."""
    rows = conn.execute(
        "SELECT * FROM maint_equipment WHERE parent_id IS NULL ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def _build_tree(node: dict, children_map: dict) -> dict:
    node['children'] = [
        _build_tree(c, children_map)
        for c in children_map.get(node['id'], [])
    ]
    return node


def get_equipment_tree(conn) -> list[dict]:
    """Return the full equipment hierarchy as a nested list of dicts.

    Each node has a 'children' key with its sub-nodes.
    """
    rows = conn.execute(
        "SELECT * FROM maint_equipment ORDER BY parent_id NULLS FIRST, name"
    ).fetchall()
    all_eq = [dict(r) for r in rows]

    children_map: dict[int, list] = {}
    for eq in all_eq:
        pid = eq.get('parent_id')
        if pid is not None:
            children_map.setdefault(pid, []).append(eq)

    roots = [eq for eq in all_eq if eq.get('parent_id') is None]
    return [_build_tree(r, children_map) for r in roots]


def link_part_to_equipment(conn, part_id: int,
                            equipment_id: int | None) -> None:
    """Record which equipment a spare part fits. Does not commit."""
    conn.execute(
        "UPDATE maint_part SET equipment_id = %s WHERE id = %s",
        (equipment_id, part_id),
    )


def get_parts_for_equipment(conn, equipment_id: int) -> list[dict]:
    """Return spare parts associated with a piece of equipment."""
    rows = conn.execute(
        "SELECT * FROM maint_part WHERE equipment_id = %s ORDER BY name",
        (equipment_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Phase 6B — MTBF / MTTR
# ---------------------------------------------------------------------------

def get_mtbf(conn, equipment: str, months: int = 12) -> dict:
    """Compute Mean Time Between Failures and Mean Time To Repair.

    Uses `maint_downtime` records where category='Breakdown'.

    Returns:
      failure_count         number of breakdown events
      total_downtime_hours  sum of hours across all breakdown events
      mtbf_hours            (period_hours - total_downtime_hours) / failure_count
      mttr_hours            total_downtime_hours / failure_count
      period_hours          months × 24 × 30 (approximation)
      availability_pct      100 × (period_hours - total_downtime) / period_hours
    """
    period_hours = months * 30 * 24   # approximate

    row = conn.execute("""
        SELECT COUNT(*) AS failure_count,
               COALESCE(SUM(
                 CASE WHEN hours ~ E'^[0-9]+(\\.[0-9]+)?$'
                      THEN hours::real ELSE 0 END
               ), 0) AS total_hours
        FROM maint_downtime
        WHERE equipment ILIKE %s
          AND category = 'Breakdown'
          AND down_date >= (CURRENT_DATE - (%s * INTERVAL '1 month'))::text
    """, (equipment, months)).fetchone()

    failure_count = int(row['failure_count'] if row else 0)
    total_hours = float(row['total_hours'] if row else 0)

    mtbf = ((period_hours - total_hours) / failure_count
            if failure_count else None)
    mttr = total_hours / failure_count if failure_count else None
    avail = ((period_hours - total_hours) / period_hours * 100
             if period_hours else None)

    return {
        'equipment':            equipment,
        'failure_count':        failure_count,
        'total_downtime_hours': round(total_hours, 2),
        'mtbf_hours':           round(mtbf, 2) if mtbf is not None else None,
        'mttr_hours':           round(mttr, 2) if mttr is not None else None,
        'period_hours':         period_hours,
        'availability_pct':     round(avail, 1) if avail is not None else None,
    }


def get_equipment_reliability_report(conn, months: int = 12) -> list[dict]:
    """Return MTBF/MTTR/availability for each distinct equipment with downtime."""
    rows = conn.execute("""
        SELECT equipment,
               COUNT(*) FILTER (WHERE category = 'Breakdown') AS failure_count,
               COALESCE(SUM(
                 CASE WHEN hours ~ E'^[0-9]+(\\.[0-9]+)?$' THEN hours::real ELSE 0 END
               ), 0) AS total_hours
        FROM maint_downtime
        WHERE down_date >= (CURRENT_DATE - (%s * INTERVAL '1 month'))::text
        GROUP BY equipment
        ORDER BY failure_count DESC
    """, (months,)).fetchall()

    period_hours = months * 30 * 24
    result = []
    for r in rows:
        fc = int(r['failure_count'])
        th = float(r['total_hours'])
        result.append({
            'equipment':            r['equipment'],
            'failure_count':        fc,
            'total_downtime_hours': round(th, 2),
            'mtbf_hours':           round((period_hours - th) / fc, 2) if fc else None,
            'mttr_hours':           round(th / fc, 2) if fc else None,
            'availability_pct':     round((period_hours - th) / period_hours * 100, 1),
        })
    return result


# ---------------------------------------------------------------------------
# Phase 6B — PM Alerts
# ---------------------------------------------------------------------------

def get_pm_alerts(conn, days_ahead: int = 14) -> list[dict]:
    """Return PM schedules that are overdue or due within *days_ahead* days.

    Each item includes 'urgency': 'overdue', 'due_soon', or 'due'.
    """
    today = _today()
    cutoff = (datetime.date.today()
              + datetime.timedelta(days=days_ahead)).isoformat()
    rows = conn.execute("""
        SELECT *
        FROM maint_schedule
        WHERE next_due != ''
          AND next_due <= %s
          AND status NOT IN ('Completed', 'Skipped')
        ORDER BY next_due ASC
    """, (cutoff,)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        next_due = d.get('next_due', '') or ''
        if next_due < today:
            d['urgency'] = 'overdue'
        elif next_due <= (datetime.date.today()
                          + datetime.timedelta(days=3)).isoformat():
            d['urgency'] = 'due_soon'
        else:
            d['urgency'] = 'due'
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Labor time & cost reports (WO estimated-vs-actual, by-mechanic rollup)
# ---------------------------------------------------------------------------

def get_maint_wo_time_variance_report(conn, date_from=None, date_to=None,
                                      status=None) -> list[dict]:
    """maint_work_order-level estimated-vs-actual hours & labor cost.

    One row per WO that has an estimated_hours or actual_hours value set
    (WOs never given an hour estimate/actual have nothing to compare).
    Bounded by due_date, matching list_work_orders' date-agnostic filter
    style (status/search).

    Returns dicts with keys: wo_id, title, equipment, status, due_date,
    estimated_hours, actual_hours, hours_variance, variance_pct,
    labor_cost (actual_hours * matched mechanic's hourly_rate, 0 if the
    assignee doesn't case-insensitively match a maint_mechanic.name).
    """
    from .reports_core import hours_variance

    conditions, params = [
        "(wo.estimated_hours IS NOT NULL OR wo.actual_hours IS NOT NULL)",
    ], []
    if date_from:
        conditions.append("wo.due_date >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("wo.due_date <= %s")
        params.append(date_to)
    if status:
        conditions.append("wo.status = %s")
        params.append(status)
    where = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(
        "SELECT wo.id AS wo_id, wo.title, wo.equipment, wo.status, "
        "wo.due_date, wo.estimated_hours, wo.actual_hours, "
        "COALESCE(wo.actual_hours, 0) * COALESCE(mech.hourly_rate, 0) "
        "  AS labor_cost "
        "FROM maint_work_order wo "
        "LEFT JOIN maint_mechanic mech "
        "  ON LOWER(mech.name) = LOWER(wo.assigned_to) "
        f"{where} "
        "ORDER BY wo.due_date DESC NULLS LAST, wo.id DESC",
        params,
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d['hours_variance'], d['variance_pct'] = hours_variance(
            d['estimated_hours'], d['actual_hours'])
        result.append(d)
    return result


def get_maint_labor_by_mechanic_report(conn, date_from=None,
                                       date_to=None) -> list[dict]:
    """Per-mechanic rollup across all Maintenance WOs in range.

    maint_work_order.assigned_to is matched case-insensitively to
    maint_mechanic.name — simpler and more reliable than the Production
    side's completed_by matching, since mechanics aren't logins so there's
    no email-vs-name ambiguity (see _notify_maint_wo_assigned's comment on
    why mechanics have no people_id/login link).

    Returns dicts with keys: mechanic_id, mechanic_name, wo_count,
    estimated_hours, actual_hours, hours_variance, variance_pct,
    hourly_rate, total_cost, wos (list of {wo_id, title, estimated_hours,
    actual_hours, cost}).
    """
    from .reports_core import hours_variance

    conditions, params = [
        "(wo.estimated_hours IS NOT NULL OR wo.actual_hours IS NOT NULL)",
        "wo.assigned_to != ''",
    ], []
    if date_from:
        conditions.append("wo.due_date >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("wo.due_date <= %s")
        params.append(date_to)
    where = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(
        "SELECT mech.id AS mechanic_id, mech.name AS mechanic_name, "
        "mech.hourly_rate, wo.id AS wo_id, wo.title, "
        "wo.estimated_hours, wo.actual_hours "
        "FROM maint_work_order wo "
        "JOIN maint_mechanic mech "
        "  ON LOWER(mech.name) = LOWER(wo.assigned_to) "
        f"{where} "
        "ORDER BY mech.name, wo.id",
        params,
    ).fetchall()

    mech_acc: dict[int, dict] = {}
    for r in rows:
        mid = r['mechanic_id']
        acc = mech_acc.setdefault(mid, {
            'mechanic_id': mid,
            'mechanic_name': r['mechanic_name'],
            'hourly_rate': r['hourly_rate'] or 0.0,
            'estimated_hours': 0.0, 'actual_hours': 0.0,
            'total_cost': 0.0,
            'wos': [],
        })
        est_h = r['estimated_hours'] or 0.0
        act_h = r['actual_hours'] or 0.0
        cost = act_h * acc['hourly_rate']
        acc['estimated_hours'] += est_h
        acc['actual_hours'] += act_h
        acc['total_cost'] += cost
        acc['wos'].append({
            'wo_id': r['wo_id'], 'title': r['title'],
            'estimated_hours': est_h, 'actual_hours': act_h, 'cost': cost,
        })

    result = []
    for acc in mech_acc.values():
        variance, variance_pct = hours_variance(
            acc['estimated_hours'], acc['actual_hours'])
        result.append({
            **acc,
            'wo_count': len(acc['wos']),
            'hours_variance': variance,
            'variance_pct': variance_pct,
        })
    result.sort(key=lambda d: d['mechanic_name'])
    return result
