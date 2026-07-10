"""cto_core.py — Qt-free Configure-to-Order (CTO), 7/10 of the top-10
ERPs have it.

A configurable product defines **option groups** (e.g. "Frame Color",
"Wheel Size") each holding mutually-exclusive **options**, and each option
maps to one BOM-component substitution (e.g. "Red" -> component #42,
"Blue" -> component #43). A **configuration** is one customer's actual
selections for a specific SO line — one option chosen per group.

``generate_configured_bom`` resolves a configuration into a flat component
list: every base BOM line for the product *except* the ones being replaced
by a selected option's component, plus the selected options' own
components. There's no separate "configurable BOM" table — the base
`bom` table (via ``bom_web_core.get_bom``) stays the single source of
truth for the product's fixed structure; only the option-covered slots are
swapped in the resolved list.

There is no SO-to-WO conversion path anywhere else in this app — production
is planned from aggregate SO demand via MRP (``mrp_web_core``), not by
converting one SO line into its own WO. ``release_configured_wo`` fills
that gap for the CTO case specifically: build-to-order products where the
whole point is that this one order's WO needs *this* customer's exact
configuration, not a generic MRP-planned run. It reuses
``work_orders_core.create_wo`` and ``bom_core.explode_quantity`` — no
forked WO-creation logic.

Every function takes an open connection; the caller owns the transaction
(same convention as skills_matrix_core / fmea_core).
"""

from __future__ import annotations

from .bom_core import explode_quantity
from .bom_web_core import get_bom
from .work_orders_core import ensure_wo_tables, create_wo, add_wo_material


def ensure_cto_tables(conn):
    """Create the four CTO tables if absent. Idempotent — does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cto_option_group (
            id          SERIAL PRIMARY KEY,
            product_id  INTEGER NOT NULL REFERENCES product(id),
            name        TEXT NOT NULL,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            created_by  TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cto_option (
            id            SERIAL PRIMARY KEY,
            group_id      INTEGER NOT NULL REFERENCES cto_option_group(id),
            name          TEXT NOT NULL,
            component_id  INTEGER NOT NULL REFERENCES product(id),
            qty_required  REAL NOT NULL DEFAULT 1.0,
            sort_order    INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cto_configuration (
            id           SERIAL PRIMARY KEY,
            so_item_id   INTEGER NOT NULL UNIQUE,
            product_id   INTEGER NOT NULL REFERENCES product(id),
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cto_configuration_selection (
            id                SERIAL PRIMARY KEY,
            configuration_id  INTEGER NOT NULL REFERENCES cto_configuration(id),
            group_id          INTEGER NOT NULL REFERENCES cto_option_group(id),
            option_id         INTEGER NOT NULL REFERENCES cto_option(id),
            UNIQUE (configuration_id, group_id)
        )
    """)


# ---------------------------------------------------------------------------
# Option groups / options (product-level setup)
# ---------------------------------------------------------------------------

def create_option_group(conn, product_id, name, sort_order=0, created_by=''):
    if not name or not name.strip():
        raise ValueError('name is required')
    row = conn.execute(
        "INSERT INTO cto_option_group (product_id, name, sort_order, created_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (product_id, name.strip(), int(sort_order or 0), created_by or ''),
    ).fetchone()
    return row['id']


def add_option(conn, group_id, name, component_id, qty_required=1.0, sort_order=0):
    if not name or not name.strip():
        raise ValueError('name is required')
    row = conn.execute(
        "INSERT INTO cto_option (group_id, name, component_id, qty_required, sort_order) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (group_id, name.strip(), component_id, float(qty_required or 1.0),
         int(sort_order or 0)),
    ).fetchone()
    return row['id']


def list_option_groups(conn, product_id):
    """Option groups for a product, each with its own nested 'options' list."""
    groups = [dict(r) for r in conn.execute(
        "SELECT * FROM cto_option_group WHERE product_id = %s "
        "ORDER BY sort_order, id",
        (product_id,),
    ).fetchall()]
    for group in groups:
        group['options'] = [dict(r) for r in conn.execute(
            "SELECT o.*, p.name AS component_name FROM cto_option o "
            "JOIN product p ON p.id = o.component_id "
            "WHERE o.group_id = %s ORDER BY o.sort_order, o.id",
            (group['id'],),
        ).fetchall()]
    return groups


