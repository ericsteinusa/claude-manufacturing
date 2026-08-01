"""Tests for manufacturing/credit_core.py — pure unit tests, no Qt, no DB."""

import pytest
from unittest.mock import MagicMock

from manufacturing.credit_core import (
    get_credit_dashboard,
    list_credit_accounts, get_credit_account, get_credit_account_by_customer,
    customers_without_credit_account, create_credit_account, update_credit_account,
    list_limit_history,
    list_credit_applications, get_credit_application,
    create_credit_application, decide_credit_application,
    list_collection_activities, get_collection_activity,
    create_collection_activity, update_collection_activity,
    CREDIT_STATUSES, APPLICATION_STATUSES, COLLECTION_STATUSES, ACTIVITY_TYPES,
)

_ACCT_STATS = {'total': 10, 'good': 7, 'hold': 2, 'suspended': 1, 'total_exposure': 210000.0}
_APP_STATS = {'total': 8, 'pending': 2}
_COLL_STATS = {'total': 5, 'open': 5}


def _dash_conn(acct=None, app=None, coll=None):
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value=acct if acct is not None else _ACCT_STATS)),
        MagicMock(fetchone=MagicMock(return_value=app if app is not None else _APP_STATS)),
        MagicMock(fetchone=MagicMock(return_value=coll if coll is not None else _COLL_STATS)),
    ]
    return c


# ---------------------------------------------------------------------------
# get_credit_dashboard
# ---------------------------------------------------------------------------

def test_dashboard_returns_dict():
    assert isinstance(get_credit_dashboard(_dash_conn()), dict)


def test_dashboard_accounts_total():
    assert get_credit_dashboard(_dash_conn())['accounts']['total'] == 10


def test_dashboard_applications_pending():
    assert get_credit_dashboard(_dash_conn())['applications']['pending'] == 2


def test_dashboard_collections_open():
    assert get_credit_dashboard(_dash_conn())['collections']['open'] == 5


def test_dashboard_falls_back_when_fetchone_returns_none():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    result = get_credit_dashboard(c)
    assert result['accounts'] == {
        'total': 0, 'good': 0, 'hold': 0, 'suspended': 0, 'total_exposure': 0.0}
    assert result['applications'] == {'total': 0, 'pending': 0}
    assert result['collections'] == {'total': 0, 'open': 0}


# ---------------------------------------------------------------------------
# list_credit_accounts / get_credit_account
# ---------------------------------------------------------------------------

def _rows_conn(rows):
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows
    return c


def test_list_credit_accounts_returns_list():
    assert list_credit_accounts(_rows_conn([])) == []


def test_list_credit_accounts_status_filter_in_sql():
    c = _rows_conn([])
    list_credit_accounts(c, status='hold')
    sql = c.execute.call_args[0][0]
    assert 'ca.status = %s' in sql


def test_list_credit_accounts_search_filter_in_sql():
    c = _rows_conn([])
    list_credit_accounts(c, search='acme')
    sql = c.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_get_credit_account_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_credit_account(c, 99) is None


def test_get_credit_account_by_customer_found():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 3, 'customer_id': 1}
    assert get_credit_account_by_customer(c, 1)['id'] == 3


def test_customers_without_credit_account_returns_list():
    assert customers_without_credit_account(_rows_conn([])) == []


# ---------------------------------------------------------------------------
# create_credit_account
# ---------------------------------------------------------------------------

def test_create_credit_account_requires_customer():
    c = MagicMock()
    with pytest.raises(ValueError):
        create_credit_account(c, 0, 5000, 'good', 'Net 30', '2026-01-01', '')


def test_create_credit_account_rejects_duplicate():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 1, 'customer_id': 5}
    with pytest.raises(ValueError):
        create_credit_account(c, 5, 5000, 'good', 'Net 30', '2026-01-01', '')


def test_create_credit_account_returns_id():
    c = MagicMock()
    # first call: get_credit_account_by_customer -> None (no existing account)
    # second call: the INSERT ... RETURNING id
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value=None)),
        MagicMock(fetchone=MagicMock(return_value={'id': 7})),
    ]
    result = create_credit_account(c, 5, 5000, 'good', 'Net 30', '2026-01-01', '')
    assert result == 7


def test_create_credit_account_defaults_bad_status_to_good():
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value=None)),
        MagicMock(fetchone=MagicMock(return_value={'id': 1})),
    ]
    create_credit_account(c, 5, 5000, 'bogus', '', '2026-01-01', '')
    params = c.execute.call_args[0][1]
    assert params[2] == 'good'


