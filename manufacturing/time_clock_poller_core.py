"""Time clock device polling framework.

Manages physical time clock terminals (badge readers, biometric units, etc.)
and imports their punch records into the time_clock table.

Architecture:
  - time_clock_devices  — registered terminals (IP, type, location)
  - time_clock_sync_log — history of every poll attempt
  - Adapters            — one per device_type; each implements poll()

Adding a new hardware adapter:
  1. Write a class with .poll(device: dict) -> list[PunchRecord]
  2. Register it in ADAPTERS below
  3. Add the type string to DEVICE_TYPES

PunchRecord fields: people_id (int), punched_at (str 'YYYY-MM-DD HH:MM:SS'),
                    direction ('in'|'out'|'unknown')
"""
from datetime import datetime
from typing import NamedTuple


DEVICE_TYPES = ('csv', 'http_rest', 'zkteco', 'manual')

DEVICE_TYPE_LABELS = {
    'csv':      'CSV File Import',
    'http_rest': 'HTTP REST API',
    'zkteco':   'ZKTeco Terminal',
    'manual':   'Manual Entry',
}


class PunchRecord(NamedTuple):
    people_id: int
    punched_at: str      # 'YYYY-MM-DD HH:MM:SS'
    direction: str       # 'in', 'out', 'unknown'


# ---------------------------------------------------------------------------
# Device CRUD
# ---------------------------------------------------------------------------

