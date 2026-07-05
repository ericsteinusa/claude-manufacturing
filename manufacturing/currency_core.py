"""
Multi-currency support.
Tables: currency
Adds currency/exchange_rate columns to purchase_order, sales_order,
ap_invoice, ar_invoice via ALTER TABLE IF NOT EXISTS (idempotent).
"""
from __future__ import annotations

COMMON_CURRENCIES = [
    # (code, name, symbol, default_rate_to_USD)
    ('USD', 'US Dollar',        '$',   1.0),
    ('EUR', 'Euro',             '€',   1.09),
    ('GBP', 'British Pound',    '£',   1.27),
    ('CAD', 'Canadian Dollar',  'C$',  0.73),
    ('MXN', 'Mexican Peso',     'MX$', 0.058),
    ('JPY', 'Japanese Yen',     '¥',   0.0066),
    ('CNY', 'Chinese Yuan',     '¥',   0.138),
    ('AUD', 'Australian Dollar','A$',  0.65),
    ('CHF', 'Swiss Franc',      'CHF', 1.12),
    ('INR', 'Indian Rupee',     '₹',  0.012),
    ('BRL', 'Brazilian Real',   'R$',  0.20),
    ('SGD', 'Singapore Dollar', 'S$',  0.74),
]


def init_currency_schema(conn) -> None:
    """Create currency table and add currency columns to financial tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS currency (
            id            SERIAL PRIMARY KEY,
            code          TEXT NOT NULL UNIQUE,
            name          TEXT NOT NULL,
            symbol        TEXT DEFAULT '$',
            exchange_rate REAL DEFAULT 1.0,
            is_base       BOOLEAN DEFAULT FALSE,
            is_active     BOOLEAN DEFAULT TRUE,
            updated_at    TEXT DEFAULT ''
        )
    """)
    # Seed USD as base if empty
    row = conn.execute("SELECT COUNT(*) FROM currency").fetchone()
    if row[0] == 0:
        for code, name, symbol, rate in COMMON_CURRENCIES:
            conn.execute(
                "INSERT INTO currency (code, name, symbol, exchange_rate, is_base) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                (code, name, symbol, rate, code == 'USD'),
            )
    # Add currency columns to financial tables (idempotent)
    _add_currency_cols(conn, 'purchase_order')
    _add_currency_cols(conn, 'sales_order')
    _add_currency_cols(conn, 'ap_invoice')
    _add_currency_cols(conn, 'ar_invoice')


def _add_currency_cols(conn, table: str) -> None:
    conn.execute(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'USD'"
    )
    conn.execute(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS exchange_rate REAL DEFAULT 1.0"
    )


def list_currencies(conn, active_only: bool = False) -> list:
    sql = "SELECT id, code, name, symbol, exchange_rate, is_base, is_active, updated_at FROM currency"
    if active_only:
        sql += " WHERE is_active = TRUE"
    sql += " ORDER BY is_base DESC, code"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_currency(conn, code: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM currency WHERE code = %s", [code]
    ).fetchone()
    return dict(row) if row else None


def upsert_currency(conn, code: str, name: str, symbol: str,
                    exchange_rate: float, is_base: bool = False,
                    is_active: bool = True) -> None:
    from datetime import date
    if is_base:
        conn.execute("UPDATE currency SET is_base = FALSE")
    conn.execute("""
        INSERT INTO currency (code, name, symbol, exchange_rate, is_base, is_active, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (code) DO UPDATE SET
            name=EXCLUDED.name, symbol=EXCLUDED.symbol,
            exchange_rate=EXCLUDED.exchange_rate, is_base=EXCLUDED.is_base,
            is_active=EXCLUDED.is_active, updated_at=EXCLUDED.updated_at
    """, (code, name, symbol, float(exchange_rate), is_base, is_active,
          str(date.today())))


def get_base_currency(conn) -> dict:
    row = conn.execute(
        "SELECT * FROM currency WHERE is_base = TRUE LIMIT 1"
    ).fetchone()
    if row:
        return dict(row)
    return {'code': 'USD', 'symbol': '$', 'exchange_rate': 1.0}


def convert_to_base(amount: float, exchange_rate: float) -> float:
    """Convert a foreign-currency amount to base currency."""
    if not exchange_rate or exchange_rate == 0:
        return amount
    return round(amount * exchange_rate, 2)


def get_currency_symbol(conn, code: str) -> str:
    row = conn.execute(
        "SELECT symbol FROM currency WHERE code = %s", [code]
    ).fetchone()
    return row['symbol'] if row else code
