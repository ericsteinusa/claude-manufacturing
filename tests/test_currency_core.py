"""Tests for currency_core — multi-currency support (currency table CRUD,
schema bootstrap/seeding, and base-currency conversion math).

No live database: a fake connection replays canned rows, mirroring the
pattern in test_cash_flow_core.py / test_fixed_asset_core.py. Rows are
plain dicts everywhere except the COUNT(*) check in init_currency_schema,
which the real code reads positionally (row[0]) the way psycopg2's
DictCursor rows support both dict and index access — so that one row is a
tuple instead.
"""

from manufacturing.currency_core import (
    COMMON_CURRENCIES, init_currency_schema, list_currencies, get_currency,
    upsert_currency, get_base_currency, convert_to_base, get_currency_symbol,
)


# ── fake DB infrastructure (mirrors test_cash_flow_core.py's _DispatchConn)

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
    """Returns canned rows based on a substring match against the SQL."""
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, list(params or [])))
        for substring, rows in self.routes:
            if substring in sql:
                return _Cursor(rows)
        return _Cursor([])


# ── COMMON_CURRENCIES ────────────────────────────────────────────────────────

def test_common_currencies_includes_usd_as_base_rate_one():
    codes = [c[0] for c in COMMON_CURRENCIES]
    assert 'USD' in codes
    usd = next(c for c in COMMON_CURRENCIES if c[0] == 'USD')
    assert usd[3] == 1.0


def test_common_currencies_all_have_four_fields():
    for entry in COMMON_CURRENCIES:
        assert len(entry) == 4


# ── init_currency_schema ─────────────────────────────────────────────────────

def test_init_currency_schema_creates_table_and_alters_financial_tables():
    conn = _DispatchConn([("SELECT COUNT(*) FROM currency", [(5,)])])
    init_currency_schema(conn)
    sqls = [c[0] for c in conn.calls]
    assert any("CREATE TABLE IF NOT EXISTS currency" in s for s in sqls)
    for table in ('purchase_order', 'sales_order', 'ap_invoice', 'ar_invoice'):
        assert any(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS currency" in s
            for s in sqls
        )
        assert any(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS exchange_rate" in s
            for s in sqls
        )


def test_init_currency_schema_seeds_common_currencies_when_table_empty():
    conn = _DispatchConn([("SELECT COUNT(*) FROM currency", [(0,)])])
    init_currency_schema(conn)
    insert_calls = [c for c in conn.calls if c[0].startswith("INSERT INTO currency")]
    assert len(insert_calls) == len(COMMON_CURRENCIES)
    usd_call = next(c for c in insert_calls if c[1][0] == 'USD')
    assert usd_call[1][-1] is True  # is_base = (code == 'USD')
    eur_call = next(c for c in insert_calls if c[1][0] == 'EUR')
    assert eur_call[1][-1] is False


def test_init_currency_schema_skips_seeding_when_table_not_empty():
    conn = _DispatchConn([("SELECT COUNT(*) FROM currency", [(3,)])])
    init_currency_schema(conn)
    insert_calls = [c for c in conn.calls if c[0].startswith("INSERT INTO currency")]
    assert insert_calls == []


# ── list_currencies ──────────────────────────────────────────────────────────

def test_list_currencies_default_has_no_active_filter():
    conn = _Conn(rows=[])
    list_currencies(conn)
    assert "WHERE is_active = TRUE" not in conn.last_sql
    assert "ORDER BY is_base DESC, code" in conn.last_sql


def test_list_currencies_active_only_adds_filter():
    conn = _Conn(rows=[])
    list_currencies(conn, active_only=True)
    assert "WHERE is_active = TRUE" in conn.last_sql


def test_list_currencies_returns_list_of_dicts():
    row = {'id': 1, 'code': 'USD', 'name': 'US Dollar', 'symbol': '$',
           'exchange_rate': 1.0, 'is_base': True, 'is_active': True,
           'updated_at': ''}
    conn = _Conn(rows=[row])
    result = list_currencies(conn)
    assert result == [row]


# ── get_currency ──────────────────────────────────────────────────────────

def test_get_currency_found():
    row = {'id': 2, 'code': 'EUR', 'name': 'Euro', 'symbol': '€'}
    conn = _Conn(rows=[row])
    assert get_currency(conn, 'EUR') == row
    assert conn.last_params == ['EUR']


def test_get_currency_not_found_returns_none():
    conn = _Conn(rows=[])
    assert get_currency(conn, 'ZZZ') is None


# ── upsert_currency ──────────────────────────────────────────────────────────

def test_upsert_currency_non_base_skips_reset_step():
    conn = _Conn(rows=[])
    upsert_currency(conn, 'EUR', 'Euro', '€', 1.09, is_base=False, is_active=True)
    assert len(conn.calls) == 1
    assert "INSERT INTO currency" in conn.last_sql
    assert conn.last_params[:6] == ['EUR', 'Euro', '€', 1.09, False, True]


def test_upsert_currency_base_resets_other_bases_first():
    conn = _Conn(rows=[])
    upsert_currency(conn, 'USD', 'US Dollar', '$', 1.0, is_base=True)
    assert len(conn.calls) == 2
    assert conn.calls[0][0] == "UPDATE currency SET is_base = FALSE"
    assert conn.calls[0][1] == []
    assert "INSERT INTO currency" in conn.calls[1][0]
    assert conn.calls[1][1][:6] == ['USD', 'US Dollar', '$', 1.0, True, True]


def test_upsert_currency_coerces_exchange_rate_to_float():
    conn = _Conn(rows=[])
    upsert_currency(conn, 'JPY', 'Japanese Yen', '¥', '0.0066', is_base=False)
    assert conn.last_params[3] == 0.0066
    assert isinstance(conn.last_params[3], float)


# ── get_base_currency ────────────────────────────────────────────────────────

def test_get_base_currency_found():
    row = {'code': 'EUR', 'symbol': '€', 'exchange_rate': 1.09, 'is_base': True}
    conn = _Conn(rows=[row])
    assert get_base_currency(conn) == row


def test_get_base_currency_defaults_to_usd_when_none_set():
    conn = _Conn(rows=[])
    assert get_base_currency(conn) == {
        'code': 'USD', 'symbol': '$', 'exchange_rate': 1.0,
    }


# ── convert_to_base ──────────────────────────────────────────────────────────

def test_convert_to_base_multiplies_and_rounds():
    assert convert_to_base(100, 1.09) == 109.0


def test_convert_to_base_rounds_to_two_decimals():
    assert convert_to_base(33.333, 3) == 100.0


def test_convert_to_base_zero_rate_returns_amount_unchanged():
    assert convert_to_base(150, 0) == 150


def test_convert_to_base_none_rate_returns_amount_unchanged():
    assert convert_to_base(150, None) == 150


# ── get_currency_symbol ──────────────────────────────────────────────────────

def test_get_currency_symbol_found():
    conn = _Conn(rows=[{'symbol': '£'}])
    assert get_currency_symbol(conn, 'GBP') == '£'


def test_get_currency_symbol_not_found_falls_back_to_code():
    conn = _Conn(rows=[])
    assert get_currency_symbol(conn, 'ZZZ') == 'ZZZ'
