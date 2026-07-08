"""
ecommerce_core.py — Qt-free e-Commerce Integration (P4-E).

Real inbound webhook handling for Shopify/WooCommerce "new order" events:
HMAC-SHA256 signature verification (both platforms sign identically —
``base64(HMAC-SHA256(secret, raw_body))``), JSON payload parsing for the
common subset of both platforms' near-identical order shape, and
idempotent Sales Order creation. This is genuine security/parsing logic,
not a stub.

What's honestly out of scope is a **live storefront to push to** — there
is no real Shopify/WooCommerce store reachable from this environment.
Outbound sync (inventory level, price, shipment confirmation) is real,
config-gated HTTP POST code (stdlib ``urllib.request`` — no new
dependency; ``requests`` is importable in this env but not listed in
``requirements.txt``): if a connection has a ``sync_endpoint_url``
configured it is actually called, and success/failure is logged; if not,
the attempt is logged as ``queued`` rather than faked as a success. This
mirrors the existing precedent in
``management/commands/send_daily_digest.py``, which emails only
``if EMAIL_HOST:`` is configured and otherwise prints.

"Push on every transaction" (per the roadmap bullet) is implemented as
on-demand sync actions plus a schedulable batch command
(``manage.py sync_ecommerce``), not intrusive hooks into every
inventory-mutating call site — ``product``'s ``CREATE TABLE`` is
duplicated across 5+ modules with no single centralized "inventory
changed" call site to hook non-invasively.

``product`` has no SKU/code column anywhere in this codebase — only a
free-text ``name``. A storefront's line item carries *its own* SKU, so a
per-connection item cross-reference table (``storefront_item_xref``) is
the actual field-mapping mechanism, exactly as ``edi_partner_item_xref``
is for EDI (P4-D). An inbound line with no mapping still becomes a valid
``so_item`` (``product_id=None``, using the storefront's raw item name) —
mirrors how ``so_item`` already supports text-only/service lines.

Price push reads from this codebase's existing tiered pricing
(``price_list_core.get_price_for_product``) rather than
``product.purchase_price`` (which is cost, not a sell price).

Reuses existing, unmodified functions for all real side effects:
``sales_orders_core.next_so_number``/``create_so``/``add_so_item``
(inbound order webhook), ``production_core.get_shipment`` (outbound
shipment push), ``price_list_core.get_price_for_product`` (outbound price
push). Every function taking ``conn`` takes an open connection; the
caller owns the transaction.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from .log_utils import get_logger
from .sales_orders_core import next_so_number, create_so, add_so_item
from .production_core import get_shipment
from .price_list_core import get_price_for_product

log = get_logger(__name__)

PLATFORMS = ('shopify', 'woocommerce')


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def ensure_ecommerce_tables(conn) -> None:
    """Create ecommerce_*/storefront_* tables if absent. Does not commit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS storefront_connection (
            id                     SERIAL PRIMARY KEY,
            platform               TEXT NOT NULL,
            store_name             TEXT NOT NULL,
            webhook_secret         TEXT DEFAULT '',
            default_customer_id    INTEGER,
            default_price_list_id  INTEGER,
            sync_endpoint_url      TEXT DEFAULT '',
            is_active              BOOLEAN NOT NULL DEFAULT TRUE,
            created_at             TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS storefront_item_xref (
            id             SERIAL PRIMARY KEY,
            connection_id  INTEGER NOT NULL,
            external_sku   TEXT NOT NULL,
            product_id     INTEGER NOT NULL,
            UNIQUE (connection_id, external_sku)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ecommerce_order_log (
            id                 SERIAL PRIMARY KEY,
            connection_id      INTEGER NOT NULL,
            external_order_id  TEXT NOT NULL,
            so_id              INTEGER,
            created_at         TEXT DEFAULT '',
            UNIQUE (connection_id, external_order_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ecommerce_sync_log (
            id             SERIAL PRIMARY KEY,
            connection_id  INTEGER,
            event_type     TEXT NOT NULL,
            direction      TEXT NOT NULL,
            product_id     INTEGER,
            so_id          INTEGER,
            shipment_id    INTEGER,
            payload        TEXT DEFAULT '',
            status         TEXT NOT NULL,
            detail         TEXT DEFAULT '',
            created_at     TEXT DEFAULT '',
            created_by     TEXT DEFAULT ''
        )
    """)


# ---------------------------------------------------------------------------
# Storefront connection CRUD
# ---------------------------------------------------------------------------

def create_connection(conn, platform: str, store_name: str, webhook_secret: str,
                       default_customer_id=None, default_price_list_id=None,
                       sync_endpoint_url: str = '') -> int:
    if platform not in PLATFORMS:
        raise ValueError(f"platform must be one of {PLATFORMS}.")
    if not store_name:
        raise ValueError("Store name is required.")
    row = conn.execute(
        "INSERT INTO storefront_connection "
        "(platform, store_name, webhook_secret, default_customer_id, "
        "default_price_list_id, sync_endpoint_url, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (platform, store_name, webhook_secret or '', default_customer_id,
         default_price_list_id, sync_endpoint_url or '', datetime.now().isoformat()),
    ).fetchone()
    return row['id']


def update_connection(conn, connection_id: int, **fields) -> None:
    allowed = {'store_name', 'webhook_secret', 'default_customer_id',
               'default_price_list_id', 'sync_endpoint_url', 'is_active'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE storefront_connection SET {set_clause} WHERE id = %s",
        (*cols.values(), connection_id),
    )


def get_connection(conn, connection_id: int) -> dict | None:
    row = conn.execute("""
        SELECT sc.*, c.company_name, c.first_name, c.last_name,
               pl.name AS price_list_name
        FROM storefront_connection sc
        LEFT JOIN customer c ON c.id = sc.default_customer_id
        LEFT JOIN price_list pl ON pl.id = sc.default_price_list_id
        WHERE sc.id = %s
    """, (connection_id,)).fetchone()
    return dict(row) if row else None


def list_connections(conn) -> list:
    rows = conn.execute("""
        SELECT sc.*, c.company_name, c.first_name, c.last_name,
               pl.name AS price_list_name
        FROM storefront_connection sc
        LEFT JOIN customer c ON c.id = sc.default_customer_id
        LEFT JOIN price_list pl ON pl.id = sc.default_price_list_id
        ORDER BY sc.store_name
    """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Item cross-reference
# ---------------------------------------------------------------------------

def set_item_xref(conn, connection_id: int, external_sku: str, product_id: int) -> None:
    if not external_sku:
        raise ValueError("External SKU is required.")
    conn.execute(
        "INSERT INTO storefront_item_xref (connection_id, external_sku, product_id) "
        "VALUES (%s,%s,%s) "
        "ON CONFLICT (connection_id, external_sku) DO UPDATE "
        "SET product_id=EXCLUDED.product_id",
        (connection_id, external_sku, product_id),
    )


def list_item_xrefs(conn, connection_id: int) -> list:
    rows = conn.execute("""
        SELECT x.*, p.name AS product_name
        FROM storefront_item_xref x
        LEFT JOIN product p ON p.id = x.product_id
        WHERE x.connection_id = %s
        ORDER BY x.external_sku
    """, (connection_id,)).fetchall()
    return [dict(r) for r in rows]


def resolve_product_id(conn, connection_id: int, external_sku: str):
    if not external_sku:
        return None
    row = conn.execute(
        "SELECT product_id FROM storefront_item_xref "
        "WHERE connection_id = %s AND external_sku = %s",
        (connection_id, external_sku),
    ).fetchone()
    return row['product_id'] if row else None


def _resolve_external_sku(conn, connection_id: int, product_id):
    """Reverse lookup: our product_id -> the storefront's own SKU, for
    outbound inventory/price push payloads."""
    if not product_id:
        return None
    row = conn.execute(
        "SELECT external_sku FROM storefront_item_xref "
        "WHERE connection_id = %s AND product_id = %s LIMIT 1",
        (connection_id, product_id),
    ).fetchone()
    return row['external_sku'] if row else None


# ---------------------------------------------------------------------------
# Sync/order log
# ---------------------------------------------------------------------------

def _log_sync(conn, connection_id, event_type: str, direction: str, status: str,
              *, product_id=None, so_id=None, shipment_id=None, payload: str = '',
              detail: str = '', created_by=None) -> dict:
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO ecommerce_sync_log "
        "(connection_id, event_type, direction, product_id, so_id, shipment_id, "
        "payload, status, detail, created_at, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (connection_id, event_type, direction, product_id, so_id, shipment_id,
         payload, status, detail, now, created_by or ''),
    )
    return {
        'connection_id': connection_id, 'event_type': event_type,
        'direction': direction, 'product_id': product_id, 'so_id': so_id,
        'shipment_id': shipment_id, 'status': status, 'detail': detail,
    }


def list_sync_log(conn, connection_id: int | None = None, limit: int = 100) -> list:
    q = """
        SELECT l.*, sc.store_name
        FROM ecommerce_sync_log l
        LEFT JOIN storefront_connection sc ON sc.id = l.connection_id
    """
    params: list = []
    if connection_id:
        q += " WHERE l.connection_id = %s"
        params.append(connection_id)
    q += " ORDER BY l.id DESC LIMIT %s"
    params.append(limit)
    return [dict(r) for r in conn.execute(q, params).fetchall()]


def find_connection_for_so(conn, so_id: int):
    """Return the connection_id that created this SO via webhook, or None
    if the SO didn't originate from an e-commerce order."""
    row = conn.execute(
        "SELECT connection_id FROM ecommerce_order_log "
        "WHERE so_id = %s ORDER BY id DESC LIMIT 1",
        (so_id,),
    ).fetchone()
    return row['connection_id'] if row else None


# ---------------------------------------------------------------------------
# Inbound — order webhook
# ---------------------------------------------------------------------------

def verify_webhook_signature(secret: str, raw_body: bytes, signature_b64: str) -> bool:
    """Shopify (X-Shopify-Hmac-Sha256) and WooCommerce (X-WC-Webhook-
    Signature) both sign as base64(HMAC-SHA256(secret, raw_body)) — one
    verifier covers both platforms."""
    if not secret or not signature_b64:
        return False
    computed = base64.b64encode(
        hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).digest()
    ).decode('utf-8')
    return hmac.compare_digest(computed, signature_b64)


def parse_order_webhook(payload: dict) -> dict:
    """Normalize Shopify's and WooCommerce's near-identical order-webhook
    JSON shape (id/order_number, line_items: [{sku, quantity, price,
    name}]) into {external_order_id, order_date, email, lines: [{
    external_sku, description, qty, unit_price}]}. Covers the common
    subset of both platforms' shape, not the full API."""
    external_order_id = str(
        payload.get('id') or payload.get('order_number') or payload.get('number') or ''
    )
    raw_date = payload.get('created_at') or payload.get('date_created') or ''
    order_date = raw_date[:10] if raw_date else None

    lines = []
    for li in payload.get('line_items') or []:
        lines.append({
            'external_sku': li.get('sku') or '',
            'description': li.get('name') or li.get('title') or 'Item',
            'qty': float(li.get('quantity') or 1),
            'unit_price': float(li.get('price') or 0),
        })

    return {
        'external_order_id': external_order_id,
        'order_date': order_date,
        'email': payload.get('email') or '',
        'lines': lines,
    }


def receive_order_webhook(conn, connection_id: int, raw_body: bytes,
                           signature_header: str, created_by=None) -> dict:
    """Verify signature, dedupe against ecommerce_order_log (webhooks can
    legitimately retry/replay, unlike EDI's one-shot manual upload), then
    create a real Sales Order via the existing, unmodified
    next_so_number/create_so/add_so_item."""
    connection = get_connection(conn, connection_id)
    if not connection or not connection.get('is_active'):
        return {'ok': False, 'error': 'Unknown or inactive storefront connection.'}

    if not verify_webhook_signature(connection['webhook_secret'], raw_body, signature_header or ''):
        return {'ok': False, 'error': 'Invalid webhook signature.'}

    try:
        payload = json.loads(raw_body)
    except (ValueError, TypeError):
        return {'ok': False, 'error': 'Invalid JSON payload.'}

    parsed = parse_order_webhook(payload)
    if not parsed['external_order_id']:
        return {'ok': False, 'error': 'Order payload is missing an id.'}

    existing = conn.execute(
        "SELECT so_id FROM ecommerce_order_log "
        "WHERE connection_id = %s AND external_order_id = %s",
        (connection_id, parsed['external_order_id']),
    ).fetchone()
    if existing:
        return {'ok': True, 'duplicate': True, 'so_id': existing['so_id']}

    lines = []
    unmapped_count = 0
    for li in parsed['lines']:
        product_id = resolve_product_id(conn, connection_id, li['external_sku'])
        if product_id is None:
            unmapped_count += 1
        lines.append({**li, 'product_id': product_id})

    so_number = next_so_number(conn)
    so_id = create_so(
        conn, so_number, customer_id=connection.get('default_customer_id'),
        order_date=parsed['order_date'], status='draft',
        notes=f"Imported via e-Commerce webhook (order #{parsed['external_order_id']})",
        created_by=created_by,
    )
    for ln in lines:
        add_so_item(
            conn, so_id, ln['description'], product_id=ln['product_id'],
            qty=ln['qty'] or 1, unit_price=ln['unit_price'],
        )

    conn.execute(
        "INSERT INTO ecommerce_order_log (connection_id, external_order_id, so_id, created_at) "
        "VALUES (%s,%s,%s,%s)",
        (connection_id, parsed['external_order_id'], so_id, datetime.now().isoformat()),
    )
    _log_sync(
        conn, connection_id, 'order_webhook', 'inbound', 'success',
        so_id=so_id, detail=f"SO {so_number} created ({unmapped_count} unmapped line(s)).",
        payload=raw_body.decode('utf-8', errors='replace'), created_by=created_by,
    )

    return {
        'ok': True, 'duplicate': False, 'so_id': so_id, 'so_number': so_number,
        'unmapped_count': unmapped_count, 'line_count': len(lines),
    }


# ---------------------------------------------------------------------------
# Outbound — inventory / price / shipment push
# ---------------------------------------------------------------------------

def _post_json(url: str, payload: dict, timeout: int = 5) -> tuple:
    """Real HTTP POST via stdlib urllib (no new dependency). A network
    call is a legitimate boundary for a broad except: any transport
    failure should degrade to a logged 'failed' status, not crash the
    caller."""
    data = json.dumps(payload).encode('utf-8')
    req = Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=timeout) as resp:
            return True, f'HTTP {resp.status}'
    except (URLError, OSError) as e:
        return False, str(e)


def _dispatch_push(conn, connection: dict, event_type: str, payload: dict, created_by,
                    *, product_id=None, so_id=None, shipment_id=None) -> dict:
    endpoint = connection.get('sync_endpoint_url')
    if not endpoint:
        return _log_sync(
            conn, connection['id'], event_type, 'outbound', 'queued',
            product_id=product_id, so_id=so_id, shipment_id=shipment_id,
            payload=json.dumps(payload),
            detail='No sync endpoint configured — manual export required.',
            created_by=created_by,
        )
    ok, detail = _post_json(endpoint, payload)
    return _log_sync(
        conn, connection['id'], event_type, 'outbound',
        'success' if ok else 'failed',
        product_id=product_id, so_id=so_id, shipment_id=shipment_id,
        payload=json.dumps(payload), detail=detail, created_by=created_by,
    )


def push_inventory_level(conn, connection_id: int, product_id: int, created_by=None) -> dict:
    connection = get_connection(conn, connection_id)
    if not connection:
        return _log_sync(conn, connection_id, 'inventory_push', 'outbound', 'failed',
                          product_id=product_id, detail='Unknown storefront connection.',
                          created_by=created_by)
    row = conn.execute("SELECT amount FROM product WHERE id = %s", (product_id,)).fetchone()
    qty = float(row['amount']) if row and row['amount'] is not None else 0.0
    external_sku = _resolve_external_sku(conn, connection_id, product_id)
    payload = {'type': 'inventory', 'external_sku': external_sku, 'quantity': qty}
    return _dispatch_push(conn, connection, 'inventory_push', payload, created_by,
                           product_id=product_id)


def push_price_update(conn, connection_id: int, product_id: int, created_by=None) -> dict:
    connection = get_connection(conn, connection_id)
    if not connection:
        return _log_sync(conn, connection_id, 'price_push', 'outbound', 'failed',
                          product_id=product_id, detail='Unknown storefront connection.',
                          created_by=created_by)
    price_list_id = connection.get('default_price_list_id')
    price = get_price_for_product(conn, price_list_id, product_id, qty=1) if price_list_id else None
    if price is None:
        return _log_sync(conn, connection_id, 'price_push', 'outbound', 'failed',
                          product_id=product_id,
                          detail='No price list configured or no price for this product.',
                          created_by=created_by)
    external_sku = _resolve_external_sku(conn, connection_id, product_id)
    payload = {'type': 'price', 'external_sku': external_sku, 'price': price}
    return _dispatch_push(conn, connection, 'price_push', payload, created_by,
                           product_id=product_id)


def push_shipment_confirmation(conn, connection_id: int, shipment_id: int, created_by=None) -> dict:
    connection = get_connection(conn, connection_id)
    if not connection:
        return _log_sync(conn, connection_id, 'shipment_push', 'outbound', 'failed',
                          shipment_id=shipment_id, detail='Unknown storefront connection.',
                          created_by=created_by)
    shipment = get_shipment(conn, shipment_id)
    if not shipment:
        return _log_sync(conn, connection_id, 'shipment_push', 'outbound', 'failed',
                          shipment_id=shipment_id, detail='Shipment not found.',
                          created_by=created_by)
    order_row = conn.execute(
        "SELECT external_order_id FROM ecommerce_order_log "
        "WHERE connection_id = %s AND so_id = %s",
        (connection_id, shipment.get('so_id')),
    ).fetchone()
    if not order_row:
        return _log_sync(conn, connection_id, 'shipment_push', 'outbound', 'failed',
                          shipment_id=shipment_id, so_id=shipment.get('so_id'),
                          detail="Shipment's sales order has no e-commerce origin.",
                          created_by=created_by)
    payload = {
        'type': 'fulfillment', 'external_order_id': order_row['external_order_id'],
        'tracking_number': shipment.get('tracking_number') or '',
        'carrier': shipment.get('carrier') or '',
    }
    return _dispatch_push(conn, connection, 'shipment_push', payload, created_by,
                           shipment_id=shipment_id, so_id=shipment.get('so_id'))