# ---------------------------------------------------------------------------
# update_credit_account
# ---------------------------------------------------------------------------

def test_update_credit_account_missing_raises():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    with pytest.raises(ValueError):
        update_credit_account(c, 99, 5000, 'good', '', '', 'a@example.com')


def test_update_credit_account_no_history_when_unchanged():
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value={'credit_limit': 5000, 'status': 'good'})),
        MagicMock(),  # UPDATE credit_account
    ]
    update_credit_account(c, 1, 5000, 'good', 'Net 30', '', 'a@example.com')
    assert c.execute.call_count == 2  # SELECT + UPDATE only, no history INSERT


def test_update_credit_account_logs_history_on_limit_change():
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value={'credit_limit': 5000, 'status': 'good'})),
        MagicMock(),  # UPDATE credit_account
        MagicMock(fetchone=MagicMock(return_value={'customer_id': 9})),
        MagicMock(),  # INSERT credit_limit_history
    ]
    update_credit_account(c, 1, 8000, 'good', 'Net 30', '', 'a@example.com')
    assert c.execute.call_count == 4
    history_sql = c.execute.call_args_list[3][0][0]
    assert 'INSERT INTO credit_limit_history' in history_sql


def test_update_credit_account_logs_history_on_status_change():
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value={'credit_limit': 5000, 'status': 'good'})),
        MagicMock(),
        MagicMock(fetchone=MagicMock(return_value={'customer_id': 9})),
        MagicMock(),
    ]
    update_credit_account(c, 1, 5000, 'hold', 'Net 30', '', 'a@example.com')
    assert c.execute.call_count == 4


# ---------------------------------------------------------------------------
# list_limit_history
# ---------------------------------------------------------------------------

def test_list_limit_history_returns_list():
    assert list_limit_history(_rows_conn([])) == []


def test_list_limit_history_customer_filter_in_sql():
    c = _rows_conn([])
    list_limit_history(c, customer_id=5)
    sql = c.execute.call_args[0][0]
    assert 'h.customer_id = %s' in sql


# ---------------------------------------------------------------------------
# credit applications
# ---------------------------------------------------------------------------

def test_list_credit_applications_returns_list():
    assert list_credit_applications(_rows_conn([])) == []


def test_get_credit_application_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_credit_application(c, 99) is None


def test_create_credit_application_requires_customer():
    c = MagicMock()
    with pytest.raises(ValueError):
        create_credit_application(c, 0, '2026-01-01', 1000, '', 'a@example.com')


def test_create_credit_application_requires_positive_limit():
    c = MagicMock()
    with pytest.raises(ValueError):
        create_credit_application(c, 5, '2026-01-01', 0, '', 'a@example.com')


def test_create_credit_application_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 4}
    assert create_credit_application(c, 5, '2026-01-01', 1000, '', 'a@example.com') == 4


# ---------------------------------------------------------------------------
# decide_credit_application
# ---------------------------------------------------------------------------

def test_decide_credit_application_bad_decision_raises():
    c = MagicMock()
    with pytest.raises(ValueError):
        decide_credit_application(c, 1, 'maybe', None, 'a@example.com', '')


def test_decide_credit_application_missing_raises():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    with pytest.raises(ValueError):
        decide_credit_application(c, 99, 'approved', 5000, 'a@example.com', '')


def test_decide_credit_application_already_decided_raises():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {
        'id': 1, 'status': 'approved', 'customer_id': 5, 'requested_limit': 1000, 'notes': '',
    }
    with pytest.raises(ValueError):
        decide_credit_application(c, 1, 'approved', 5000, 'a@example.com', '')


def test_decide_credit_application_denied_does_not_touch_accounts():
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value={
            'id': 1, 'status': 'pending', 'customer_id': 5,
            'requested_limit': 1000, 'notes': '',
        })),
        MagicMock(),  # UPDATE credit_application
    ]
    decide_credit_application(c, 1, 'denied', None, 'a@example.com', 'not qualified')
    assert c.execute.call_count == 2


