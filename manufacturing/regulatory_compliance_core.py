"""regulatory_compliance_core.py — Qt-free Regulatory Compliance Templates
(FDA, ISO), 7/10 of the top-10 ERPs have it. Closes Quality Management's
last remaining domain gap.

A compliance **template** is a reusable requirement checklist for a named
standard (e.g. "ISO 9001:2015", "FDA 21 CFR Part 820") — a header plus a
flat list of clause/requirement rows. A **checklist** is one instantiation
of a template against a real scope (an internal audit, a site, a product
line): creating one snapshots every template item into its own
checklist-item row, so editing the template afterward never rewrites
history for a checklist already in progress — the same
"snapshot-at-creation-time" choice already used for CoA generation against
SPC measurements.

**The seeded starter templates are illustrative, not exhaustive or
certified.** The clause list here is a small, representative subset picked
to demonstrate the structure — real ISO/FDA compliance requires the actual
standard text and a qualified auditor, the same "structure is real, the
org's own numbers/content still need expert judgment" scoping already used
for FMEA's S/O/D rating anchors and sampling_plan_core's AQL disclaimer.

Tables:
  compliance_template       — header: name, standard, description
  compliance_template_item  — one row per requirement clause
  compliance_checklist      — one instantiation of a template against a
                              real scope, with a rollup status
  compliance_checklist_item — one row per template item, snapshotted at
                              instantiation; tracks its own status/evidence

Every function takes an open connection; the caller owns the transaction
(same convention as sampling_plan_core / fmea_core).
"""

from __future__ import annotations

import datetime

ITEM_STATUSES = ('not_started', 'in_progress', 'complete', 'not_applicable')
CHECKLIST_STATUSES = ('open', 'complete')


def _today() -> str:
    return datetime.date.today().isoformat()


