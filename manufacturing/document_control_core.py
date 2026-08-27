"""document_control_core.py — Qt-free Document Control module (P2-F from
COMPETITIVE_GAP_ANALYSIS.md): a document master (number, title, type,
revision, status) with revision history, an optional file attachment, an
approval workflow reusing approval_workflow_core, and links to other
entities (BOM/routing/sampling plan/equipment/workcenter).

Approval workflow entity_id gotcha: approval_step.entity_id is a single
integer key shared across every review round for an entity, and
submit_for_approval() is idempotent on (entity_type, entity_id) — a second
call just returns the first round's (already-decided) step ids instead of
creating new ones. A document's row id can't be reused as entity_id across
revisions, or resubmitting revision B for review would silently return
revision A's stale steps. So each review round is submitted against that
revision's own document_revision.id (stored as document.current_revision_id)
rather than document.id — every revision gets an independent set of
approval steps.

File storage: core functions only ever handle file_path/file_name strings.
Reading the upload and writing it to MEDIA_ROOT is the view layer's job
(this is the first feature in the app to accept file uploads — see
manufacture/settings.py MEDIA_ROOT/MEDIA_URL), so the core module — and
its tests, run against a fake connection with no real filesystem — never
touch disk.

Every function takes an open connection; the caller owns the transaction
(same convention as sampling_plan_core / cycle_count_core).
"""

from __future__ import annotations

import datetime

from .mrp_core import next_sequence_number
from .approval_workflow_core import submit_for_approval, decide_step

DOC_TYPES = ('SOP', 'WI', 'Drawing', 'Spec')
STATUSES = ('draft', 'in_review', 'approved', 'superseded', 'obsolete')
LINK_TYPES = ('bom', 'routing', 'sampling_plan', 'maint_equipment', 'workcenter')