def test_decide_credit_application_approved_opens_new_account():
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value={
            'id': 1, 'status': 'pending', 'customer_id': 5,
            'requested_limit': 1000, 'notes': '',
        })),
        MagicMock(),  # UPDATE credit_application
        MagicMock(fetchone=MagicMock(return_value=None)),  # get_credit_account_by_customer -> none
        MagicMock(fetchone=MagicMock(return_value=None)),  # create_credit_account: dup check
        MagicMock(fetchone=MagicMock(return_value={'id': 20})),  # INSERT credit_account
        MagicMock(),  # INSERT credit_limit_history
    ]
    decide_credit_application(c, 1, 'approved', 5000, 'a@example.com', '')
    assert c.execute.call_count == 6
    last_sql = c.execute.call_args_list[-1][0][0]
    assert 'INSERT INTO credit_limit_history' in last_sql


def test_decide_credit_application_approved_updates_existing_account():
    c = MagicMock()
    c.execute.side_effect = [
        MagicMock(fetchone=MagicMock(return_value={
            'id': 1, 'status': 'pending', 'customer_id': 5,
            'requested_limit': 1000, 'notes': '',
        })),
        MagicMock(),  # UPDATE credit_application
        MagicMock(fetchone=MagicMock(return_value={
            'id': 20, 'status': 'good', 'terms': 'Net 30', 'notes': '',
            'credit_limit': 3000,
        })),  # get_credit_account_by_customer -> existing
        MagicMock(fetchone=MagicMock(return_value={'credit_limit': 3000, 'status': 'good'})),
        MagicMock(),  # UPDATE credit_account
        MagicMock(fetchone=MagicMock(return_value={'customer_id': 5})),
        MagicMock(),  # INSERT credit_limit_history
    ]
    decide_credit_application(c, 1, 'approved', 5000, 'a@example.com', '')
    assert c.execute.call_count == 7


# ---------------------------------------------------------------------------
# collections
# ---------------------------------------------------------------------------

def test_list_collection_activities_returns_list():
    assert list_collection_activities(_rows_conn([])) == []


def test_list_collection_activities_customer_filter_in_sql():
    c = _rows_conn([])
    list_collection_activities(c, customer_id=5)
    sql = c.execute.call_args[0][0]
    assert 'ca.customer_id = %s' in sql


def test_get_collection_activity_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_collection_activity(c, 99) is None


def test_create_collection_activity_requires_customer():
    c = MagicMock()
    with pytest.raises(ValueError):
        create_collection_activity(
            c, 0, '2026-01-01', 'Call', '', '', None, None, None, 'Open', 'a@example.com')


def test_create_collection_activity_bad_type_defaults_to_other():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 1}
    create_collection_activity(
        c, 5, '2026-01-01', 'Bogus', '', '', None, None, None, 'Open', 'a@example.com')
    params = c.execute.call_args[0][1]
    assert params[2] == 'Other'


def test_create_collection_activity_bad_status_defaults_to_open():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 1}
    create_collection_activity(
        c, 5, '2026-01-01', 'Call', '', '', None, None, None, 'Bogus', 'a@example.com')
    params = c.execute.call_args[0][1]
    assert params[8] == 'Open'


def test_create_collection_activity_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = {'id': 11}
    result = create_collection_activity(
        c, 5, '2026-01-01', 'Call', 'Jane', '', 500, '2026-02-01', None, 'Open', 'a@example.com')
    assert result == 11


def test_update_collection_activity_builds_set_clause():
    c = MagicMock()
    update_collection_activity(c, 1, status='Resolved', notes='done')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE collection_activity' in sql and 'status' in sql


def test_update_collection_activity_ignores_unknown_fields():
    c = MagicMock()
    update_collection_activity(c, 1, bogus='x')
    c.execute.assert_not_called()


def test_update_collection_activity_noop_when_no_fields():
    c = MagicMock()
    update_collection_activity(c, 1)
    c.execute.assert_not_called()


def test_update_collection_activity_bad_status_defaults_to_open():
    c = MagicMock()
    update_collection_activity(c, 1, status='Bogus')
    params = c.execute.call_args[0][1]
    assert params[0] == 'Open'


# ---------------------------------------------------------------------------
# status tuples
# ---------------------------------------------------------------------------

def test_credit_statuses_tuple():
    assert CREDIT_STATUSES == ('good', 'hold', 'suspended', 'closed')


def test_application_statuses_tuple():
    assert APPLICATION_STATUSES == ('pending', 'approved', 'denied')


def test_collection_statuses_tuple():
    assert COLLECTION_STATUSES == ('Open', 'In Progress', 'Escalated', 'Resolved')


def test_activity_types_tuple():
    assert ACTIVITY_TYPES == ('Call', 'Email', 'Letter', 'Visit', 'Other')
