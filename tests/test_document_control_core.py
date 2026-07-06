"""Tests for document_control_core — Document Control module (P2-F).

No live database: a fake connection replays canned rows, so the revision
lettering, approval-workflow integration, and CRUD SQL are pinned down
without Postgres.
"""

import datetime

import pytest

from manufacturing.document_control_core import (
    DOC_TYPES, STATUSES, LINK_TYPES,
    ensure_document_tables, list_documents, get_document, create_document,
    attach_file, get_revisions, create_revision, submit_for_review,
    decide_document, approve_document, mark_superseded, mark_obsolete,
    get_links, add_link, remove_link, _next_revision_letter, _next_doc_number,
)


# ── fake DB infrastructure (mirrors test_sampling_plan_core.py) ────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Single canned row-set returned for every execute() call."""
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        return _Cursor(self.rows)

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


class _DispatchConn:
    """Returns canned rows based on a substring match against the SQL.
    Routes are checked in order — put more specific substrings first."""
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        for substring, rows in self.routes:
            if substring in sql:
                return _Cursor(rows)
        return _Cursor([])

    @property
    def last_sql(self):
        return self.calls[-1][0]

    @property
    def last_params(self):
        return self.calls[-1][1]


def _doc_row(**overrides):
    row = {
        'id': 10, 'doc_number': 'DOC-2026-0001', 'title': 'Widget SOP',
        'doc_type': 'SOP', 'status': 'draft', 'current_revision': 'A',
        'current_revision_id': 100, 'owner': 'qa@x.com', 'dept_key': 'quality_assurance',
        'file_path': '', 'file_name': '', 'notes': '', 'created_by': 'qa@x.com',
        'created_at': None, 'updated_at': None,
    }
    row.update(overrides)
    return row


# ── _next_revision_letter ───────────────────────────────────────────────────

def test_next_revision_letter_simple_increment():
    assert _next_revision_letter('A') == 'B'
    assert _next_revision_letter('B') == 'C'


def test_next_revision_letter_wraps_to_double_letters():
    assert _next_revision_letter('Z') == 'AA'


def test_next_revision_letter_increments_last_of_double():
    assert _next_revision_letter('AZ') == 'BA'


def test_next_revision_letter_wraps_all_letters():
    assert _next_revision_letter('ZZ') == 'AAA'


# ── _next_doc_number ─────────────────────────────────────────────────────────

def test_next_doc_number_uses_year_prefix_and_gap_safe_numbering():
    yr = datetime.date.today().year
    conn = _Conn(rows=[{'doc_number': f'DOC-{yr}-0003'}])
    assert _next_doc_number(conn) == f'DOC-{yr}-0004'


def test_next_doc_number_first_of_year():
    conn = _Conn(rows=[])
    yr = datetime.date.today().year
    assert _next_doc_number(conn) == f'DOC-{yr}-0001'


# ── ensure_document_tables ───────────────────────────────────────────────────

def test_ensure_tables_creates_all_three_tables():
    conn = _Conn(rows=[])
    ensure_document_tables(conn)
    sqls = [s for s, _ in conn.calls]
    assert any('CREATE TABLE IF NOT EXISTS document (' in s for s in sqls)
    assert any('CREATE TABLE IF NOT EXISTS document_revision' in s for s in sqls)
    assert any('CREATE TABLE IF NOT EXISTS document_link' in s for s in sqls)
    assert any('current_revision_id' in s for s in sqls)


# ── list_documents / get_document ────────────────────────────────────────────

def test_list_documents_filters_by_status_type_and_search():
    conn = _Conn(rows=[])
    list_documents(conn, status='draft', doc_type='SOP', search='widget')
    assert "status = %s" in conn.last_sql
    assert "doc_type = %s" in conn.last_sql
    assert "title ILIKE %s OR doc_number ILIKE %s" in conn.last_sql
    assert conn.last_params == ['draft', 'SOP', '%widget%', '%widget%']


def test_get_document_returns_none_when_missing():
    conn = _Conn(rows=[])
    assert get_document(conn, 1) is None


# ── create_document ──────────────────────────────────────────────────────────

