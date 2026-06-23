"""
Tests for manufacturing/engineering_core.py — pure unit tests, no Qt, no DB.
"""

import pytest
from unittest.mock import MagicMock

from manufacturing.engineering_core import (
    PROJECT_STATUSES, TASK_STATUSES, ECR_STATUSES, PRIORITIES,
    load_products, load_people,
    next_project_number, next_ecr_number,
    get_eng_dashboard,
    list_projects, get_project, create_project, update_project,
    list_project_tasks, list_tasks, create_task, update_task, get_task,
    list_ecrs, get_ecr, create_ecr, update_ecr, set_ecr_status,
    eng_reports,
)


def _conn(fetchone=None, fetchall=None):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = fetchone
    c.execute.return_value.fetchall.return_value = fetchall or []
    return c


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_project_statuses_has_planning():
    assert 'planning' in PROJECT_STATUSES

def test_project_statuses_has_completed():
    assert 'completed' in PROJECT_STATUSES

def test_task_statuses_has_open():
    assert 'open' in TASK_STATUSES

def test_ecr_statuses_has_draft():
    assert 'draft' in ECR_STATUSES

def test_ecr_statuses_has_approved():
    assert 'approved' in ECR_STATUSES

def test_priorities_has_critical():
    assert 'critical' in PRIORITIES

def test_priorities_has_four():
    assert len(PRIORITIES) == 4


# ---------------------------------------------------------------------------
# Reference helpers
# ---------------------------------------------------------------------------

def test_load_products_returns_labels():
    conn = _conn(fetchall=[{'id': 1, 'name': 'Widget'}])
    assert load_products(conn)[0]['label'] == 'Widget'

def test_load_products_empty():
    assert load_products(_conn(fetchall=[])) == []

def test_load_people_builds_label():
    conn = _conn(fetchall=[{'id': 1, 'first_name': 'Jane',
                            'last_name': 'Smith', 'email': 'j@co.com'}])
    result = load_people(conn)
    assert result[0]['label'] == 'Jane Smith'
    assert result[0]['email'] == 'j@co.com'

def test_load_people_empty():
    assert load_people(_conn(fetchall=[])) == []


# ---------------------------------------------------------------------------
# Sequence numbers
# ---------------------------------------------------------------------------

def test_next_project_number_starts_at_one():
    import datetime
    yr = datetime.date.today().year
    conn = _conn(fetchall=[])
    result = next_project_number(conn)
    assert result == f'PROJ-{yr}-0001'

def test_next_project_number_increments():
    import datetime
    yr = datetime.date.today().year
    conn = _conn(fetchall=[{'project_number': f'PROJ-{yr}-0003'}])
    assert next_project_number(conn) == f'PROJ-{yr}-0004'

def test_next_project_number_skips_malformed():
    import datetime
    yr = datetime.date.today().year
    conn = _conn(fetchall=[{'project_number': f'PROJ-{yr}-BAD'},
                            {'project_number': f'PROJ-{yr}-0005'}])
    assert next_project_number(conn) == f'PROJ-{yr}-0006'

def test_next_ecr_number_starts_at_one():
    import datetime
    yr = datetime.date.today().year
    conn = _conn(fetchall=[])
    assert next_ecr_number(conn) == f'ECR-{yr}-0001'

def test_next_ecr_number_increments():
    import datetime
    yr = datetime.date.today().year
    conn = _conn(fetchall=[{'ecr_number': f'ECR-{yr}-0002'},
                            {'ecr_number': f'ECR-{yr}-0007'}])
    assert next_ecr_number(conn) == f'ECR-{yr}-0008'


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def _dash_row(**kw):
    return {'planning': 2, 'in_progress': 3, 'on_hold': 1,
            'completed': 5, 'total': 11,
            'draft': 1, 'pending': 2, 'approved': 3,
            'open_tasks': 4, 'active_tasks': 2, 'overdue_tasks': 1,
            **kw}


