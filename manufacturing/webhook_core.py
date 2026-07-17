"""
webhook_core.py — general-purpose outbound webhook dispatch.

webhook_subscription  — who wants to hear about which events, and where.
webhook_delivery       — an audit log of every dispatch attempt (mirrors
                         ecommerce_core.py's ecommerce_sync_log for its own
                         outbound pushes).

Event-type convention: "<entity>.<status>" (e.g. "po.received",
"wo.completed", "so.confirmed", "ncr.opened") — dotted, Stripe/GitHub-style,
so a subscriber picks exactly the transition it cares about rather than
getting every status change for an entity type.

Dispatch is fire-and-forget and never raises: a broken or unreachable
subscriber must not break the caller's real transaction (a WO/PO/SO status
change, or NCR creation). This mirrors two existing precedents in this
codebase: ecommerce_core.py's _post_json (a network call is a legitimate
except-boundary) and notify_core.py's _send (all exceptions swallowed and
logged, never propagated).
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from .log_utils import get_logger

log = get_logger(__name__)

EVENT_TYPES = (
    'po.draft', 'po.pending_approval', 'po.sent', 'po.partial',
    'po.received', 'po.cancelled',
    'wo.draft', 'wo.open', 'wo.in_progress', 'wo.completed', 'wo.cancelled',
    'so.draft', 'so.confirmed', 'so.shipped', 'so.invoiced', 'so.cancelled',
    'ncr.opened',
)


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def ensure_webhook_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS webhook_subscription (
            id           SERIAL PRIMARY KEY,
            event_type   TEXT NOT NULL,
            target_url   TEXT NOT NULL,
            secret       TEXT NOT NULL DEFAULT '',
            is_active    BOOLEAN NOT NULL DEFAULT TRUE,
            created_by   TEXT NOT NULL DEFAULT '',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS webhook_delivery (
            id              SERIAL PRIMARY KEY,
            subscription_id INTEGER,
            event_type      TEXT NOT NULL,
            entity_type     TEXT NOT NULL,
            entity_id       INTEGER,
            payload         TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL,
            detail          TEXT NOT NULL DEFAULT '',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS webhook_subscription_event "
        "ON webhook_subscription(event_type, is_active)"
    )


# ---------------------------------------------------------------------------
# Subscription CRUD
# ---------------------------------------------------------------------------

def create_subscription(conn, event_type: str, target_url: str,
                        secret: str = '', created_by: str = '') -> int:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of {EVENT_TYPES}")
    if not target_url.strip():
        raise ValueError("target_url is required")
    row = conn.execute(
        "INSERT INTO webhook_subscription (event_type, target_url, secret, created_by) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (event_type, target_url.strip(), secret or '', created_by or ''),
    ).fetchone()
    return row['id']


def list_subscriptions(conn, event_type: str | None = None,
                       active_only: bool = False) -> list[dict]:
    conds, params = [], []
    if active_only:
        conds.append("is_active = TRUE")
    if event_type:
        conds.append("event_type = %s")
        params.append(event_type)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = conn.execute(
        f"SELECT id, event_type, target_url, secret, is_active, created_by, created_at "
        f"FROM webhook_subscription {where} ORDER BY event_type, id",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_subscription(conn, subscription_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, event_type, target_url, secret, is_active, created_by, created_at "
        "FROM webhook_subscription WHERE id = %s",
        (subscription_id,),
    ).fetchone()
    return dict(row) if row else None


def update_subscription(conn, subscription_id: int, **fields) -> None:
    allowed = {'event_type', 'target_url', 'secret', 'is_active'}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    if 'event_type' in cols and cols['event_type'] not in EVENT_TYPES:
        raise ValueError(f"event_type must be one of {EVENT_TYPES}")
    set_clause = ", ".join(f"{k} = %s" for k in cols)
    conn.execute(
        f"UPDATE webhook_subscription SET {set_clause} WHERE id = %s",
        list(cols.values()) + [subscription_id],
    )


def delete_subscription(conn, subscription_id: int) -> None:
    conn.execute("DELETE FROM webhook_subscription WHERE id = %s", (subscription_id,))


def list_deliveries(conn, subscription_id: int | None = None, limit: int = 50) -> list[dict]:
    sql = ("SELECT id, subscription_id, event_type, entity_type, entity_id, "
           "payload, status, detail, created_at FROM webhook_delivery")
    params = []
    if subscription_id:
        sql += " WHERE subscription_id = %s"
        params.append(subscription_id)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _sign_payload(secret: str, body: bytes) -> str:
    """Same base64(HMAC-SHA256) scheme this app's inbound Shopify/WooCommerce
    webhook verification already uses (ecommerce_core.verify_webhook_signature),
    so a subscriber built against that existing pattern can verify ours too."""
    return base64.b64encode(
        hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    ).decode('ascii')


def _post_webhook(url: str, body: bytes, secret: str, timeout: int = 5) -> tuple:
    """Real HTTP POST via stdlib urllib (no new dependency) — same approach
    as ecommerce_core._post_json. A network call is a legitimate boundary
    for a narrow except: any transport failure degrades to a logged
    'failed' delivery, not a raised exception."""
    headers = {'Content-Type': 'application/json'}
    if secret:
        headers['X-Webhook-Signature'] = _sign_payload(secret, body)
    req = Request(url, data=body, headers=headers, method='POST')
    try:
        with urlopen(req, timeout=timeout) as resp:
            return True, f'HTTP {resp.status}'
    except (URLError, OSError) as e:
        return False, str(e)


def dispatch_event(conn, event_type: str, entity_type: str, entity_id: int,
                   extra: dict | None = None) -> int:
    """Fire *event_type* to every active subscription for it.

    Never raises: any failure (bad subscriber config, DB hiccup writing the
    delivery log, network error) is logged and swallowed, since a broken
    webhook subscriber must never break the real business transaction this
    is hung off of. Returns the number of subscriptions dispatched to.
    """
    try:
        ensure_webhook_tables(conn)
        subs = conn.execute(
            "SELECT id, target_url, secret FROM webhook_subscription "
            "WHERE event_type = %s AND is_active = TRUE",
            (event_type,),
        ).fetchall()
    except Exception as exc:
        log.warning("dispatch_event: failed to load subscriptions for %s: %s",
                    event_type, exc)
        return 0
    if not subs:
        return 0

    payload = {
        'event_type': event_type,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'occurred_at': datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    body = json.dumps(payload).encode('utf-8')

    dispatched = 0
    for sub in subs:
        try:
            ok, detail = _post_webhook(sub['target_url'], body, sub['secret'] or '')
            conn.execute(
                "INSERT INTO webhook_delivery "
                "(subscription_id, event_type, entity_type, entity_id, "
                " payload, status, detail) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (sub['id'], event_type, entity_type, entity_id,
                 body.decode('utf-8'), 'success' if ok else 'failed', detail),
            )
            dispatched += 1
        except Exception as exc:
            log.warning("dispatch_event: delivery to subscription %s failed: %s",
                        sub.get('id'), exc)
    return dispatched