def test_create_document_rejects_unknown_doc_type():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_document(conn, 'Title', 'Blueprint')


def test_create_document_rejects_empty_title():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        create_document(conn, '   ', 'SOP')


def test_create_document_inserts_doc_and_initial_revision():
    conn = _DispatchConn([
        ("FROM document WHERE doc_number LIKE", []),
        ("INSERT INTO document (", [{'id': 42}]),
        ("INSERT INTO document_revision", [{'id': 900}]),
        ("UPDATE document SET current_revision_id", []),
    ])
    doc_id = create_document(
        conn, ' Widget SOP ', 'SOP', owner='qa@x.com',
        dept_key='quality_assurance', notes='n', created_by='qa@x.com',
    )
    assert doc_id == 42
    insert_doc_calls = [c for c in conn.calls if c[0].startswith('INSERT INTO document (')]
    assert insert_doc_calls[0][1][1] == 'Widget SOP'  # title stripped
    insert_rev_calls = [c for c in conn.calls if 'INSERT INTO document_revision' in c[0]]
    assert insert_rev_calls[0][1] == [42, 'A', 'Initial draft', 'qa@x.com']
    update_calls = [c for c in conn.calls if c[0].startswith('UPDATE document SET current_revision_id')]
    assert update_calls[0][1] == [900, 42]


# ── attach_file ──────────────────────────────────────────────────────────────

def test_attach_file_raises_when_document_missing():
    conn = _DispatchConn([("FROM document WHERE id", [])])
    with pytest.raises(ValueError):
        attach_file(conn, 999, 'documents/1/f.pdf', 'f.pdf')


def test_attach_file_updates_document_and_current_revision():
    conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(current_revision_id=100)]),
        ("UPDATE document SET file_path", []),
        ("UPDATE document_revision SET file_path", []),
    ])
    attach_file(conn, 10, 'documents/10/spec.pdf', 'spec.pdf')
    doc_update = [c for c in conn.calls if c[0].startswith('UPDATE document SET file_path')]
    assert doc_update[0][1] == ['documents/10/spec.pdf', 'spec.pdf', 10]
    rev_update = [c for c in conn.calls if c[0].startswith('UPDATE document_revision SET file_path')]
    assert rev_update[0][1] == ['documents/10/spec.pdf', 'spec.pdf', 100]


def test_attach_file_skips_revision_update_when_no_current_revision():
    conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(current_revision_id=None)]),
        ("UPDATE document SET file_path", []),
    ])
    attach_file(conn, 10, 'documents/10/spec.pdf', 'spec.pdf')
    assert not any('UPDATE document_revision SET file_path' in c[0] for c in conn.calls)


# ── get_revisions / create_revision ─────────────────────────────────────────

def test_get_revisions_orders_most_recent_first():
    conn = _Conn(rows=[{'id': 2}, {'id': 1}])
    revisions = get_revisions(conn, 10)
    assert [r['id'] for r in revisions] == [2, 1]
    assert "ORDER BY id DESC" in conn.last_sql


def test_create_revision_raises_when_document_missing():
    conn = _DispatchConn([("FROM document WHERE id", [])])
    with pytest.raises(ValueError):
        create_revision(conn, 999, 'change', 'qa@x.com')


def test_create_revision_raises_when_not_approved():
    conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(status='draft')]),
    ])
    with pytest.raises(ValueError):
        create_revision(conn, 10, 'change', 'qa@x.com')


def test_create_revision_bumps_letter_and_resets_to_draft():
    conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(status='approved', current_revision='A')]),
        ("INSERT INTO document_revision", [{'id': 200}]),
        ("UPDATE document SET current_revision", []),
    ])
    new_letter = create_revision(conn, 10, 'Updated torque spec', 'eng@x.com')
    assert new_letter == 'B'
    update_calls = [c for c in conn.calls if c[0].startswith('UPDATE document SET current_revision')]
    assert update_calls[0][1][:2] == ['B', 200]


# ── submit_for_review ────────────────────────────────────────────────────────

def test_submit_for_review_raises_when_document_missing():
    conn = _DispatchConn([("FROM document WHERE id", [])])
    with pytest.raises(ValueError):
        submit_for_review(conn, 999, requested_by='qa@x.com')