def ensure_compliance_tables(conn):
    """Create the four compliance tables if absent. Idempotent — does not
    commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compliance_template (
            id           SERIAL PRIMARY KEY,
            name         TEXT NOT NULL,
            standard     TEXT NOT NULL DEFAULT '',
            description  TEXT NOT NULL DEFAULT '',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compliance_template_item (
            id                SERIAL PRIMARY KEY,
            template_id       INTEGER NOT NULL REFERENCES compliance_template(id),
            clause_ref        TEXT NOT NULL DEFAULT '',
            requirement_text  TEXT NOT NULL,
            category          TEXT NOT NULL DEFAULT '',
            sort_order        INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS compliance_template_item_template "
        "ON compliance_template_item(template_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compliance_checklist (
            id           SERIAL PRIMARY KEY,
            template_id  INTEGER NOT NULL REFERENCES compliance_template(id),
            name         TEXT NOT NULL,
            owner        TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'open',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compliance_checklist_item (
            id                SERIAL PRIMARY KEY,
            checklist_id      INTEGER NOT NULL REFERENCES compliance_checklist(id),
            template_item_id  INTEGER REFERENCES compliance_template_item(id),
            clause_ref        TEXT NOT NULL DEFAULT '',
            requirement_text  TEXT NOT NULL,
            category          TEXT NOT NULL DEFAULT '',
            sort_order        INTEGER NOT NULL DEFAULT 0,
            status            TEXT NOT NULL DEFAULT 'not_started',
            evidence_notes    TEXT NOT NULL DEFAULT '',
            completed_by      TEXT NOT NULL DEFAULT '',
            completed_at      TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS compliance_checklist_item_checklist "
        "ON compliance_checklist_item(checklist_id)"
    )


_SEED_TEMPLATES = [
    {
        'name': 'ISO 9001:2015 Quality Management System (starter)',
        'standard': 'ISO 9001:2015',
        'items': [
            ('4.4', 'Processes needed for the QMS are identified and their sequence/interaction determined', 'Context'),
            ('5.1', 'Top management demonstrates leadership and commitment to the QMS', 'Leadership'),
            ('6.1', 'Risks and opportunities affecting QMS conformity are identified and addressed', 'Planning'),
            ('7.1.5', 'Monitoring and measuring resources are calibrated/verified at specified intervals', 'Support'),
            ('8.5.1', 'Production is carried out under controlled conditions', 'Operation'),
            ('9.2', 'Internal audits are conducted at planned intervals', 'Performance Evaluation'),
            ('10.2', 'Nonconformities are corrected and root-caused, with corrective action taken', 'Improvement'),
        ],
    },
    {
        'name': 'FDA 21 CFR Part 820 Quality System Regulation (starter)',
        'standard': 'FDA 21 CFR Part 820',
        'items': [
            ('820.30', 'Design controls are established for device design and development', 'Design Controls'),
            ('820.50', 'Purchasing controls verify that suppliers meet specified requirements', 'Purchasing'),
            ('820.70', 'Production and process controls document and control the manufacturing process', 'Production'),
            ('820.80', 'Receiving, in-process, and finished device acceptance activities are documented', 'Inspection'),
            ('820.100', 'A corrective and preventive action (CAPA) procedure is documented and followed', 'CAPA'),
            ('820.184', 'Device history records (DHR) are maintained for each unit/lot/batch', 'Records'),
        ],
    },
]


def seed_default_templates(conn, created_by=''):
    """Insert the starter ISO/FDA templates if no template of that name
    exists yet. Idempotent — safe to call on every request. Returns the
    number of templates actually created (0 if they already existed)."""
    created = 0
    for tpl in _SEED_TEMPLATES:
        existing = conn.execute(
            "SELECT id FROM compliance_template WHERE name = %s", (tpl['name'],)
        ).fetchone()
        if existing:
            continue
        template_id = create_template(
            conn, tpl['name'], tpl['standard'],
            description=(
                'Illustrative starter checklist — a small representative '
                'subset of clauses, not the full standard. Consult the '
                'actual standard text and a qualified auditor for real '
                'certification work.'
            ),
            created_by=created_by,
        )
        for i, (clause_ref, text, category) in enumerate(tpl['items']):
            add_template_item(conn, template_id, clause_ref, text,
                              category=category, sort_order=i)
        created += 1
    return created


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def list_templates(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM compliance_template ORDER BY name"
    ).fetchall()]


def get_template(conn, template_id):
    row = conn.execute(
        "SELECT * FROM compliance_template WHERE id = %s", (template_id,)
    ).fetchone()
    if not row:
        return None
    tpl = dict(row)
    tpl['items'] = list_template_items(conn, template_id)
    return tpl


def list_template_items(conn, template_id):
    rows = conn.execute(
        "SELECT * FROM compliance_template_item WHERE template_id = %s "
        "ORDER BY sort_order, id",
        (template_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_template(conn, name, standard, description='', created_by=''):
    if not name or not name.strip():
        raise ValueError('name is required')
    row = conn.execute(
        "INSERT INTO compliance_template (name, standard, description, created_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (name.strip(), standard or '', description or '', created_by or ''),
    ).fetchone()
    return row['id']


def add_template_item(conn, template_id, clause_ref, requirement_text,
                      category='', sort_order=0):
    if not requirement_text or not requirement_text.strip():
        raise ValueError('requirement_text is required')
    row = conn.execute(
        "INSERT INTO compliance_template_item "
        "(template_id, clause_ref, requirement_text, category, sort_order) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (template_id, clause_ref or '', requirement_text.strip(),
         category or '', int(sort_order or 0)),
    ).fetchone()
    return row['id']


# ---------------------------------------------------------------------------
# Checklists (instantiated from a template)
# ---------------------------------------------------------------------------

def list_checklists(conn, status=None):
    sql = (
        "SELECT c.*, t.name AS template_name, t.standard "
        "FROM compliance_checklist c "
        "JOIN compliance_template t ON t.id = c.template_id "
        "WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND c.status = %s"
        params.append(status)
    sql += " ORDER BY c.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_checklist(conn, template_id, name, owner='', created_by=''):
    """Instantiate a checklist from a template: snapshots every template
    item into its own checklist_item row so later template edits don't
    retroactively change a checklist already in progress. Raises if the
    template has no items yet."""
    if not name or not name.strip():
        raise ValueError('name is required')
    items = list_template_items(conn, template_id)
    if not items:
        raise ValueError('Template has no requirement items to instantiate')
    row = conn.execute(
        "INSERT INTO compliance_checklist (template_id, name, owner, created_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (template_id, name.strip(), owner or '', created_by or ''),
    ).fetchone()
    checklist_id = row['id']
    for item in items:
        conn.execute(
            "INSERT INTO compliance_checklist_item "
            "(checklist_id, template_item_id, clause_ref, requirement_text, "
            " category, sort_order) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (checklist_id, item['id'], item['clause_ref'],
             item['requirement_text'], item['category'], item['sort_order']),
        )
    return checklist_id


def get_checklist(conn, checklist_id):
    row = conn.execute(
        "SELECT c.*, t.name AS template_name, t.standard "
        "FROM compliance_checklist c "
        "JOIN compliance_template t ON t.id = c.template_id "
        "WHERE c.id = %s",
        (checklist_id,),
    ).fetchone()
    if not row:
        return None
    checklist = dict(row)
    checklist['items'] = list_checklist_items(conn, checklist_id)
    checklist['progress'] = get_checklist_progress(conn, checklist_id)
    return checklist


def list_checklist_items(conn, checklist_id):
    rows = conn.execute(
        "SELECT * FROM compliance_checklist_item WHERE checklist_id = %s "
        "ORDER BY sort_order, id",
        (checklist_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_checklist_item(conn, item_id, status, evidence_notes='',
                          completed_by=''):
    """Update one checklist item's status/evidence, then roll the parent
    checklist's own status up (complete once every item is 'complete' or
    'not_applicable'). Does not commit."""
    if status not in ITEM_STATUSES:
        raise ValueError(f'status must be one of {ITEM_STATUSES}')
    row = conn.execute(
        "SELECT checklist_id FROM compliance_checklist_item WHERE id = %s",
        (item_id,),
    ).fetchone()
    if not row:
        raise ValueError(f'No checklist item with id {item_id}')
    completed_at = _today() if status in ('complete', 'not_applicable') else None
    conn.execute(
        "UPDATE compliance_checklist_item SET status = %s, evidence_notes = %s, "
        "completed_by = %s, completed_at = %s WHERE id = %s",
        (status, evidence_notes or '', completed_by or '', completed_at, item_id),
    )
    _recompute_checklist_status(conn, row['checklist_id'])


def _recompute_checklist_status(conn, checklist_id):
    progress = get_checklist_progress(conn, checklist_id)
    new_status = 'complete' if progress['percent'] >= 100 else 'open'
    conn.execute(
        "UPDATE compliance_checklist SET status = %s WHERE id = %s",
        (new_status, checklist_id),
    )


def get_checklist_progress(conn, checklist_id):
    """{'total', 'complete', 'not_applicable', 'in_progress', 'not_started',
    'percent'} — percent counts both 'complete' and 'not_applicable' as
    done, since a not-applicable item isn't outstanding work."""
    items = list_checklist_items(conn, checklist_id)
    total = len(items)
    counts = {s: 0 for s in ITEM_STATUSES}
    for item in items:
        counts[item['status']] = counts.get(item['status'], 0) + 1
    done = counts['complete'] + counts['not_applicable']
    percent = round(100.0 * done / total, 1) if total else 0.0
    return {
        'total': total,
        'complete': counts['complete'],
        'not_applicable': counts['not_applicable'],
        'in_progress': counts['in_progress'],
        'not_started': counts['not_started'],
        'percent': percent,
    }
