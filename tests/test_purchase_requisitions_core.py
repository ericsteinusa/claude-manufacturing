"""Tests for the Qt-free purchase-requisition authorization logic."""
from manufacturing.purchase_requisitions_core import (
    can_authorize, is_manager, is_company_wide,
    AUTHORIZER_ROLES, COMPANY_WIDE_ROLES,
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