def list_devices(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT d.*, l.last_sync_at, l.records_imported, l.status as last_status
        FROM time_clock_devices d
        LEFT JOIN LATERAL (
            SELECT synced_at as last_sync_at, records_imported, status
            FROM time_clock_sync_log
            WHERE device_id = d.id
            ORDER BY id DESC LIMIT 1
        ) l ON true
        ORDER BY d.name
    """).fetchall()
    return [dict(r) for r in rows]


def get_device(conn, device_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM time_clock_devices WHERE id = %s", (device_id,)
    ).fetchone()
    return dict(row) if row else None


def create_device(conn, name: str, location: str, device_type: str,
                  ip_address: str = '', port: int = 0,
                  config_json: str = '{}', created_by=None) -> int:
    row = conn.execute(
        "INSERT INTO time_clock_devices "
        "(name, location, device_type, ip_address, port, config_json, "
        "enabled, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,true,%s) RETURNING id",
        (name, location, device_type, ip_address, port or 0,
         config_json, created_by)
    ).fetchone()
    return row['id']


def update_device(conn, device_id: int, name: str, location: str,
                  device_type: str, ip_address: str = '', port: int = 0,
                  config_json: str = '{}', enabled: bool = True):
    conn.execute(
        "UPDATE time_clock_devices SET name=%s, location=%s, device_type=%s, "
        "ip_address=%s, port=%s, config_json=%s, enabled=%s WHERE id=%s",
        (name, location, device_type, ip_address, port or 0,
         config_json, enabled, device_id)
    )


def delete_device(conn, device_id: int):
    conn.execute(
        "DELETE FROM time_clock_sync_log WHERE device_id = %s", (device_id,))
    conn.execute(
        "DELETE FROM time_clock_devices WHERE id = %s", (device_id,))


# ---------------------------------------------------------------------------
# Sync log
# ---------------------------------------------------------------------------

def list_sync_log(conn, device_id: int | None = None,
                  limit: int = 50) -> list[dict]:
    if device_id:
        rows = conn.execute("""
            SELECT l.*, d.name as device_name
            FROM time_clock_sync_log l
            JOIN time_clock_devices d ON d.id = l.device_id
            WHERE l.device_id = %s
            ORDER BY l.id DESC LIMIT %s
        """, (device_id, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT l.*, d.name as device_name
            FROM time_clock_sync_log l
            JOIN time_clock_devices d ON d.id = l.device_id
            ORDER BY l.id DESC LIMIT %s
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def _write_sync_log(conn, device_id: int, status: str,
                    records_imported: int = 0, error_msg: str = '') -> int:
    row = conn.execute(
        "INSERT INTO time_clock_sync_log "
        "(device_id, synced_at, status, records_imported, error_msg) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (device_id,
         datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
         status, records_imported, error_msg)
    ).fetchone()
    return row['id']


# ---------------------------------------------------------------------------
# Import punches into time_clock
# ---------------------------------------------------------------------------

def import_punches(conn, device_id: int, punches: list[PunchRecord]) -> int:
    """Insert PunchRecords into time_clock, deduplicating on (people_id, punched_at).

    Returns count of rows actually inserted.
    """
    imported = 0
    for p in punches:
        existing = conn.execute(
            "SELECT id FROM time_clock WHERE people_id=%s AND clock_in=%s",
            (p.people_id, p.punched_at)
        ).fetchone()
        if existing:
            continue
        if p.direction == 'in':
            conn.execute(
                "INSERT INTO time_clock (people_id, clock_in, created_by) "
                "VALUES (%s,%s,'device:%s')",
                (p.people_id, p.punched_at, device_id)
            )
        elif p.direction == 'out':
            # Find the most recent open entry for this person
            open_entry = conn.execute(
                "SELECT id FROM time_clock "
                "WHERE people_id=%s AND clock_out IS NULL "
                "AND clock_in < %s ORDER BY id DESC LIMIT 1",
                (p.people_id, p.punched_at)
            ).fetchone()
            if open_entry:
                from .time_clock_core import compute_hours
                h = compute_hours(p.punched_at[:16].replace('T', ' ') + ':00',
                                  p.punched_at)
                conn.execute(
                    "UPDATE time_clock SET clock_out=%s, hours_worked=%s "
                    "WHERE id=%s",
                    (p.punched_at, round(h, 4), open_entry['id'])
                )
            else:
                # No open entry — store as a standalone out punch in notes
                conn.execute(
                    "INSERT INTO time_clock "
                    "(people_id, clock_in, clock_out, created_by) "
                    "VALUES (%s,%s,%s,'device:%s')",
                    (p.people_id, p.punched_at, p.punched_at, device_id)
                )
        else:
            conn.execute(
                "INSERT INTO time_clock (people_id, clock_in, created_by) "
                "VALUES (%s,%s,'device:%s')",
                (p.people_id, p.punched_at, device_id)
            )
        imported += 1
    return imported


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

class _CsvAdapter:
    """Import punches from a CSV file on disk.

    Expected format (header row required):
      employee_id,datetime,direction
      1001,2026-06-21 08:05:00,in
      1001,2026-06-21 17:02:00,out

    The device's config_json should contain: {"file_path": "/path/to/file.csv"}
    and employee_id must match people.employee_id.
    """

    def poll(self, device: dict, conn) -> tuple[list[PunchRecord], str]:
        import csv
        import json
        import os
        cfg = json.loads(device.get('config_json') or '{}')
        path = cfg.get('file_path', '')
        if not path or not os.path.exists(path):
            return [], f"File not found: {path}"

        # Build employee_id -> people_id map
        rows = conn.execute(
            "SELECT id, employee_id FROM people WHERE employee_id > 0"
        ).fetchall()
        emp_map = {r['employee_id']: r['id'] for r in rows}

        punches: list[PunchRecord] = []
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    emp_id = int(row.get('employee_id', 0))
                    people_id = emp_map.get(emp_id)
                    if not people_id:
                        continue
                    punched_at = row.get('datetime', '').strip()
                    direction = (row.get('direction') or 'unknown').strip().lower()
                    if direction not in ('in', 'out', 'unknown'):
                        direction = 'unknown'
                    punches.append(PunchRecord(people_id, punched_at, direction))
                except (ValueError, KeyError):
                    continue
        return punches, ''


class _HttpRestAdapter:
    """Poll a time clock device via HTTP REST API.

    config_json: {"base_url": "http://192.168.1.50", "api_key": "...",
                  "endpoint": "/api/punches"}

    Response must be JSON array:
      [{"employee_id": 1001, "datetime": "2026-06-21 08:05:00", "direction": "in"}, ...]

    This is a skeleton — wire in your device's actual API path and auth.
    """

    def poll(self, device: dict, conn) -> tuple[list[PunchRecord], str]:
        import json
        try:
            import urllib.request
        except ImportError:
            return [], "urllib not available"

        cfg = json.loads(device.get('config_json') or '{}')
        base_url = cfg.get('base_url', '').rstrip('/')
        endpoint = cfg.get('endpoint', '/api/punches')
        api_key = cfg.get('api_key', '')

        if not base_url:
            return [], "base_url not configured"

        url = base_url + endpoint
        rows = conn.execute(
            "SELECT id, employee_id FROM people WHERE employee_id > 0"
        ).fetchall()
        emp_map = {r['employee_id']: r['id'] for r in rows}

        try:
            req = urllib.request.Request(url)
            if api_key:
                req.add_header('Authorization', f'Bearer {api_key}')
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            return [], str(e)

        punches: list[PunchRecord] = []
        for item in data:
            try:
                emp_id = int(item.get('employee_id', 0))
                people_id = emp_map.get(emp_id)
                if not people_id:
                    continue
                direction = (item.get('direction') or 'unknown').lower()
                punches.append(PunchRecord(
                    people_id, item['datetime'], direction))
            except (ValueError, KeyError):
                continue
        return punches, ''


class _ZktecoAdapter:
    """ZKTeco terminal polling (TCP port 4370, ZKTeco protocol).

    config_json: {"ip": "192.168.1.100", "port": 4370, "password": 0}

    Requires pyzk: pip install pyzk
    This is a skeleton — install pyzk and uncomment the real logic below.
    """

    def poll(self, device: dict, conn) -> tuple[list[PunchRecord], str]:
        import json
        cfg = json.loads(device.get('config_json') or '{}')
        ip = cfg.get('ip') or device.get('ip_address', '')
        port = int(cfg.get('port') or device.get('port') or 4370)

        if not ip:
            return [], "IP address not configured"

        try:
            from zk import ZK  # type: ignore[import]
        except ImportError:
            return [], (
                "pyzk not installed. Run: pip install pyzk\n"
                f"Would connect to {ip}:{port}"
            )

        rows = conn.execute(
            "SELECT id, employee_id FROM people WHERE employee_id > 0"
        ).fetchall()
        emp_map = {r['employee_id']: r['id'] for r in rows}

        try:
            zk = ZK(ip, port=port, timeout=10,
                    password=int(cfg.get('password', 0)))
            conn_zk = zk.connect()
            attendance = conn_zk.get_attendance()
            conn_zk.disconnect()
        except Exception as e:
            return [], str(e)

        punches: list[PunchRecord] = []
        for rec in attendance:
            people_id = emp_map.get(rec.user_id)
            if not people_id:
                continue
            direction = 'in' if rec.punch == 0 else 'out'
            punched_at = rec.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            punches.append(PunchRecord(people_id, punched_at, direction))
        return punches, ''


class _ManualAdapter:
    """No-op adapter for manually-entered punches (web UI only)."""

    def poll(self, device: dict, conn) -> tuple[list[PunchRecord], str]:
        return [], "Manual devices are updated via the web UI — no polling needed."


ADAPTERS: dict = {
    'csv':      _CsvAdapter(),
    'http_rest': _HttpRestAdapter(),
    'zkteco':   _ZktecoAdapter(),
    'manual':   _ManualAdapter(),
}


# ---------------------------------------------------------------------------
# Poll a single device
# ---------------------------------------------------------------------------

def poll_device(conn, device_id: int) -> dict:
    """Poll one device, import punches, write sync log. Does not commit.

    Returns {'status': 'ok'|'error', 'records_imported': int, 'error': str}
    """
    device = get_device(conn, device_id)
    if not device:
        return {'status': 'error', 'records_imported': 0,
                'error': f'Device {device_id} not found'}
    if not device.get('enabled'):
        return {'status': 'error', 'records_imported': 0,
                'error': 'Device is disabled'}

    adapter = ADAPTERS.get(device['device_type'])
    if not adapter:
        err = f"Unknown device type: {device['device_type']}"
        _write_sync_log(conn, device_id, 'error', 0, err)
        return {'status': 'error', 'records_imported': 0, 'error': err}

    try:
        punches, err = adapter.poll(device, conn)
    except Exception as e:
        err = str(e)
        punches = []

    if err and not punches:
        _write_sync_log(conn, device_id, 'error', 0, err)
        return {'status': 'error', 'records_imported': 0, 'error': err}

    imported = import_punches(conn, device_id, punches)
    status = 'ok' if not err else 'partial'
    _write_sync_log(conn, device_id, status, imported, err)
    return {'status': status, 'records_imported': imported, 'error': err}
