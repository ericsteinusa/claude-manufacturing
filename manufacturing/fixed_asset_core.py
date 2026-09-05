"""
Fixed Asset Management (non-IT assets: equipment, vehicles, buildings, etc.)
Tables: fixed_asset, fixed_asset_event
"""
from __future__ import annotations
from datetime import date as _date

FIXED_ASSET_TYPES = (
    'Equipment', 'Vehicle', 'Building', 'Land',
    'Machinery', 'Furniture & Fixtures', 'Computer Equipment',
    'Leasehold Improvement', 'Other',
)

FIXED_ASSET_STATUSES = ('Active', 'Inactive', 'Disposed', 'Under Repair', 'Sold')

DEPRECIATION_METHODS = ('Straight-Line', 'Declining Balance', 'None')


def init_fixed_asset_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fixed_asset (
            id                   SERIAL PRIMARY KEY,
            asset_number         TEXT NOT NULL UNIQUE,
            asset_name           TEXT NOT NULL,
            asset_type           TEXT DEFAULT 'Equipment',
            category             TEXT DEFAULT '',
            location             TEXT DEFAULT '',
            department           TEXT DEFAULT '',
            vendor               TEXT DEFAULT '',
            purchase_date        TEXT DEFAULT '',
            purchase_price       REAL DEFAULT 0,
            salvage_value        REAL DEFAULT 0,
            useful_life_years    INTEGER DEFAULT 5,
            depreciation_method  TEXT DEFAULT 'Straight-Line',
            status               TEXT DEFAULT 'Active',
            serial_number        TEXT DEFAULT '',
            notes                TEXT DEFAULT '',
            created_by           TEXT DEFAULT '',
            created_date         TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fixed_asset_event (
            id          SERIAL PRIMARY KEY,
            asset_id    INTEGER NOT NULL REFERENCES fixed_asset(id),
            event_type  TEXT DEFAULT '',
            description TEXT DEFAULT '',
            changed_by  TEXT DEFAULT '',
            changed_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    # Add optional columns if they don't exist yet
    for _col in [
        "ALTER TABLE fixed_asset ADD COLUMN IF NOT EXISTS cost_center TEXT DEFAULT ''",
        "ALTER TABLE fixed_asset ADD COLUMN IF NOT EXISTS assigned_to TEXT DEFAULT ''",
        "ALTER TABLE fixed_asset ADD COLUMN IF NOT EXISTS in_service_date TEXT DEFAULT ''",
    ]:
        conn.execute(_col)
    # Extend it_asset with cost/depreciation fields
    _extend_it_asset(conn)


def _extend_it_asset(conn) -> None:
    for col_sql in [
        "ALTER TABLE it_asset ADD COLUMN IF NOT EXISTS purchase_price REAL DEFAULT 0",
        "ALTER TABLE it_asset ADD COLUMN IF NOT EXISTS salvage_value REAL DEFAULT 0",
        "ALTER TABLE it_asset ADD COLUMN IF NOT EXISTS useful_life_years INTEGER DEFAULT 5",
        "ALTER TABLE it_asset ADD COLUMN IF NOT EXISTS depreciation_method TEXT DEFAULT 'Straight-Line'",
        "ALTER TABLE it_asset ADD COLUMN IF NOT EXISTS vendor TEXT DEFAULT ''",
        "ALTER TABLE it_asset ADD COLUMN IF NOT EXISTS location TEXT DEFAULT ''",
        "ALTER TABLE it_asset ADD COLUMN IF NOT EXISTS cost_center TEXT DEFAULT ''",
    ]:
        conn.execute(col_sql)


def next_asset_number(conn) -> str:
    year = _date.today().year
    prefix = f"FA-{year}-"
    rows = conn.execute(
        "SELECT asset_number FROM fixed_asset WHERE asset_number LIKE %s",
        (prefix + "%",)
    ).fetchall()
    nums = []
    for r in rows:
        try:
            nums.append(int(r['asset_number'][len(prefix):]))
        except (ValueError, TypeError):
            pass
    n = max(nums) + 1 if nums else 1
    return f"{prefix}{n:04d}"


def list_fixed_assets(conn, status=None, asset_type=None, search=None) -> list:
    sql = (
        "SELECT id, asset_number, asset_name, asset_type, location, department, "
        "vendor, purchase_date, in_service_date, purchase_price, salvage_value, useful_life_years, "
        "depreciation_method, status "
        "FROM fixed_asset WHERE TRUE"
    )
    params: list = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if asset_type:
        sql += " AND asset_type = %s"
        params.append(asset_type)
    if search:
        sql += " AND (asset_name ILIKE %s OR asset_number ILIKE %s OR vendor ILIKE %s)"
        params.extend([f"%{search}%"] * 3)
    sql += " ORDER BY asset_number"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        r['book_value'] = calc_book_value(r)
        r['annual_depreciation'] = calc_annual_depreciation(r)
    return rows


def get_fixed_asset(conn, asset_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM fixed_asset WHERE id = %s", [asset_id]
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d['book_value'] = calc_book_value(d)
    d['annual_depreciation'] = calc_annual_depreciation(d)
    d['accumulated_depreciation'] = calc_accumulated_depreciation(d)
    return d


def create_fixed_asset(conn, asset_number: str, asset_name: str, asset_type: str,
                        category: str, location: str, department: str, vendor: str,
                        purchase_date: str, purchase_price: float, salvage_value: float,
                        useful_life_years: int, depreciation_method: str,
                        status: str, serial_number: str, notes: str,
                        created_by: str, in_service_date: str = '') -> int:
    row = conn.execute("""
        INSERT INTO fixed_asset
            (asset_number, asset_name, asset_type, category, location, department,
             vendor, purchase_date, purchase_price, salvage_value, useful_life_years,
             depreciation_method, status, serial_number, notes, created_by, created_date,
             in_service_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (asset_number, asset_name, asset_type, category, location, department,
          vendor, purchase_date, float(purchase_price or 0), float(salvage_value or 0),
          int(useful_life_years or 5), depreciation_method, status or 'Active',
          serial_number, notes, created_by, str(_date.today()),
          in_service_date or None)).fetchone()
    return row['id']


def update_fixed_asset(conn, asset_id: int, **fields) -> None:
    allowed = {
        'asset_name', 'asset_type', 'category', 'location', 'department',
        'vendor', 'purchase_date', 'purchase_price', 'salvage_value',
        'useful_life_years', 'depreciation_method', 'status', 'serial_number', 'notes',
        'cost_center', 'assigned_to', 'in_service_date',
    }
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE fixed_asset SET {set_clause} WHERE id = %s",
        list(cols.values()) + [asset_id],
    )


def log_fixed_asset_event(conn, asset_id: int, event_type: str,
                           description: str, changed_by: str) -> None:
    conn.execute(
        "INSERT INTO fixed_asset_event (asset_id, event_type, description, changed_by) "
        "VALUES (%s,%s,%s,%s)",
        (asset_id, event_type, description, changed_by),
    )


def list_fixed_asset_events(conn, asset_id: int) -> list:
    rows = conn.execute(
        "SELECT id, event_type, description, changed_by, changed_at "
        "FROM fixed_asset_event WHERE asset_id = %s ORDER BY changed_at DESC",
        [asset_id]
    ).fetchall()
    return [dict(r) for r in rows]


# ── Depreciation calculations ─────────────────────────────────────────────────

def calc_annual_depreciation(asset: dict) -> float:
    method = (asset.get('depreciation_method') or '').lower()
    price = float(asset.get('purchase_price') or 0)
    salvage = float(asset.get('salvage_value') or 0)
    life = int(asset.get('useful_life_years') or 5) or 5
    if method == 'none' or price == 0:
        return 0.0
    if 'straight' in method:
        return round((price - salvage) / life, 2)
    if 'declining' in method:
        rate = 2.0 / life  # double-declining
        return round(price * rate, 2)
    return round((price - salvage) / life, 2)


def calc_accumulated_depreciation(asset: dict) -> float:
    purchase_date = asset.get('purchase_date') or ''
    if not purchase_date:
        return 0.0
    try:
        p_date = _date.fromisoformat(str(purchase_date)[:10])
        years_owned = max(0.0, (_date.today() - p_date).days / 365.25)
    except (ValueError, TypeError):
        return 0.0
    annual = calc_annual_depreciation(asset)
    price = float(asset.get('purchase_price') or 0)
    salvage = float(asset.get('salvage_value') or 0)
    total = min(annual * years_owned, price - salvage)
    return round(total, 2)


def calc_book_value(asset: dict) -> float:
    price = float(asset.get('purchase_price') or 0)
    acc = calc_accumulated_depreciation(asset)
    return round(max(float(asset.get('salvage_value') or 0), price - acc), 2)


def get_fixed_asset_summary(conn) -> dict:
    """KPI summary for the fixed asset dashboard."""
    try:
        rows = conn.execute(
            "SELECT id, purchase_price, salvage_value, useful_life_years, "
            "depreciation_method, purchase_date, status FROM fixed_asset"
        ).fetchall()
    except Exception:
        return {}
    assets = [dict(r) for r in rows]
    total_cost = sum(float(a.get('purchase_price') or 0) for a in assets)
    total_book = sum(calc_book_value(a) for a in assets)
    total_depreciation = sum(calc_accumulated_depreciation(a) for a in assets)
    total_annual_dep = sum(calc_annual_depreciation(a) for a in assets)
    active = sum(1 for a in assets if a.get('status') == 'Active')
    return {
        'count': len(assets),
        'active': active,
        'total_cost': round(total_cost, 2),
        'total_book_value': round(total_book, 2),
        'total_accumulated_depreciation': round(total_depreciation, 2),
        'total_annual_dep': round(total_annual_dep, 2),
    }
