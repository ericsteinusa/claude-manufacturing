"""recipe_core.py — Qt-free Recipe / Formula Management (process
manufacturing), 7/10 of the top-10 ERPs have it.

The existing `bom` table models a fixed, per-unit component structure —
"1 unit of the parent needs N units of this component" — which is exactly
right for discrete assembly but wrong for process/formula manufacturing,
where a recipe is defined per **batch** (e.g. "this 500 kg batch of syrup
needs 320 kg sugar + 180 kg water") and scaling to a different batch size
isn't a straight qty-per-unit multiply: a process typically loses some
output to yield loss, so scaling *up* the target output requires scaling
the *inputs* by more than the naive ratio. This is a genuinely different
computation from `bom_core.explode_quantity`, so recipes are deliberately
a **parallel structure to BOM, not a replacement or a fork of it** — the
same "parallel, not merged" scoping already used for FIFO/LIFO cost layers
next to standard costing and ABC costing next to the flat overhead rate.

A recipe has a lifecycle mirroring `document_control_core`'s single-
active-revision pattern: draft -> active -> superseded. Activating a new
recipe for a product automatically supersedes whichever one was active
before, so exactly one recipe per product is ever "active" at a time —
the one `release_batch_wo` and `scale_recipe` actually use.

Every function takes an open connection; the caller owns the transaction
(same convention as skills_matrix_core / fmea_core).
"""

from __future__ import annotations

from .work_orders_core import ensure_wo_tables, create_wo, add_wo_material

RECIPE_STATUSES = ('draft', 'active', 'superseded')


def ensure_recipe_tables(conn):
    """Create recipe / recipe_ingredient if absent. Idempotent — does not
    commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recipe (
            id           SERIAL PRIMARY KEY,
            product_id   INTEGER NOT NULL REFERENCES product(id),
            name         TEXT NOT NULL,
            revision     TEXT NOT NULL DEFAULT 'A',
            batch_size   REAL NOT NULL DEFAULT 1.0,
            batch_uom    TEXT NOT NULL DEFAULT 'kg',
            yield_pct    REAL NOT NULL DEFAULT 100.0,
            status       TEXT NOT NULL DEFAULT 'draft',
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recipe_ingredient (
            id             SERIAL PRIMARY KEY,
            recipe_id      INTEGER NOT NULL REFERENCES recipe(id),
            component_id   INTEGER NOT NULL REFERENCES product(id),
            qty_per_batch  REAL NOT NULL DEFAULT 0.0,
            uom            TEXT NOT NULL DEFAULT 'kg',
            sequence       INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS recipe_ingredient_recipe "
        "ON recipe_ingredient(recipe_id)"
    )


# ---------------------------------------------------------------------------
# Recipe CRUD / lifecycle
# ---------------------------------------------------------------------------

def list_recipes(conn, product_id=None, status=None):
    sql = (
        "SELECT r.*, p.name AS product_name FROM recipe r "
        "JOIN product p ON p.id = r.product_id WHERE TRUE"
    )
    params: list = []
    if product_id:
        sql += " AND r.product_id = %s"
        params.append(product_id)
    if status:
        sql += " AND r.status = %s"
        params.append(status)
    sql += " ORDER BY r.id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_recipe(conn, recipe_id):
    row = conn.execute(
        "SELECT r.*, p.name AS product_name FROM recipe r "
        "JOIN product p ON p.id = r.product_id WHERE r.id = %s",
        (recipe_id,),
    ).fetchone()
    if not row:
        return None
    recipe = dict(row)
    recipe['ingredients'] = list_ingredients(conn, recipe_id)
    return recipe


def get_active_recipe(conn, product_id):
    row = conn.execute(
        "SELECT id FROM recipe WHERE product_id = %s AND status = 'active'",
        (product_id,),
    ).fetchone()
    return get_recipe(conn, row['id']) if row else None


def create_recipe(conn, product_id, name, batch_size, batch_uom='kg',
                  yield_pct=100.0, revision='A', created_by=''):
    if not name or not name.strip():
        raise ValueError('name is required')
    if batch_size is None or float(batch_size) <= 0:
        raise ValueError('batch_size must be greater than zero')
    yield_pct = float(yield_pct if yield_pct is not None else 100.0)
    if not (0 < yield_pct <= 100):
        raise ValueError('yield_pct must be between 0 (exclusive) and 100')
    row = conn.execute(
        "INSERT INTO recipe (product_id, name, revision, batch_size, batch_uom, "
        "yield_pct, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (product_id, name.strip(), revision or 'A', float(batch_size),
         batch_uom or 'kg', yield_pct, created_by or ''),
    ).fetchone()
    return row['id']


def list_ingredients(conn, recipe_id):
    rows = conn.execute(
        "SELECT ri.*, p.name AS component_name FROM recipe_ingredient ri "
        "JOIN product p ON p.id = ri.component_id "
        "WHERE ri.recipe_id = %s ORDER BY ri.sequence, ri.id",
        (recipe_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_ingredient(conn, recipe_id, component_id, qty_per_batch, uom='kg', sequence=0):
    if qty_per_batch is None or float(qty_per_batch) <= 0:
        raise ValueError('qty_per_batch must be greater than zero')
    row = conn.execute(
        "INSERT INTO recipe_ingredient (recipe_id, component_id, qty_per_batch, uom, sequence) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (recipe_id, component_id, float(qty_per_batch), uom or 'kg', int(sequence or 0)),
    ).fetchone()
    return row['id']


def remove_ingredient(conn, ingredient_id):
    conn.execute("DELETE FROM recipe_ingredient WHERE id = %s", (ingredient_id,))


def activate_recipe(conn, recipe_id):
    """Mark this recipe active, superseding whichever recipe was
    previously active for the same product. Raises if the recipe has no
    ingredients yet — an empty recipe can't actually be released."""
    recipe = get_recipe(conn, recipe_id)
    if not recipe:
        raise ValueError(f'No recipe with id {recipe_id}')
    if not recipe['ingredients']:
        raise ValueError('Cannot activate a recipe with no ingredients.')
    conn.execute(
        "UPDATE recipe SET status = 'superseded' "
        "WHERE product_id = %s AND status = 'active' AND id != %s",
        (recipe['product_id'], recipe_id),
    )
    conn.execute("UPDATE recipe SET status = 'active' WHERE id = %s", (recipe_id,))


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------

