"""Tests for manufacturing/termination_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock, patch

from manufacturing.termination_core import (
    TERM_TYPES, TERM_STATUSES, REHIRE_OPTIONS,
    EXIT_INTERVIEW_RECOMMEND_OPTIONS,
    OFFBOARD_STATUSES, OFFBOARD_DEFAULT_TASKS,
    list_terminations, get_termination, create_termination, update_termination,
    list_exit_interviews, get_exit_interview, create_exit_interview,
    list_offboarding_tasks, create_offboarding_task, complete_offboarding_task,
)


def _list_conn(rows):
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows
    return c


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_term_types_has_voluntary():
    assert 'Voluntary' in TERM_TYPES

def test_term_statuses_has_initiated():
    assert 'Initiated' in TERM_STATUSES

def test_term_statuses_has_completed():
    assert 'Completed' in TERM_STATUSES

def test_rehire_options_has_yes():
    assert 'Yes' in REHIRE_OPTIONS

def test_exit_interview_recommend_options_has_unsure():
    assert 'Unsure' in EXIT_INTERVIEW_RECOMMEND_OPTIONS

def test_offboard_statuses_has_pending():
    assert 'Pending' in OFFBOARD_STATUSES

def test_offboard_default_tasks_nonempty():
    assert len(OFFBOARD_DEFAULT_TASKS) > 0


# ---------------------------------------------------------------------------
# list_terminations / get_termination
# ---------------------------------------------------------------------------

def test_list_terminations_returns_list():
    assert isinstance(list_terminations(_list_conn([])), list)

def test_list_terminations_status_filter():
    c = _list_conn([])
    list_terminations(c, status='Completed')
    sql, params = c.execute.call_args[0]
    assert 'tr.status = %s' in sql and 'Completed' in params

def test_list_terminations_search_filter():
    c = _list_conn([])
    list_terminations(c, search='layoff')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('layoff' in str(p) for p in params)

def test_list_terminations_converts_to_dicts():
    row = {'id': 1, 'people_id': 9, 'termination_date': '2026-08-01',
           'term_type': 'Voluntary', 'reason': 'New opportunity',
           'status': 'Initiated', 'rehire_eligible': 'Yes',
           'employee_name': 'Jane Doe', 'dept_name': 'Engineering'}
    result = list_terminations(_list_conn([row]))
    assert result[0]['employee_name'] == 'Jane Doe'

def test_get_termination_returns_dict():
    row = {'id': 1, 'people_id': 9, 'status': 'Initiated'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_termination(c, 1) == row

def test_get_termination_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_termination(c, 99) is None


# ---------------------------------------------------------------------------
# create_termination
# ---------------------------------------------------------------------------

def test_create_termination_returns_id_no_date():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 5}
    result = create_termination(c, people_id=9, termination_date='', term_type='Voluntary',
                                reason='New job', status='Initiated',
                                rehire_eligible='Yes', notes='', created_by='hr@example.com')
    assert result == 5

def test_create_termination_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 1}
    create_termination(c, people_id=9, termination_date='', term_type='Voluntary',
                       reason='', status='Initiated', rehire_eligible='Yes',
                       notes='', created_by='')
    sql = c.execute.call_args[0][0]
    assert 'INSERT INTO termination_record' in sql

@patch('manufacturing.termination_core.set_employment_dates')
def test_create_termination_syncs_employment_dates_when_date_given(mock_set):
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(), MagicMock(), MagicMock(),  # _ensure_tables' 3 CREATEs
        MagicMock(fetchone=MagicMock(return_value={'id': 5})),  # INSERT
        MagicMock(fetchone=MagicMock(return_value={'hire_date': '2020-01-01'})),  # SELECT hire_date
    ]
    create_termination(c, people_id=9, termination_date='2026-08-01', term_type='Voluntary',
                       reason='', status='Initiated', rehire_eligible='Yes',
                       notes='', created_by='')
    mock_set.assert_called_once()
    args, kwargs = mock_set.call_args
    assert kwargs['hire_date'] == '2020-01-01'
    assert kwargs['termination_date'] == '2026-08-01'
    assert kwargs['employment_status'] == 'terminated'

@patch('manufacturing.termination_core.set_employment_dates')
def test_create_termination_does_not_sync_when_no_date(mock_set):
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 1}
    create_termination(c, people_id=9, termination_date='', term_type='Voluntary',
                       reason='', status='Initiated', rehire_eligible='Yes',
                       notes='', created_by='')
    mock_set.assert_not_called()


# ---------------------------------------------------------------------------
# update_termination
# ---------------------------------------------------------------------------

def test_update_termination_builds_set_clause():
    c = MagicMock()
    update_termination(c, 1, status='Completed')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE termination_record' in sql and 'status' in sql

def test_update_termination_ignores_unknown_fields():
    c = MagicMock()
    update_termination(c, 1, bogus='x')
    c.execute.assert_not_called()

def test_update_termination_noop_when_no_fields():
    c = MagicMock()
    update_termination(c, 1)
    c.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Exit interviews
# ---------------------------------------------------------------------------

def test_list_exit_interviews_returns_list():
    assert isinstance(list_exit_interviews(_list_conn([])), list)

def test_list_exit_interviews_search_filter():
    c = _list_conn([])
    list_exit_interviews(c, search='relocation')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('relocation' in str(p) for p in params)

def test_get_exit_interview_returns_dict():
    row = {'id': 1, 'people_id': 9}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_exit_interview(c, 1) == row

def test_get_exit_interview_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_exit_interview(c, 99) is None

def test_create_exit_interview_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 3}
    result = create_exit_interview(c, people_id=9, interview_date='2026-08-01',
                                   interviewer='HR Manager', reason_for_leaving='Relocation',
                                   feedback='Positive', would_recommend='Yes', notes='')
    assert result == 3

def test_create_exit_interview_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 1}
    create_exit_interview(c, people_id=9, interview_date='', interviewer='',
                          reason_for_leaving='', feedback='', would_recommend='', notes='')
    sql = c.execute.call_args[0][0]
    assert 'INSERT INTO exit_interview' in sql


# ---------------------------------------------------------------------------
# Offboarding tasks
# ---------------------------------------------------------------------------

def test_list_offboarding_tasks_returns_list():
    assert isinstance(list_offboarding_tasks(_list_conn([])), list)

def test_list_offboarding_tasks_status_filter():
    c = _list_conn([])
    list_offboarding_tasks(c, status='Pending')
    sql, params = c.execute.call_args[0]
    assert 'ot.status = %s' in sql and 'Pending' in params

def test_create_offboarding_task_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 4}
    result = create_offboarding_task(c, people_id=9, task='Return laptop',
                                     status='Pending', due_date='2026-08-05',
                                     assigned_to='IT', notes='')
    assert result == 4

def test_create_offboarding_task_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 1}
    create_offboarding_task(c, people_id=9, task='Return laptop', status='Pending',
                            due_date='', assigned_to='', notes='')
    sql = c.execute.call_args[0][0]
    assert 'INSERT INTO offboarding_task' in sql

def test_complete_offboarding_task_updates_status():
    c = MagicMock()
    complete_offboarding_task(c, 4, '2026-08-10')
    sql, params = c.execute.call_args[0]
    assert "status = 'Completed'" in sql and '2026-08-10' in params
