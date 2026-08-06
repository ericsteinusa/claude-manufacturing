"""Tests for fixed_asset_core — Fixed Asset Management (equipment, vehicles,
buildings, etc.) and depreciation calculations.

No live database: a fake connection replays canned rows, mirroring the
pattern in test_cash_flow_core.py / test_coa_core.py.
"""

from datetime import date, timedelta

from manufacturing.fixed_asset_core import (
    next_asset_number, list_fixed_assets, get_fixed_asset,
    create_fixed_asset, update_fixed_asset,
    log_fixed_asset_event, list_fixed_asset_events,
    calc_annual_depreciation, calc_accumulated_depreciation, calc_book_value,
    get_fixed_asset_summary,
)


# ── fake DB infrastructure (mirrors test_cash_flow_core.py / test_coa_core.py)

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


class _RaisingConn:
    def execute(self, sql, params=None):
        raise RuntimeError("boom")


# ── next_asset_number ────────────────────────────────────────────────────────

def test_next_asset_number_first_of_year():
    conn = _Conn(rows=[])
    n = next_asset_number(conn)
    year = date.today().year
    assert n == f"FA-{year}-0001"


def test_next_asset_number_increments_past_max():
    year = date.today().year
    conn = _Conn(rows=[{'asset_number': f'FA-{year}-0003'},
                        {'asset_number': f'FA-{year}-0007'}])
    n = next_asset_number(conn)
    assert n == f"FA-{year}-0008"


def test_next_asset_number_ignores_malformed_suffix():
    year = date.today().year
    conn = _Conn(rows=[{'asset_number': f'FA-{year}-0002'},
                        {'asset_number': f'FA-{year}-abcd'}])
    n = next_asset_number(conn)
    assert n == f"FA-{year}-0003"


# ── list_fixed_assets ────────────────────────────────────────────────────────

def test_list_fixed_assets_no_filters():
    conn = _Conn(rows=[])
    list_fixed_assets(conn)
    assert "WHERE TRUE" in conn.last_sql
    assert "status = %s" not in conn.last_sql
    assert conn.last_params == []


def test_list_fixed_assets_applies_status_type_and_search_filters():
    conn = _Conn(rows=[])
    list_fixed_assets(conn, status='Active', asset_type='Vehicle', search='truck')
    assert "status = %s" in conn.last_sql
    assert "asset_type = %s" in conn.last_sql
    assert "ILIKE %s OR asset_number ILIKE %s OR vendor ILIKE %s" in conn.last_sql
    assert conn.last_params == ['Active', 'Vehicle', '%truck%', '%truck%', '%truck%']


def test_list_fixed_assets_enriches_rows_with_book_value_and_depreciation():
    row = {
        'id': 1, 'asset_number': 'FA-2026-0001', 'purchase_price': 1000.0,
        'salvage_value': 100.0, 'useful_life_years': 9,
        'depreciation_method': 'Straight-Line', 'purchase_date': str(date.today()),
        'status': 'Active',
    }
    conn = _Conn(rows=[row])
    rows = list_fixed_assets(conn)
    assert rows[0]['annual_depreciation'] == 100.0  # (1000-100)/9
    assert rows[0]['book_value'] == 1000.0  # owned 0 days => no depreciation yet


# ── get_fixed_asset ──────────────────────────────────────────────────────────

def test_get_fixed_asset_returns_none_when_missing():
    conn = _Conn(rows=[])
    assert get_fixed_asset(conn, 999) is None


def test_get_fixed_asset_enriches_with_calculated_fields():
    row = {
        'id': 5, 'purchase_price': 5000.0, 'salvage_value': 500.0,
        'useful_life_years': 5, 'depreciation_method': 'Straight-Line',
        'purchase_date': str(date.today()),
    }
    conn = _Conn(rows=[row])
    result = get_fixed_asset(conn, 5)
    assert result['annual_depreciation'] == 900.0  # (5000-500)/5
    assert result['accumulated_depreciation'] == 0.0
    assert result['book_value'] == 5000.0


# ── create_fixed_asset ───────────────────────────────────────────────────────