def scale_recipe(conn, recipe_id, target_qty):
    """Scale every ingredient's qty_per_batch to produce ``target_qty``
    units of finished output, accounting for yield loss: at yield_pct < 100,
    more input is required than a naive (target_qty / batch_size) ratio
    would suggest, since some of what goes in doesn't come out as good
    output. Returns a flat list of {component_id, component_name,
    qty_needed, uom}."""
    recipe = get_recipe(conn, recipe_id)
    if not recipe:
        raise ValueError(f'No recipe with id {recipe_id}')
    if target_qty is None or float(target_qty) <= 0:
        raise ValueError('target_qty must be greater than zero')

    yield_fraction = recipe['yield_pct'] / 100.0
    # Batches needed to yield target_qty good output, given yield loss.
    batches_needed = float(target_qty) / (recipe['batch_size'] * yield_fraction)

    return [
        {
            'component_id': ing['component_id'],
            'component_name': ing['component_name'],
            'qty_needed': round(ing['qty_per_batch'] * batches_needed, 4),
            'uom': ing['uom'],
        }
        for ing in recipe['ingredients']
    ]


def release_batch_wo(conn, recipe_id, wo_number, target_qty, start_date=None,
                     due_date=None, created_by=''):
    """Create a real Work Order for a batch release, with wo_material
    populated from the recipe scaled to target_qty. Returns the new WO id."""
    recipe = get_recipe(conn, recipe_id)
    if not recipe:
        raise ValueError(f'No recipe with id {recipe_id}')
    if recipe['status'] != 'active':
        raise ValueError("Can only release a batch from an 'active' recipe "
                         f"(current status: {recipe['status']!r})")

    scaled = scale_recipe(conn, recipe_id, target_qty)
    ensure_wo_tables(conn)
    wo_id = create_wo(
        conn, wo_number, product_id=recipe['product_id'],
        description=f"Batch release: {recipe['name']} (Rev {recipe['revision']})",
        quantity=max(1, round(target_qty)), start_date=start_date, due_date=due_date,
        status='draft', notes=f"Released from recipe #{recipe_id}, scaled to {target_qty} "
                              f"{recipe['batch_uom']}", created_by=created_by,
    )
    for ing in scaled:
        add_wo_material(
            conn, wo_id, ing['component_id'], qty_required=ing['qty_needed'],
            notes=f"Recipe {recipe['name']} Rev {recipe['revision']}",
        )
    return wo_id
