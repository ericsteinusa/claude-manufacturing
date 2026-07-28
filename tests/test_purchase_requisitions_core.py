"""Tests for the Qt-free purchase-requisition authorization logic and data layer."""
from unittest.mock import MagicMock, patch

from manufacturing.purchase_requisitions_core import (
    can_authorize, is_manager, is_company_wide,
    AUTHORIZER_ROLES, COMPANY_WIDE_ROLES, REQ_STATUSES,
    list_requisitions, get_requisition,
    list_requisition_items, list_requisition_approvals,
    create_requisition, add_requisition_item,
    submit_requisition, decide_requisition,
)


def test_is_manager_true_for_all_authorizer_roles():
    for role in AUTHORIZER_ROLES:
        assert is_manager(role), f"{role!r} should be an authorizer"


def test_is_manager_false_for_non_authorizer():
    assert not is_manager("Employee")
    assert not is_manager("Admin")
    assert not is_manager("")
    assert not is_manager("clerk")


def test_is_company_wide_true_for_senior_roles():
    for role in COMPANY_WIDE_ROLES:
        assert is_company_wide(role)


def test_is_company_wide_false_for_dept_level_roles():
    assert not is_company_wide("Department Manager")
    assert not is_company_wide("Supervisor")
    assert not is_company_wide("Employee")


def test_can_authorize_happy_path():
    assert can_authorize("Department Manager", "submitted",
                         req_dept_id=5, actor_dept_id=5, is_own=False)


def test_can_authorize_company_wide_crosses_departments():
    assert can_authorize("President", "submitted",
                         req_dept_id=5, actor_dept_id=9, is_own=False)
    assert can_authorize("Vice President", "submitted",
                         req_dept_id=1, actor_dept_id=7, is_own=False)


def test_can_authorize_denied_when_not_manager():
    assert not can_authorize("Employee", "submitted",
                             req_dept_id=5, actor_dept_id=5, is_own=False)


def test_can_authorize_denied_when_not_submitted():
    assert not can_authorize("Department Manager", "draft",
                             req_dept_id=5, actor_dept_id=5, is_own=False)
    assert not can_authorize("Department Manager", "authorized",
                             req_dept_id=5, actor_dept_id=5, is_own=False)


def test_can_authorize_denied_for_own_request():
    assert not can_authorize("Department Manager", "submitted",
                             req_dept_id=5, actor_dept_id=5, is_own=True)


def test_can_authorize_denied_wrong_department():
    assert not can_authorize("Department Manager", "submitted",
                             req_dept_id=5, actor_dept_id=9, is_own=False)