def test_create_fixed_asset_returns_new_id():
    conn = _Conn(rows=[{'id': 42}])
    new_id = create_fixed_asset(
        conn, 'FA-2026-0001', 'Forklift', 'Equipment', 'Warehouse',
        'Dock A', 'Warehouse', 'Acme Corp', '2026-01-15', 15000, 1500,
        7, 'Straight-Line', 'Active', 'SN-001', 'notes', 'alice@example.com',
    )
    assert new_id == 42
    assert "INSERT INTO fixed_asset" in conn.last_sql
    assert "RETURNING id" in conn.last_sql


def test_create_fixed_asset_defaults_and_type_coercion():
    conn = _Conn(rows=[{'id': 1}])
    create_fixed_asset(
        conn, 'FA-2026-0002', 'Widget', 'Equipment', '', '', '', '',
        '', None, None, None, 'Straight-Line', '', '', '', 'bob@example.com',
    )
    params = conn.last_params
    # purchase_price, salvage_value coerced to float 0; useful_life_years -> 5;
    # status defaults to 'Active'; in_service_date '' -> None
    assert params[8] == 0.0    # purchase_price
    assert params[9] == 0.0    # salvage_value
    assert params[10] == 5     # useful_life_years
    assert params[12] == 'Active'  # status
    assert params[-1] is None  # in_service_date


# ── update_fixed_asset ───────────────────────────────────────────────────────

def test_update_fixed_asset_only_allowed_fields():
    conn = _Conn(rows=[])
    update_fixed_asset(conn, 7, asset_name='New Name', status='Inactive',
                        created_by='hacker', not_a_real_field='x')
    assert "asset_name = %s" in conn.last_sql
    assert "status = %s" in conn.last_sql
    assert "created_by" not in conn.last_sql
    assert "not_a_real_field" not in conn.last_sql
    assert conn.last_params == ['New Name', 'Inactive', 7]


def test_update_fixed_asset_noop_when_no_allowed_fields():
    conn = _Conn(rows=[])
    update_fixed_asset(conn, 7, created_by='hacker', bogus='x')
    assert conn.calls == []


# ── log_fixed_asset_event / list_fixed_asset_events ─────────────────────────

def test_log_fixed_asset_event_inserts_row():
    conn = _Conn(rows=[])
    log_fixed_asset_event(conn, 3, 'Status Change', 'Moved to Under Repair', 'alice')
    assert "INSERT INTO fixed_asset_event" in conn.last_sql
    assert conn.last_params == [3, 'Status Change', 'Moved to Under Repair', 'alice']


def test_list_fixed_asset_events_returns_dicts_ordered_by_conn():
    rows = [
        {'id': 2, 'event_type': 'Disposed', 'description': '', 'changed_by': 'bob',
         'changed_at': '2026-02-01'},
        {'id': 1, 'event_type': 'Created', 'description': '', 'changed_by': 'alice',
         'changed_at': '2026-01-01'},
    ]
    conn = _Conn(rows=rows)
    result = list_fixed_asset_events(conn, 3)
    assert result == rows
    assert "ORDER BY changed_at DESC" in conn.last_sql
    assert conn.last_params == [3]


# ── calc_annual_depreciation ─────────────────────────────────────────────────

def test_calc_annual_depreciation_none_method_is_zero():
    asset = {'depreciation_method': 'None', 'purchase_price': 1000, 'salvage_value': 0,
              'useful_life_years': 5}
    assert calc_annual_depreciation(asset) == 0.0


def test_calc_annual_depreciation_zero_price_is_zero():
    asset = {'depreciation_method': 'Straight-Line', 'purchase_price': 0,
              'salvage_value': 0, 'useful_life_years': 5}
    assert calc_annual_depreciation(asset) == 0.0


def test_calc_annual_depreciation_straight_line():
    asset = {'depreciation_method': 'Straight-Line', 'purchase_price': 10000,
              'salvage_value': 1000, 'useful_life_years': 9}
    assert calc_annual_depreciation(asset) == 1000.0  # (10000-1000)/9


def test_calc_annual_depreciation_declining_balance():
    asset = {'depreciation_method': 'Declining Balance', 'purchase_price': 10000,
              'salvage_value': 1000, 'useful_life_years': 5}
    # double-declining rate = 2/5 = 0.4 -> 10000 * 0.4
    assert calc_annual_depreciation(asset) == 4000.0


def test_calc_annual_depreciation_unknown_method_falls_back_to_straight_line():
    asset = {'depreciation_method': 'Bogus', 'purchase_price': 5000,
              'salvage_value': 500, 'useful_life_years': 5}
    assert calc_annual_depreciation(asset) == 900.0  # (5000-500)/5


