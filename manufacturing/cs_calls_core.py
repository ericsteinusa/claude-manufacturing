"""Qt-free helpers for the Customer Service Calls screen.

Kept import-safe for CI (no PyQt6, no DB at import time) so the pure logic
— customer-label formatting, id parsing and record validation — can be
unit-tested. The GUI (cs_calls_widget.py) imports from here.
"""

# Editable columns of the calls2 table, in the order the form collects them.
CALL_COLUMNS = ("customer_id", "call", "call_date", "call_time",
                "completion_date", "completion_time", "comments_box",
                "completion_box")


def format_customer_label(
    customer_id, first_name: str | None = "", last_name: str | None = ""
) -> str:
    """Combobox label like ``"7 - Jane Doe"`` (id alone when no name)."""
    parts = [p for p in (first_name or "", last_name or "") if p]
    name = " ".join(parts).strip()
    return f"{customer_id} - {name}" if name else str(customer_id)


def parse_customer_id(label):
    """Extract the leading integer id from a customer label or raw value.

    Tolerates ``"7 - Jane Doe"``, ``"7"``, ``"{7} ..."`` and plain ints;
    returns ``None`` when no id can be read.
    """
    if label is None:
        return None
    if isinstance(label, int):
        return label
    token = str(label).strip().split(" ", 1)[0].strip("{}")
    try:
        return int(token)
    except (TypeError, ValueError):
        return None


def validate_call(customer_id, call) -> list:
    """Return a list of human-readable errors for a new/updated call.

    A call needs a customer and a problem description; completion details
    are optional (an open call has none yet).
    """
    errors = []
    if parse_customer_id(customer_id) is None:
        errors.append("Please select a customer.")
    if not (call or "").strip():
        errors.append("Please enter the call / problem description.")
    return errors
