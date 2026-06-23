"""
maintenance_core.py — Qt-free data layer for Maintenance web views.

Tables: maint_work_order, maint_equipment, maint_schedule, maint_inspection,
        maint_downtime, maint_part, maint_mechanic
No PyQt6, no commit inside any function.
"""

import datetime

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
        "(SELECT COUNT(*) FROM maint_equipment WHERE status IN ('Needs Service','Under Repair','Down')) AS equip_issues, "
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


# ---------------------------------------------------------------------------
# Mechanic loader (for dropdowns)
# ---------------------------------------------------------------------------

def load_mechanics(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT name FROM maint_mechanic WHERE status='Active' ORDER BY name"
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


def create_work_order(conn, title: str, equipment: str, work_type: str,
                      priority: str, assigned_to: str, requested_date: str,
                      due_date: str, notes: str, created_by: str) -> int:
    if not title.strip():
        raise ValueError("Title is required.")
    row = conn.execute(
        "INSERT INTO maint_work_order "
        "(title, equipment, work_type, priority, assigned_to, "
        "requested_date, due_date, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,'Open',%s,%s) RETURNING id",
        (title.strip(), equipment.strip(), work_type,
         priority if priority in PRIORITIES else 'Medium',
         assigned_to.strip(), requested_date or _today(),
         due_date, notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_work_order(conn, wo_id: int, title: str, equipment: str,
                      work_type: str, priority: str, assigned_to: str,
                      requested_date: str, due_date: str, completed_date: str,
                      status: str, notes: str) -> None:
    if not title.strip():
        raise ValueError("Title is required.")
    conn.execute(
        "UPDATE maint_work_order SET title=%s, equipment=%s, work_type=%s, "
        "priority=%s, assigned_to=%s, requested_date=%s, due_date=%s, "
        "completed_date=%s, status=%s, notes=%s WHERE id=%s",
        (title.strip(), equipment.strip(), work_type, priority,
         assigned_to.strip(), requested_date, due_date, completed_date,
         status, notes.strip(), wo_id),
    )


def complete_work_order(conn, wo_id: int) -> None:
    conn.execute(
        "UPDATE maint_work_order SET status='Completed', completed_date=%s WHERE id=%s",
        (_today(), wo_id),
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
                    status: str, notes: str, created_by: str) -> int:
    if not name.strip():
        raise ValueError("Name is required.")
    row = conn.execute(
        "INSERT INTO maint_mechanic "
        "(name, trade, shift, phone, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (name.strip(), trade, shift,
         phone.strip(),
         status if status in MECHANIC_STATUSES else 'Active',
         notes.strip(), created_by),
    ).fetchone()
    return row['id']


def update_mechanic(conn, mech_id: int, name: str, trade: str, shift: str,
                    phone: str, status: str, notes: str) -> None:
    if not name.strip():
        raise ValueError("Name is required.")
    conn.execute(
        "UPDATE maint_mechanic SET name=%s, trade=%s, shift=%s, "
        "phone=%s, status=%s, notes=%s WHERE id=%s",
        (name.strip(), trade, shift, phone.strip(),
         status, notes.strip(), mech_id),
    )