def test_calc_annual_depreciation_zero_life_defaults_to_five():
    asset = {'depreciation_method': 'Straight-Line', 'purchase_price': 5000,
              'salvage_value': 0, 'useful_life_years': 0}
    assert calc_annual_depreciation(asset) == 1000.0  # 5000/5 (life 0 -> 5)


# ── calc_accumulated_depreciation ────────────────────────────────────────────

def test_calc_accumulated_depreciation_no_purchase_date_is_zero():
    asset = {'purchase_date': '', 'purchase_price': 1000, 'salvage_value': 0,
              'useful_life_years': 5, 'depreciation_method': 'Straight-Line'}
    assert calc_accumulated_depreciation(asset) == 0.0


def test_calc_accumulated_depreciation_invalid_date_is_zero():
    asset = {'purchase_date': 'not-a-date', 'purchase_price': 1000,
              'salvage_value': 0, 'useful_life_years': 5,
              'depreciation_method': 'Straight-Line'}
    assert calc_accumulated_depreciation(asset) == 0.0


def test_calc_accumulated_depreciation_purchased_today_is_zero():
    asset = {'purchase_date': str(date.today()), 'purchase_price': 1000,
              'salvage_value': 0, 'useful_life_years': 5,
              'depreciation_method': 'Straight-Line'}
    assert calc_accumulated_depreciation(asset) == 0.0


def test_calc_accumulated_depreciation_partial_year():
    purchase_date = date.today() - timedelta(days=730)  # ~2 years ago
    asset = {'purchase_date': str(purchase_date), 'purchase_price': 10000,
              'salvage_value': 1000, 'useful_life_years': 9,
              'depreciation_method': 'Straight-Line'}
    annual = calc_annual_depreciation(asset)
    years_owned = (date.today() - purchase_date).days / 365.25
    expected = round(min(annual * years_owned, 9000), 2)
    assert calc_accumulated_depreciation(asset) == expected


def test_calc_accumulated_depreciation_caps_at_price_minus_salvage():
    old_date = date(2000, 1, 1)  # always far enough in the past to fully depreciate
    asset = {'purchase_date': str(old_date), 'purchase_price': 10000,
              'salvage_value': 1000, 'useful_life_years': 2,
              'depreciation_method': 'Straight-Line'}
    assert calc_accumulated_depreciation(asset) == 9000.0  # capped at price - salvage


# ── calc_book_value ──────────────────────────────────────────────────────────

def test_calc_book_value_new_asset_equals_purchase_price():
    asset = {'purchase_date': str(date.today()), 'purchase_price': 10000,
              'salvage_value': 1000, 'useful_life_years': 9,
              'depreciation_method': 'Straight-Line'}
    assert calc_book_value(asset) == 10000.0


def test_calc_book_value_fully_depreciated_asset_floors_at_salvage_value():
    old_date = date(2000, 1, 1)
    asset = {'purchase_date': str(old_date), 'purchase_price': 10000,
              'salvage_value': 1000, 'useful_life_years': 2,
              'depreciation_method': 'Straight-Line'}
    assert calc_book_value(asset) == 1000.0


# ── get_fixed_asset_summary ──────────────────────────────────────────────────

def test_get_fixed_asset_summary_aggregates_across_assets():
    rows = [
        {'id': 1, 'purchase_price': 10000, 'salvage_value': 1000,
         'useful_life_years': 2, 'depreciation_method': 'Straight-Line',
         'purchase_date': str(date(2000, 1, 1)), 'status': 'Active'},
        {'id': 2, 'purchase_price': 5000, 'salvage_value': 0,
         'useful_life_years': 5, 'depreciation_method': 'Straight-Line',
         'purchase_date': str(date.today()), 'status': 'Disposed'},
    ]
    conn = _Conn(rows=rows)
    summary = get_fixed_asset_summary(conn)
    assert summary['count'] == 2
    assert summary['active'] == 1
    assert summary['total_cost'] == 15000.0
    assert summary['total_book_value'] == 1000.0 + 5000.0
    assert summary['total_accumulated_depreciation'] == 9000.0 + 0.0


def test_get_fixed_asset_summary_returns_empty_dict_on_query_error():
    assert get_fixed_asset_summary(_RaisingConn()) == {}