def test_submit_for_review_raises_when_not_draft():
    conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(status='approved')]),
    ])
    with pytest.raises(ValueError):
        submit_for_review(conn, 10, requested_by='qa@x.com')


def test_submit_for_review_fails_open_when_no_approval_rule():
    conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(status='draft', current_revision_id=100)]),
        ("UPDATE document SET status = 'in_review'", []),
        ("SELECT id FROM approval_step", []),        # no existing steps
        ("FROM approval_rule", []),                  # no rules configured
        ("UPDATE document SET status = 'approved'", []),
    ])
    status = submit_for_review(conn, 10, requested_by='qa@x.com')
    assert status == 'approved'
    assert any(c[0].startswith("UPDATE document SET status = 'in_review'") for c in conn.calls)
    assert any(c[0].startswith("UPDATE document SET status = 'approved'") for c in conn.calls)


def test_submit_for_review_stays_in_review_when_rule_applies():
    rule_row = {
        'id': 1, 'entity_type': 'document', 'dept_key': '', 'threshold_amount': 0.0,
        'approver_role': 'QA Manager', 'seq': 10, 'escalate_after_hours': 24.0,
    }
    conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(status='draft', current_revision_id=100)]),
        ("UPDATE document SET status = 'in_review'", []),
        ("SELECT id FROM approval_step", []),
        ("FROM approval_rule", [rule_row]),
        ("INSERT INTO approval_step", [{'id': 55}]),
    ])
    status = submit_for_review(conn, 10, requested_by='qa@x.com')
    assert status == 'in_review'
    assert not any(c[0].startswith("UPDATE document SET status = 'approved'") for c in conn.calls)


# ── decide_document ──────────────────────────────────────────────────────────

def _pending_step_row(**overrides):
    row = {'id': 55, 'entity_type': 'document', 'entity_id': 100, 'seq': 10, 'status': 'pending'}
    row.update(overrides)
    return row


def test_decide_document_approves_when_all_steps_approved():
    conn = _DispatchConn([
        ("seq < %s AND status = 'pending'", [{'cnt': 0}]),         # no earlier pending steps
        ("SELECT id, entity_type, entity_id, seq, status", [_pending_step_row()]),
        ("entity_id = %s AND status = 'pending'", [{'cnt': 0}]),   # nothing else pending
        ("UPDATE document SET status = 'approved'", []),
    ])
    status = decide_document(conn, 10, 55, 'approved', 'mgr@x.com')
    assert status == 'approved'
    assert any(c[0].startswith("UPDATE document SET status = 'approved'") for c in conn.calls)


def test_decide_document_rejects_kicks_back_to_draft():
    conn = _DispatchConn([
        ("seq < %s AND status = 'pending'", [{'cnt': 0}]),
        ("SELECT id, entity_type, entity_id, seq, status", [_pending_step_row()]),
        ("UPDATE document SET status = 'draft'", []),
        ("FROM document WHERE id", [_doc_row(current_revision_id=100)]),
        ("DELETE FROM approval_step", []),
    ])
    status = decide_document(conn, 10, 55, 'rejected', 'mgr@x.com')
    assert status == 'draft'
    delete_calls = [c for c in conn.calls if c[0].startswith('DELETE FROM approval_step')]
    assert delete_calls[0][1] == [100]