def is_configurable(conn, product_id) -> bool:
    row = conn.execute(
        "SELECT id FROM cto_option_group WHERE product_id = %s LIMIT 1",
        (product_id,),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Per-order configuration
# ---------------------------------------------------------------------------

def get_configuration(conn, so_item_id):
    row = conn.execute(
        "SELECT * FROM cto_configuration WHERE so_item_id = %s", (so_item_id,)
    ).fetchone()
    if not row:
        return None
    config = dict(row)
    config['selections'] = [dict(r) for r in conn.execute(
        "SELECT s.*, g.name AS group_name, o.name AS option_name, "
        "o.component_id, o.qty_required "
        "FROM cto_configuration_selection s "
        "JOIN cto_option_group g ON g.id = s.group_id "
        "JOIN cto_option o ON o.id = s.option_id "
        "WHERE s.configuration_id = %s ORDER BY g.sort_order",
        (config['id'],),
    ).fetchall()]
    return config


def create_configuration(conn, so_item_id, product_id, created_by=''):
    """Create (or return the existing) configuration for an SO line.
    Idempotent on so_item_id — a line can only be configured once."""
    existing = get_configuration(conn, so_item_id)
    if existing:
        return existing['id']
    row = conn.execute(
        "INSERT INTO cto_configuration (so_item_id, product_id, created_by) "
        "VALUES (%s,%s,%s) RETURNING id",
        (so_item_id, product_id, created_by or ''),
    ).fetchone()
    return row['id']


def set_selection(conn, configuration_id, group_id, option_id):
    """Upsert this configuration's choice for one option group. Raises if
    the option doesn't actually belong to the given group."""
    option = conn.execute(
        "SELECT id FROM cto_option WHERE id = %s AND group_id = %s",
        (option_id, group_id),
    ).fetchone()
    if not option:
        raise ValueError('That option does not belong to this option group.')
    conn.execute(
        "INSERT INTO cto_configuration_selection (configuration_id, group_id, option_id) "
        "VALUES (%s,%s,%s) "
        "ON CONFLICT (configuration_id, group_id) "
        "DO UPDATE SET option_id = EXCLUDED.option_id",
        (configuration_id, group_id, option_id),
    )


def is_configuration_complete(conn, configuration_id, product_id) -> bool:
    """True once a selection exists for every option group on the product."""
    groups = list_option_groups(conn, product_id)
    if not groups:
        return True
    selected = conn.execute(
        "SELECT group_id FROM cto_configuration_selection WHERE configuration_id = %s",
        (configuration_id,),
    ).fetchall()
    selected_ids = {r['group_id'] for r in selected}
    return all(g['id'] in selected_ids for g in groups)


# ---------------------------------------------------------------------------
# Resolve -> configured BOM -> release WO
# ---------------------------------------------------------------------------

def generate_configured_bom(conn, so_item_id):
    """Resolve one SO line's configuration into a flat component list:
    every base BOM line except the ones covered by an option group, plus
    the selected options' own components. Raises if the line has never
    been configured."""
    config = get_configuration(conn, so_item_id)
    if not config:
        raise ValueError('This SO line has not been configured yet.')

    groups = list_option_groups(conn, config['product_id'])
    slot_component_ids = {
        opt['component_id'] for group in groups for opt in group['options']
    }

    base = get_bom(conn, config['product_id'])
    resolved = [
        {
            'component_id': line['component_id'],
            'component_name': line['component_name'],
            'qty_required': line['qty_required'],
            'scrap_pct': line['scrap_pct'],
            'source': 'base',
        }
        for line in base
        if line['component_id'] not in slot_component_ids
    ]
    for sel in config['selections']:
        resolved.append({
            'component_id': sel['component_id'],
            'component_name': None,
            'qty_required': sel['qty_required'],
            'scrap_pct': 0.0,
            'source': f"option: {sel['group_name']} = {sel['option_name']}",
        })
    return resolved


def release_configured_wo(conn, so_item_id, wo_number, quantity, start_date=None,
                          due_date=None, created_by=''):
    """Create a real Work Order for a configured SO line, with wo_material
    populated from that line's resolved configured BOM (scaled by
    quantity) instead of the product's generic BOM. Returns the new WO id."""
    config = get_configuration(conn, so_item_id)
    if not config:
        raise ValueError('This SO line has not been configured yet.')
    if not is_configuration_complete(conn, config['id'], config['product_id']):
        raise ValueError('This configuration is missing a selection for one or more option groups.')

    ensure_wo_tables(conn)
    resolved = generate_configured_bom(conn, so_item_id)
    wo_id = create_wo(
        conn, wo_number, product_id=config['product_id'],
        description='Configure-to-Order release', quantity=max(1, round(quantity)),
        start_date=start_date, due_date=due_date, status='draft',
        notes=f'Released from CTO configuration #{config["id"]}',
        created_by=created_by,
    )
    for line in resolved:
        qty = explode_quantity(line['qty_required'], quantity, line['scrap_pct'])
        add_wo_material(
            conn, wo_id, line['component_id'], qty_required=qty,
            notes=line['source'],
        )
    return wo_id
