"""Small helpers shared across view submodules.

No view functions live here, so this module is deliberately not
star-imported into views/__init__.py like the domain submodules are.
"""

from datetime import date


def parse_date_param(raw, default=None):
    """Validate an optional 'YYYY-MM-DD' GET param.

    Returns `default` if raw is blank or not a valid ISO date, else the
    original string unchanged (callers that need a date object can parse it
    themselves — see views/_gantt.py, which needs date arithmetic on the
    result and passes date objects as `default` too).
    """
    raw = (raw or '').strip()
    if not raw:
        return default
    try:
        date.fromisoformat(raw)
    except ValueError:
        return default
    return raw