def test_decide_document_rejects_clears_steps_so_resubmission_starts_fresh():
    """Regression test: without clearing rejected steps, submit_for_review's
    call into submit_for_approval (idempotent on entity_id) would silently
    hand back the stale rejected step instead of creating a new pending one,
    leaving the document stuck 'in_review' forever with nothing to decide."""
    conn = _DispatchConn([
        ("seq < %s AND status = 'pending'", [{'cnt': 0}]),
        ("SELECT id, entity_type, entity_id, seq, status", [_pending_step_row()]),
        ("UPDATE document SET status = 'draft'", []),
        ("FROM document WHERE id", [_doc_row(current_revision_id=100)]),
        ("DELETE FROM approval_step", []),
    ])
    decide_document(conn, 10, 55, 'rejected', 'mgr@x.com')

    # A later submit_for_review's existing-steps check should now see none.
    resubmit_conn = _DispatchConn([
        ("FROM document WHERE id", [_doc_row(status='draft', current_revision_id=100)]),
        ("UPDATE document SET status = 'in_review'", []),
        ("SELECT id FROM approval_step", []),  # cleared -> no stale rows found
        ("FROM approval_rule", [{
            'id': 1, 'entity_type': 'document', 'dept_key': '', 'threshold_amount': 0.0,
            'approver_role': 'QA Manager', 'seq': 10, 'escalate_after_hours': 24.0,
        }]),
        ("INSERT INTO approval_step", [{'id': 999}]),
    ])
    status = submit_for_review(resubmit_conn, 10, requested_by='author@x.com')
    assert status == 'in_review'
    assert any(c[0].startswith('INSERT INTO approval_step') for c in resubmit_conn.calls)


def test_decide_document_stays_in_review_when_more_steps_pending():
    conn = _DispatchConn([
        ("seq < %s AND status = 'pending'", [{'cnt': 0}]),
        ("SELECT id, entity_type, entity_id, seq, status", [_pending_step_row()]),
        ("entity_id = %s AND status = 'pending'", [{'cnt': 1}]),   # another step still pending
    ])
    status = decide_document(conn, 10, 55, 'approved', 'mgr@x.com')
    assert status == 'in_review'


# ── status transitions ───────────────────────────────────────────────────────

def test_approve_document_sql():
    conn = _Conn(rows=[])
    approve_document(conn, 10)
    assert "status = 'approved'" in conn.last_sql
    assert conn.last_params == [10]


def test_mark_superseded_sql():
    conn = _Conn(rows=[])
    mark_superseded(conn, 10)
    assert "status = 'superseded'" in conn.last_sql


def test_mark_obsolete_sql():
    conn = _Conn(rows=[])
    mark_obsolete(conn, 10)
    assert "status = 'obsolete'" in conn.last_sql


# ── links ────────────────────────────────────────────────────────────────────

def test_add_link_rejects_unknown_linked_type():
    conn = _Conn(rows=[{'id': 1}])
    with pytest.raises(ValueError):
        add_link(conn, 10, 'unknown_type', 5)


def test_add_link_inserts_and_returns_id():
    conn = _Conn(rows=[{'id': 9}])
    link_id = add_link(conn, 10, 'workcenter', 3, created_by='qa@x.com')
    assert link_id == 9
    assert conn.last_params == [10, 'workcenter', 3, 'qa@x.com']


def test_remove_link_deletes_by_id():
    conn = _Conn(rows=[])
    remove_link(conn, 9)
    assert "DELETE FROM document_link" in conn.last_sql
    assert conn.last_params == [9]


def test_get_links_attaches_display_label():
    conn = _DispatchConn([
        ("FROM document_link WHERE document_id", [
            {'id': 1, 'document_id': 10, 'linked_type': 'workcenter', 'linked_id': 3,
             'created_by': 'qa@x.com', 'created_at': None},
        ]),
        ("FROM workcenter WHERE id", [{'name': 'Assembly'}]),
    ])
    links = get_links(conn, 10)
    assert len(links) == 1
    assert links[0]['label'] == 'Assembly'


def test_get_links_falls_back_when_linked_row_deleted():
    conn = _DispatchConn([
        ("FROM document_link WHERE document_id", [
            {'id': 1, 'document_id': 10, 'linked_type': 'sampling_plan', 'linked_id': 77,
             'created_by': 'qa@x.com', 'created_at': None},
        ]),
        ("FROM sampling_plan WHERE id", []),
    ])
    links = get_links(conn, 10)
    assert links[0]['label'] == 'Sampling Plan #77'


# ── module constants ─────────────────────────────────────────────────────────

def test_doc_types_and_statuses_constants():
    assert DOC_TYPES == ('SOP', 'WI', 'Drawing', 'Spec')
    assert STATUSES == ('draft', 'in_review', 'approved', 'superseded', 'obsolete')
    assert 'bom' in LINK_TYPES and 'maint_equipment' in LINK_TYPES