def test_get_eng_dashboard_returns_sections():
    conn = _conn(fetchone=_dash_row())
    result = get_eng_dashboard(conn)
    assert 'projects' in result
    assert 'ecrs' in result
    assert 'tasks' in result

def test_get_eng_dashboard_projects_in_progress():
    conn = _conn(fetchone=_dash_row(in_progress=7))
    result = get_eng_dashboard(conn)
    assert result['projects'].get('in_progress') == 7

def test_get_eng_dashboard_tasks_overdue():
    conn = _conn(fetchone=_dash_row(overdue_tasks=3))
    result = get_eng_dashboard(conn)
    assert result['tasks'].get('overdue_tasks') == 3


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def _proj(**kw):
    base = {'id': 1, 'project_number': 'PROJ-2024-0001', 'title': 'Widget Redesign',
            'product_id': None, 'engineer': 'eng@co.com',
            'start_date': '2024-01-01', 'due_date': '2024-06-30',
            'status': 'planning', 'notes': '', 'created_by': 'u@co.com',
            'task_count': 0, 'done_count': 0, 'overdue_tasks': 0}
    base.update(kw)
    return base


def test_list_projects_returns_rows():
    conn = _conn(fetchall=[_proj()])
    result = list_projects(conn)
    assert result[0]['project_number'] == 'PROJ-2024-0001'

def test_list_projects_no_filter_passes_no_status_param():
    conn = _conn(fetchall=[])
    list_projects(conn)
    call_args = conn.execute.call_args
    # only the _today() param should be passed when no filters applied
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('params')
    # no status/engineer/search strings in the params list
    assert not any(p in ('planning', 'in_progress', 'on_hold') for p in (params or []))

def test_list_projects_status_filter():
    conn = _conn(fetchall=[])
    list_projects(conn, status='planning')
    sql = conn.execute.call_args[0][0]
    assert 'status' in sql

def test_list_projects_engineer_filter():
    conn = _conn(fetchall=[])
    list_projects(conn, engineer='eng@co.com')
    params = conn.execute.call_args[0][1]
    assert 'eng@co.com' in params

def test_list_projects_search_filter():
    conn = _conn(fetchall=[])
    list_projects(conn, search='widget')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql

def test_get_project_returns_row():
    conn = _conn(fetchone=_proj())
    r = get_project(conn, 1)
    assert r['title'] == 'Widget Redesign'

def test_get_project_returns_none():
    assert get_project(_conn(fetchone=None), 99) is None

def test_create_project_returns_id():
    conn = _conn(fetchone={'id': 5})
    pid = create_project(conn, '', 'New Project', None, 'eng@co.com',
                         '', None, 'planning', '', 'u@co.com')
    assert pid == 5

def test_create_project_rejects_empty_title():
    with pytest.raises(ValueError):
        create_project(_conn(), '', '', None, '', '', None, 'planning', '', '')

def test_create_project_defaults_bad_status():
    conn = _conn(fetchone={'id': 1})
    create_project(conn, '', 'Test', None, '', '', None, 'bad_status', '', '')
    params = conn.execute.call_args[0][1]
    assert 'planning' in params

def test_create_project_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_project(conn, 'P-001', 'Test', None, '', '', None, 'planning', '', '')
    conn.commit.assert_not_called()