def test_can_authorize_denied_when_dept_ids_are_none():
    # None dept IDs must not match each other — prevents accidental access.
    assert not can_authorize(
        "Department Manager", "submitted",
        req_dept_id=None, actor_dept_id=None, is_own=False
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_req_statuses_has_draft():
    assert 'draft' in REQ_STATUSES

def test_req_statuses_has_dept_approved():
    assert 'dept_approved' in REQ_STATUSES

def test_req_statuses_has_dept_denied():
    assert 'dept_denied' in REQ_STATUSES


# ---------------------------------------------------------------------------
# list_requisitions
# ---------------------------------------------------------------------------

def _list_conn(rows):
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows
    return c


def test_list_requisitions_returns_list():
    assert isinstance(
        list_requisitions(_list_conn([]), full_access=True, is_manager_role=False,
                          dept_id=None, requester_id=None), list)

def test_list_requisitions_full_access_sees_everything_no_filter():
    c = _list_conn([])
    list_requisitions(c, full_access=True, is_manager_role=False,
                      dept_id=5, requester_id=9)
    _, params = c.execute.call_args[0]
    assert params == []

def test_list_requisitions_manager_filters_by_dept():
    c = _list_conn([])
    list_requisitions(c, full_access=False, is_manager_role=True,
                      dept_id=5, requester_id=9)
    sql, params = c.execute.call_args[0]
    assert 'pr.dept_id = %s' in sql and params == [5]

def test_list_requisitions_regular_user_filters_by_requester():
    c = _list_conn([])
    list_requisitions(c, full_access=False, is_manager_role=False,
                      dept_id=5, requester_id=9)
    sql, params = c.execute.call_args[0]
    assert 'pr.requester_id = %s' in sql and params == [9]

def test_list_requisitions_status_filter():
    c = _list_conn([])
    list_requisitions(c, full_access=True, is_manager_role=False,
                      dept_id=None, requester_id=None, status='submitted')
    sql, params = c.execute.call_args[0]
    assert 'pr.status = %s' in sql and 'submitted' in params

def test_list_requisitions_search_filter():
    c = _list_conn([])
    list_requisitions(c, full_access=True, is_manager_role=False,
                      dept_id=None, requester_id=None, search='forklift')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('forklift' in str(p) for p in params)

def test_list_requisitions_converts_to_dicts():
    row = {'id': 1, 'req_number': 'REQ-2026-0001', 'dept_id': 5,
           'justification': 'Need parts', 'needed_date': '2026-08-01',
           'status': 'draft', 'notes': '', 'created_date': '2026-07-01',
           'requester_id': 9, 'requester_name': 'Jane Doe',
           'dept_name': 'Maintenance', 'est_total': 500.0}
    result = list_requisitions(_list_conn([row]), full_access=True,
                               is_manager_role=False, dept_id=None, requester_id=None)
    assert result[0]['req_number'] == 'REQ-2026-0001'


# ---------------------------------------------------------------------------
# get_requisition / list_requisition_items / list_requisition_approvals
# ---------------------------------------------------------------------------

def test_get_requisition_returns_dict():
    row = {'id': 1, 'req_number': 'REQ-2026-0001', 'status': 'draft'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_requisition(c, 1) == row

def test_get_requisition_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_requisition(c, 99) is None

def test_list_requisition_items_returns_list():
    assert isinstance(list_requisition_items(_list_conn([]), 1), list)

def test_list_requisition_items_converts_to_dicts():
    row = {'id': 1, 'description': 'Safety harness', 'product_id': None,
           'qty': 10, 'est_unit_price': 89.0, 'line_total': 890.0}
    result = list_requisition_items(_list_conn([row]), 1)
    assert result[0]['description'] == 'Safety harness'

def test_list_requisition_approvals_returns_list():
    assert isinstance(list_requisition_approvals(_list_conn([]), 1), list)


# ---------------------------------------------------------------------------
# create_requisition
# ---------------------------------------------------------------------------

def _create_conn(existing_numbers=None, new_id=1):
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(), MagicMock(), MagicMock(),  # ensure_requisition_tables' 3 CREATEs
        MagicMock(fetchall=MagicMock(return_value=[(n,) for n in (existing_numbers or [])])),
        MagicMock(fetchone=MagicMock(return_value=[new_id])),
    ]
    return c

def test_create_requisition_returns_id():
    c = _create_conn(new_id=7)
    result = create_requisition(c, requester_id=9, dept_id=5, dept_sub_id=None,
                                needed_date='2026-08-01', justification='Need parts',
                                notes='', created_by='jane@example.com')
    assert result == 7

def test_create_requisition_uses_insert():
    c = _create_conn()
    create_requisition(c, requester_id=9, dept_id=5, dept_sub_id=None,
                       needed_date='', justification='Need parts',
                       notes='', created_by='jane@example.com')
    sql = c.execute.call_args_list[-1][0][0]
    assert 'INSERT INTO purchase_requisition' in sql

def test_create_requisition_generates_sequential_number():
    import datetime
    year = datetime.date.today().year
    c = _create_conn(existing_numbers=[f'REQ-{year}-0001', f'REQ-{year}-0002'])
    create_requisition(c, requester_id=9, dept_id=5, dept_sub_id=None,
                       needed_date='', justification='Need parts',
                       notes='', created_by='jane@example.com')
    params = c.execute.call_args_list[-1][0][1]
    assert params[0] == f'REQ-{year}-0003'


# ---------------------------------------------------------------------------
# add_requisition_item
# ---------------------------------------------------------------------------

def test_add_requisition_item_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [3]
    result = add_requisition_item(c, 1, 'Safety harness', 10, 89.0)
    assert result == 3

def test_add_requisition_item_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    add_requisition_item(c, 1, 'Safety harness', 10, 89.0)
    sql = c.execute.call_args[0][0]
    assert 'INSERT INTO requisition_item' in sql and 'est_unit_price' in sql

def test_add_requisition_item_defaults_qty_and_price():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    add_requisition_item(c, 1, 'Safety harness', None, None)
    params = c.execute.call_args[0][1]
    assert params[2] == 1 and params[3] == 0.0


# ---------------------------------------------------------------------------
# submit_requisition
# ---------------------------------------------------------------------------

@patch('manufacturing.approval_workflow_core.submit_for_approval')
@patch('manufacturing.approval_workflow_core.ensure_approval_tables')
def test_submit_requisition_updates_status(mock_ensure, mock_submit):
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(),  # UPDATE status
        MagicMock(fetchone=MagicMock(return_value={'total': 890.0})),
        MagicMock(fetchone=MagicMock(return_value={'dept_name': 'Maintenance'})),
    ]
    submit_requisition(c, 1)
    sql = c.execute.call_args_list[0][0][0]
    assert "SET status = 'submitted'" in sql

@patch('manufacturing.approval_workflow_core.submit_for_approval')
@patch('manufacturing.approval_workflow_core.ensure_approval_tables')
def test_submit_requisition_calls_workflow_with_dept_key(mock_ensure, mock_submit):
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(),
        MagicMock(fetchone=MagicMock(return_value={'total': 890.0})),
        MagicMock(fetchone=MagicMock(return_value={'dept_name': 'Maintenance'})),
    ]
    submit_requisition(c, 1)
    mock_submit.assert_called_once()
    args = mock_submit.call_args[0]
    assert args[1] == 'purchase_requisition' and args[2] == 1 and args[3] == 890.0
    assert args[4] == 'maintenance'


# ---------------------------------------------------------------------------
# decide_requisition
# ---------------------------------------------------------------------------

def test_decide_requisition_approve_sets_dept_approved():
    c = MagicMock()
    result = decide_requisition(c, 1, 'approve', approver_id=3, comment='Looks good')
    assert result == 'dept_approved'

def test_decide_requisition_deny_sets_dept_denied():
    c = MagicMock()
    result = decide_requisition(c, 1, 'deny', approver_id=3, comment='Too costly')
    assert result == 'dept_denied'

def test_decide_requisition_inserts_approval_record():
    c = MagicMock()
    decide_requisition(c, 1, 'approve', approver_id=3, comment='Looks good')
    sql = c.execute.call_args_list[-1][0][0]
    assert 'INSERT INTO requisition_approval' in sql