def ensure_document_tables(conn):
    """Create document / document_revision / document_link if absent.
    Idempotent — does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document (
            id                   SERIAL PRIMARY KEY,
            doc_number           TEXT NOT NULL UNIQUE,
            title                TEXT NOT NULL,
            doc_type             TEXT NOT NULL DEFAULT 'SOP',
            status               TEXT NOT NULL DEFAULT 'draft',
            current_revision     TEXT NOT NULL DEFAULT 'A',
            owner                TEXT NOT NULL DEFAULT '',
            dept_key             TEXT NOT NULL DEFAULT '',
            file_path            TEXT NOT NULL DEFAULT '',
            file_name            TEXT NOT NULL DEFAULT '',
            notes                TEXT NOT NULL DEFAULT '',
            created_by           TEXT NOT NULL DEFAULT '',
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_revision (
            id                  SERIAL PRIMARY KEY,
            document_id         INTEGER NOT NULL REFERENCES document(id),
            revision            TEXT NOT NULL,
            change_description  TEXT NOT NULL DEFAULT '',
            changed_by          TEXT NOT NULL DEFAULT '',
            file_path           TEXT NOT NULL DEFAULT '',
            file_name           TEXT NOT NULL DEFAULT '',
            changed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS document_revision_doc "
        "ON document_revision(document_id)"
    )
    # current_revision_id references document_revision, which is created
    # after document — added via ALTER rather than an inline FK to avoid a
    # forward reference in the CREATE TABLE above.
    conn.execute(
        "ALTER TABLE document ADD COLUMN IF NOT EXISTS "
        "current_revision_id INTEGER REFERENCES document_revision(id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_link (
            id            SERIAL PRIMARY KEY,
            document_id   INTEGER NOT NULL REFERENCES document(id),
            linked_type   TEXT NOT NULL,
            linked_id     INTEGER NOT NULL,
            created_by    TEXT NOT NULL DEFAULT '',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS document_link_doc "
        "ON document_link(document_id)"
    )


def _next_doc_number(conn):
    yr = datetime.date.today().year
    prefix = f"DOC-{yr}-"
    rows = conn.execute(
        "SELECT doc_number FROM document WHERE doc_number LIKE %s",
        (prefix + "%",),
    ).fetchall()
    return next_sequence_number([r['doc_number'] for r in rows], prefix)


def _next_revision_letter(current):
    """Spreadsheet-style increment: A -> B -> ... -> Z -> AA -> AB -> ..."""
    letters = list(current.upper())
    i = len(letters) - 1
    while i >= 0:
        if letters[i] != 'Z':
            letters[i] = chr(ord(letters[i]) + 1)
            return ''.join(letters)
        letters[i] = 'A'
        i -= 1
    return 'A' + ''.join(letters)


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------

def list_documents(conn, status=None, doc_type=None, search=None):
    sql = "SELECT * FROM document WHERE TRUE"
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if doc_type:
        sql += " AND doc_type = %s"
        params.append(doc_type)
    if search:
        sql += " AND (title ILIKE %s OR doc_number ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY doc_number DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_document(conn, doc_id):
    row = conn.execute(
        "SELECT * FROM document WHERE id = %s", (doc_id,),
    ).fetchone()
    return dict(row) if row else None


def create_document(conn, title, doc_type, owner='', dept_key='',
                    notes='', created_by=''):
    """Create a new document in 'draft' status with an initial revision
    'A'. Returns the new document id."""
    if doc_type not in DOC_TYPES:
        raise ValueError(f'doc_type must be one of {DOC_TYPES}')
    if not title or not title.strip():
        raise ValueError('title is required')
    doc_number = _next_doc_number(conn)
    row = conn.execute(
        "INSERT INTO document "
        "(doc_number, title, doc_type, owner, dept_key, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (doc_number, title.strip(), doc_type, owner or '', dept_key or '',
         notes or '', created_by or ''),
    ).fetchone()
    doc_id = row['id']
    rev = conn.execute(
        "INSERT INTO document_revision "
        "(document_id, revision, change_description, changed_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (doc_id, 'A', 'Initial draft', created_by or ''),
    ).fetchone()
    conn.execute(
        "UPDATE document SET current_revision_id = %s WHERE id = %s",
        (rev['id'], doc_id),
    )
    return doc_id


def attach_file(conn, doc_id, file_path, file_name):
    """Record an uploaded file against the document and its current
    revision. file_path is a path relative to MEDIA_ROOT — the view layer
    has already written the bytes to disk before calling this."""
    doc = get_document(conn, doc_id)
    if not doc:
        raise ValueError(f'No document with id {doc_id}')
    conn.execute(
        "UPDATE document SET file_path = %s, file_name = %s, "
        "updated_at = NOW() WHERE id = %s",
        (file_path, file_name, doc_id),
    )
    if doc['current_revision_id']:
        conn.execute(
            "UPDATE document_revision SET file_path = %s, file_name = %s "
            "WHERE id = %s",
            (file_path, file_name, doc['current_revision_id']),
        )


# ---------------------------------------------------------------------------
# Revision history
# ---------------------------------------------------------------------------

def get_revisions(conn, doc_id):
    rows = conn.execute(
        "SELECT * FROM document_revision WHERE document_id = %s "
        "ORDER BY id DESC",
        (doc_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_revision(conn, doc_id, change_description, changed_by,
                    file_path='', file_name=''):
    """Bump to a new revision letter and reset to 'draft' so it can go
    through review again. Only allowed once the current revision has been
    approved — you revise a released document, not one still in flight.
    Returns the new revision letter."""
    doc = get_document(conn, doc_id)
    if not doc:
        raise ValueError(f'No document with id {doc_id}')
    if doc['status'] != 'approved':
        raise ValueError(
            "Can only create a new revision from an 'approved' document "
            f"(current status: {doc['status']!r})")
    new_letter = _next_revision_letter(doc['current_revision'])
    rev = conn.execute(
        "INSERT INTO document_revision "
        "(document_id, revision, change_description, changed_by, "
        " file_path, file_name) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (doc_id, new_letter, change_description or '', changed_by or '',
         file_path or '', file_name or ''),
    ).fetchone()
    conn.execute(
        "UPDATE document SET current_revision = %s, current_revision_id = %s, "
        "status = 'draft', file_path = COALESCE(NULLIF(%s, ''), file_path), "
        "file_name = COALESCE(NULLIF(%s, ''), file_name), updated_at = NOW() "
        "WHERE id = %s",
        (new_letter, rev['id'], file_path or '', file_name or '', doc_id),
    )
    return new_letter


# ---------------------------------------------------------------------------
# Approval workflow (draft -> in_review -> approved, or back to draft on
# rejection)
# ---------------------------------------------------------------------------

def submit_for_review(conn, doc_id, requested_by=''):
    """Submit the document's current revision for approval. If no
    approval_rule is configured for entity_type='document', fails open —
    the revision is approved immediately (matching cycle_count_core's
    convention) rather than blocking on a workflow nobody set up. Returns
    the resulting status ('in_review' or 'approved')."""
    doc = get_document(conn, doc_id)
    if not doc:
        raise ValueError(f'No document with id {doc_id}')
    if doc['status'] != 'draft':
        raise ValueError(
            f"Can only submit a 'draft' document for review "
            f"(current status: {doc['status']!r})")
    conn.execute(
        "UPDATE document SET status = 'in_review', updated_at = NOW() "
        "WHERE id = %s",
        (doc_id,),
    )
    step_ids = submit_for_approval(
        conn, 'document', doc['current_revision_id'], 0.0,
        dept_key=doc['dept_key'], requested_by=requested_by,
    )
    if not step_ids:
        approve_document(conn, doc_id)
        return 'approved'
    return 'in_review'


def decide_document(conn, doc_id, step_id, decision, decided_by, notes='',
                    signature_meaning=''):
    """Record an approve/reject decision on a pending review step.
    Returns the resulting document status."""
    overall = decide_step(conn, step_id, decision, decided_by, notes,
                          signature_meaning=signature_meaning)
    if overall == 'approved':
        approve_document(conn, doc_id)
        return 'approved'
    if overall == 'rejected':
        conn.execute(
            "UPDATE document SET status = 'draft', updated_at = NOW() "
            "WHERE id = %s",
            (doc_id,),
        )
        # submit_for_approval() is idempotent on (entity_type, entity_id) —
        # it returns whatever steps already exist rather than creating new
        # ones. Without clearing this round's rejected step, resubmitting
        # this same revision for review would silently hand back the old
        # rejected step (with no pending step for anyone to act on) instead
        # of starting a fresh round, leaving the document stuck in
        # 'in_review' forever.
        doc = get_document(conn, doc_id)
        if doc and doc['current_revision_id']:
            conn.execute(
                "DELETE FROM approval_step "
                "WHERE entity_type = 'document' AND entity_id = %s",
                (doc['current_revision_id'],),
            )
        return 'draft'
    return 'in_review'


def approve_document(conn, doc_id):
    conn.execute(
        "UPDATE document SET status = 'approved', updated_at = NOW() "
        "WHERE id = %s",
        (doc_id,),
    )


def mark_superseded(conn, doc_id):
    conn.execute(
        "UPDATE document SET status = 'superseded', updated_at = NOW() "
        "WHERE id = %s",
        (doc_id,),
    )


def mark_obsolete(conn, doc_id):
    conn.execute(
        "UPDATE document SET status = 'obsolete', updated_at = NOW() "
        "WHERE id = %s",
        (doc_id,),
    )


# ---------------------------------------------------------------------------
# Links to other entities
# ---------------------------------------------------------------------------

def _link_label(conn, linked_type, linked_id):
    """Best-effort display label for a linked entity. Falls back to a bare
    '<type> #<id>' if the row no longer exists (e.g. deleted since linking)
    rather than failing the whole document page over one stale link."""
    if linked_type == 'bom':
        row = conn.execute(
            "SELECT name FROM product WHERE id = %s", (linked_id,),
        ).fetchone()
        return f"BOM — {row['name']}" if row else f"BOM — product #{linked_id}"
    if linked_type == 'routing':
        row = conn.execute(
            "SELECT r.operation_seq, r.operation_name, p.name AS product_name "
            "FROM routing r LEFT JOIN product p ON p.id = r.product_id "
            "WHERE r.id = %s",
            (linked_id,),
        ).fetchone()
        if row:
            return (f"Routing — {row['product_name']} "
                    f"#{row['operation_seq']} {row['operation_name']}")
        return f"Routing #{linked_id}"
    if linked_type == 'sampling_plan':
        row = conn.execute(
            "SELECT plan_name FROM sampling_plan WHERE id = %s", (linked_id,),
        ).fetchone()
        return row['plan_name'] if row else f"Sampling Plan #{linked_id}"
    if linked_type == 'maint_equipment':
        row = conn.execute(
            "SELECT name FROM maint_equipment WHERE id = %s", (linked_id,),
        ).fetchone()
        return row['name'] if row else f"Equipment #{linked_id}"
    if linked_type == 'workcenter':
        row = conn.execute(
            "SELECT name FROM workcenter WHERE id = %s", (linked_id,),
        ).fetchone()
        return row['name'] if row else f"Workcenter #{linked_id}"
    return f"{linked_type} #{linked_id}"


def get_links(conn, doc_id):
    rows = conn.execute(
        "SELECT * FROM document_link WHERE document_id = %s ORDER BY id",
        (doc_id,),
    ).fetchall()
    links = [dict(r) for r in rows]
    for link in links:
        link['label'] = _link_label(conn, link['linked_type'], link['linked_id'])
    return links


def add_link(conn, doc_id, linked_type, linked_id, created_by=''):
    if linked_type not in LINK_TYPES:
        raise ValueError(f'linked_type must be one of {LINK_TYPES}')
    row = conn.execute(
        "INSERT INTO document_link (document_id, linked_type, linked_id, created_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (doc_id, linked_type, int(linked_id), created_by or ''),
    ).fetchone()
    return row['id']


def remove_link(conn, link_id):
    conn.execute("DELETE FROM document_link WHERE id = %s", (link_id,))
