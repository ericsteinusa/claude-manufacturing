"""Qt-free purchase-requisition authorization logic.

Kept separate from purchase_requisitions.py (which imports PyQt6) so the
authorization rules can be unit-tested without Qt.
"""

COMPANY_WIDE_ROLES = (
    "President",
    "Vice President",
)

AUTHORIZER_ROLES = (
    "Department Manager",
    "Supervisor",
) + COMPANY_WIDE_ROLES


def is_manager(role_name):
    """True if role may authorize requisitions."""
    return role_name in AUTHORIZER_ROLES


def is_company_wide(role_name):
    """True if role may authorize any department's requests (not just own)."""
    return role_name in COMPANY_WIDE_ROLES


def can_authorize(role, status, req_dept_id, actor_dept_id, is_own):
    """Return True if the actor may authorize or deny a requisition.

    Rules:
    - Actor must hold an authorizer role (manager / supervisor / executive)
    - Requisition must be in 'submitted' status
    - Actor must be in scope: company-wide role OR same dept as the request
    - Actor cannot authorize their own request
    - None dept IDs are never treated as matching (prevents accidental
      cross-dept access)
    """
    if not is_manager(role):
        return False
    if status != "submitted":
        return False
    if is_own:
        return False
    in_scope = is_company_wide(role) or (
        req_dept_id is not None and req_dept_id == actor_dept_id)
    return in_scope