def test_update_project_executes_update():
    conn = _conn()
    update_project(conn, 1, 'Updated', None, '', '', None, 'in_progress', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE eng_project' in sql

def test_update_project_rejects_empty_title():
    with pytest.raises(ValueError):
        update_project(_conn(), 1, '', None, '', '', None, 'planning', '')

def test_update_project_corrects_bad_status():
    conn = _conn()
    update_project(conn, 1, 'Test', None, '', '', None, 'bogus', '')
    params = conn.execute.call_args[0][1]
    assert 'planning' in params

def test_update_project_does_not_commit():
    conn = _conn()
    update_project(conn, 1, 'Test', None, '', '', None, 'planning', '')
    conn.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def _task(**kw):
    base = {'id': 1, 'project_id': 1, 'task_name': 'Design review',
            'assigned_to': 'eng@co.com', 'due_date': '2024-03-01',
            'priority': 'medium', 'status': 'open', 'notes': '',
            'project_number': 'PROJ-2024-0001', 'project_title': 'Widget'}
    base.update(kw)
    return base


def test_list_project_tasks_returns_rows():
    conn = _conn(fetchall=[_task()])
    result = list_project_tasks(conn, 1)
    assert result[0]['task_name'] == 'Design review'

def test_list_tasks_no_filter():
    conn = _conn(fetchall=[])
    list_tasks(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql

def test_list_tasks_status_filter():
    conn = _conn(fetchall=[])
    list_tasks(conn, status='open')
    sql = conn.execute.call_args[0][0]
    assert 'status' in sql

def test_list_tasks_priority_filter():
    conn = _conn(fetchall=[])
    list_tasks(conn, priority='critical')
    params = conn.execute.call_args[0][1]
    assert 'critical' in params

def test_get_task_returns_row():
    conn = _conn(fetchone=_task())
    assert get_task(conn, 1)['task_name'] == 'Design review'

def test_get_task_returns_none():
    assert get_task(_conn(fetchone=None), 99) is None

def test_create_task_returns_id():
    conn = _conn(fetchone={'id': 3})
    tid = create_task(conn, 1, 'Draw schematic', 'eng@co.com',
                      '2024-03-01', 'high', '', 'u@co.com')
    assert tid == 3

def test_create_task_rejects_empty_name():
    with pytest.raises(ValueError):
        create_task(_conn(), 1, '', '', None, 'medium', '', '')

def test_create_task_defaults_bad_priority():
    conn = _conn(fetchone={'id': 1})
    create_task(conn, 1, 'Task', '', None, 'extreme', '', '')
    params = conn.execute.call_args[0][1]
    assert 'medium' in params

def test_create_task_sets_status_open():
    conn = _conn(fetchone={'id': 1})
    create_task(conn, 1, 'Task', '', None, 'medium', '', '')
    sql = conn.execute.call_args[0][0]
    assert "'open'" in sql

def test_create_task_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_task(conn, 1, 'Task', '', None, 'medium', '', '')
    conn.commit.assert_not_called()

def test_update_task_executes_update():
    conn = _conn()
    update_task(conn, 1, 'Updated', '', None, 'low', 'completed', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE eng_task' in sql

def test_update_task_rejects_empty_name():
    with pytest.raises(ValueError):
        update_task(_conn(), 1, '', '', None, 'medium', 'open', '')

def test_update_task_corrects_bad_priority():
    conn = _conn()
    update_task(conn, 1, 'Task', '', None, 'extreme', 'open', '')
    params = conn.execute.call_args[0][1]
    assert 'medium' in params

def test_update_task_corrects_bad_status():
    conn = _conn()
    update_task(conn, 1, 'Task', '', None, 'medium', 'bogus', '')
    params = conn.execute.call_args[0][1]
    assert 'open' in params


# ---------------------------------------------------------------------------
# ECRs
# ---------------------------------------------------------------------------

def _ecr(**kw):
    base = {'id': 1, 'ecr_number': 'ECR-2024-0001', 'title': 'Change motor spec',
            'product_id': None, 'project_id': 1,
            'requested_by': 'eng@co.com', 'review_date': '2024-02-01',
            'status': 'draft', 'notes': '', 'created_by': 'u@co.com',
            'project_number': 'PROJ-2024-0001', 'project_title': 'Widget'}
    base.update(kw)
    return base


def test_list_ecrs_returns_rows():
    conn = _conn(fetchall=[_ecr()])
    result = list_ecrs(conn)
    assert result[0]['ecr_number'] == 'ECR-2024-0001'

def test_list_ecrs_no_filter_no_where():
    conn = _conn(fetchall=[])
    list_ecrs(conn)
    sql = conn.execute.call_args[0][0]
    assert 'WHERE' not in sql

def test_list_ecrs_status_filter():
    conn = _conn(fetchall=[])
    list_ecrs(conn, status='pending')
    sql = conn.execute.call_args[0][0]
    assert 'status' in sql

def test_list_ecrs_project_filter():
    conn = _conn(fetchall=[])
    list_ecrs(conn, project_id=3)
    params = conn.execute.call_args[0][1]
    assert 3 in params

def test_list_ecrs_search_filter():
    conn = _conn(fetchall=[])
    list_ecrs(conn, search='motor')
    sql = conn.execute.call_args[0][0]
    assert 'ILIKE' in sql

def test_get_ecr_returns_row():
    conn = _conn(fetchone=_ecr())
    assert get_ecr(conn, 1)['ecr_number'] == 'ECR-2024-0001'

def test_get_ecr_returns_none():
    assert get_ecr(_conn(fetchone=None), 99) is None

def test_create_ecr_returns_id():
    conn = _conn(fetchone={'id': 4})
    eid = create_ecr(conn, 'ECR-2024-0002', 'New spec', None, 1,
                     'eng@co.com', '2024-03-01', '', 'u@co.com')
    assert eid == 4

def test_create_ecr_rejects_empty_title():
    with pytest.raises(ValueError):
        create_ecr(_conn(), '', '', None, None, '', None, '', '')

def test_create_ecr_sets_status_draft():
    conn = _conn(fetchone={'id': 1})
    create_ecr(conn, 'ECR-001', 'Test', None, None, '', None, '', '')
    sql = conn.execute.call_args[0][0]
    assert "'draft'" in sql

def test_create_ecr_does_not_commit():
    conn = _conn(fetchone={'id': 1})
    create_ecr(conn, 'ECR-001', 'Test', None, None, '', None, '', '')
    conn.commit.assert_not_called()

def test_update_ecr_executes_update():
    conn = _conn()
    update_ecr(conn, 1, 'Updated title', None, None, '', None, 'pending', '')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE eng_design_review' in sql

def test_update_ecr_rejects_empty_title():
    with pytest.raises(ValueError):
        update_ecr(_conn(), 1, '', None, None, '', None, 'draft', '')

def test_update_ecr_corrects_bad_status():
    conn = _conn()
    update_ecr(conn, 1, 'Test', None, None, '', None, 'bogus', '')
    params = conn.execute.call_args[0][1]
    assert 'draft' in params

def test_update_ecr_does_not_commit():
    conn = _conn()
    update_ecr(conn, 1, 'Test', None, None, '', None, 'draft', '')
    conn.commit.assert_not_called()

def test_set_ecr_status_executes_update():
    conn = _conn()
    set_ecr_status(conn, 1, 'approved')
    sql = conn.execute.call_args[0][0]
    assert 'UPDATE eng_design_review' in sql

def test_set_ecr_status_corrects_bad_status():
    conn = _conn()
    set_ecr_status(conn, 1, 'bogus')
    params = conn.execute.call_args[0][1]
    assert 'draft' in params


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def test_eng_reports_returns_expected_keys():
    call_count = [0]
    def fake_execute(sql, params=None):
        call_count[0] += 1
        m = MagicMock()
        m.fetchall.return_value = []
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    result = eng_reports(conn)
    assert 'proj_by_status' in result
    assert 'ecr_by_status' in result
    assert 'overdue_projects' in result
    assert 'open_tasks_by_priority' in result
    assert 'recent_ecrs' in result

def test_eng_reports_overdue_uses_today():
    sqls = []
    def fake_execute(sql, params=None):
        sqls.append(sql)
        m = MagicMock()
        m.fetchall.return_value = []
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    eng_reports(conn)
    assert any('due_date' in s for s in sqls)

def test_eng_reports_recent_ecrs_limited():
    sqls = []
    def fake_execute(sql, params=None):
        sqls.append(sql)
        m = MagicMock()
        m.fetchall.return_value = []
        return m
    conn = MagicMock()
    conn.execute.side_effect = fake_execute
    eng_reports(conn)
    assert any('LIMIT 10' in s for s in sqls)
