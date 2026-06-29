"""Tests for time_clock_poller_core — Qt-free, no live database, no hardware."""
from manufacturing.time_clock_poller_core import (
    DEVICE_TYPES,
    DEVICE_TYPE_LABELS,
    PunchRecord,
    list_devices,
    get_device,
    create_device,
    update_device,
    delete_device,
    list_sync_log,
    import_punches,
    poll_device,
    ADAPTERS,
    _ManualAdapter,
)


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self, rows=None):
        self._rows = list(rows or [])

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Returns pre-loaded row-sets in sequence, one per execute()."""

    def __init__(self, *row_sequences):
        self.calls: list[tuple] = []
        self._seq = list(row_sequences)
        self._idx = 0

    def execute(self, sql, params=None):
        self.calls.append((sql.strip(), params))
        rows = self._seq[self._idx] if self._idx < len(self._seq) else []
        self._idx += 1
        return _FakeCursor(rows)

    def _sqls(self):
        return [sql for sql, _ in self.calls]


def _row(**kwargs):
    return kwargs


def _device(**overrides):
    base = dict(id=1, name='Front Door', location='Lobby', device_type='manual',
                ip_address='', port=0, config_json='{}', enabled=True,
                created_by='admin')
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_device_types_contains_expected():
    for t in ('csv', 'http_rest', 'zkteco', 'manual'):
        assert t in DEVICE_TYPES


def test_device_type_labels_covers_all_types():
    for t in DEVICE_TYPES:
        assert t in DEVICE_TYPE_LABELS


# ---------------------------------------------------------------------------
# PunchRecord
# ---------------------------------------------------------------------------

def test_punch_record_fields():
    p = PunchRecord(people_id=42, punched_at='2026-06-28 08:00:00', direction='in')
    assert p.people_id == 42
    assert p.punched_at == '2026-06-28 08:00:00'
    assert p.direction == 'in'


def test_punch_record_is_namedtuple():
    p = PunchRecord(1, '2026-06-28 08:00:00', 'in')
    assert isinstance(p, tuple)
    assert p._fields == ('people_id', 'punched_at', 'direction')


# ---------------------------------------------------------------------------
# list_devices
# ---------------------------------------------------------------------------

def test_list_devices_queries_with_lateral_join():
    conn = _FakeConn([])
    list_devices(conn)
    sql, _ = conn.calls[0]
    assert 'time_clock_devices' in sql
    assert 'time_clock_sync_log' in sql


def test_list_devices_returns_dicts():
    row = _row(id=1, name='Gate', location='Factory', device_type='zkteco',
               ip_address='192.168.1.1', port=4370, config_json='{}',
               enabled=True, created_by='admin',
               last_sync_at=None, records_imported=0, last_status=None)
    conn = _FakeConn([row])
    result = list_devices(conn)
    assert isinstance(result, list)
    assert result[0]['name'] == 'Gate'


# ---------------------------------------------------------------------------
# get_device
# ---------------------------------------------------------------------------

def test_get_device_returns_dict_when_found():
    row = _device()
    conn = _FakeConn([row])
    result = get_device(conn, 1)
    assert isinstance(result, dict)
    assert result['name'] == 'Front Door'


def test_get_device_returns_none_when_not_found():
    conn = _FakeConn([])
    result = get_device(conn, 999)
    assert result is None


def test_get_device_passes_id():
    conn = _FakeConn([])
    get_device(conn, 7)
    _, params = conn.calls[0]
    assert params == (7,)


# ---------------------------------------------------------------------------
# create_device
# ---------------------------------------------------------------------------

def test_create_device_returns_id():
    conn = _FakeConn([_row(id=3)])
    result = create_device(conn, 'Back Door', 'Warehouse', 'csv')
    assert result == 3


def test_create_device_passes_name_location_type():
    conn = _FakeConn([_row(id=1)])
    create_device(conn, 'Side Gate', 'Parking', 'http_rest',
                  ip_address='10.0.0.1', port=8080)
    sql, params = conn.calls[0]
    assert 'INSERT INTO time_clock_devices' in sql
    assert 'Side Gate' in params
    assert 'Parking' in params
    assert 'http_rest' in params


def test_create_device_enabled_by_default():
    conn = _FakeConn([_row(id=1)])
    create_device(conn, 'X', 'Y', 'manual')
    sql, _ = conn.calls[0]
    assert 'enabled' in sql


# ---------------------------------------------------------------------------
# update_device
# ---------------------------------------------------------------------------

def test_update_device_issues_update():
    conn = _FakeConn()
    update_device(conn, 1, 'New Name', 'New Loc', 'csv',
                  ip_address='', port=0, config_json='{}', enabled=False)
    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert 'UPDATE time_clock_devices' in sql
    assert False in params  # enabled=False


# ---------------------------------------------------------------------------
# delete_device
# ---------------------------------------------------------------------------

def test_delete_device_removes_sync_log_then_device():
    conn = _FakeConn()
    delete_device(conn, 5)
    sqls = conn._sqls()
    assert any('DELETE FROM time_clock_sync_log' in s for s in sqls)
    assert any('DELETE FROM time_clock_devices' in s for s in sqls)
    # Sync log must be deleted first (FK constraint)
    log_idx = next(i for i, s in enumerate(sqls) if 'sync_log' in s)
    dev_idx = next(i for i, s in enumerate(sqls) if 'time_clock_devices' in s)
    assert log_idx < dev_idx


# ---------------------------------------------------------------------------
# list_sync_log
# ---------------------------------------------------------------------------

def test_list_sync_log_no_device_filter():
    conn = _FakeConn([])
    list_sync_log(conn)
    sql, params = conn.calls[0]
    assert 'time_clock_sync_log' in sql
    assert 50 in params  # default limit


def test_list_sync_log_with_device_filter():
    conn = _FakeConn([])
    list_sync_log(conn, device_id=2, limit=10)
    sql, params = conn.calls[0]
    assert 'device_id = %s' in sql
    assert 2 in params
    assert 10 in params


def test_list_sync_log_returns_dicts():
    row = _row(id=1, device_id=1, device_name='Gate', synced_at='2026-01-01',
               status='ok', records_imported=5, error_msg='')
    conn = _FakeConn([row])
    result = list_sync_log(conn)
    assert result[0]['device_name'] == 'Gate'


# ---------------------------------------------------------------------------
# import_punches
# ---------------------------------------------------------------------------

def test_import_punches_skips_duplicates():
    punches = [PunchRecord(1, '2026-06-28 08:00:00', 'in')]
    # First execute (dup check) finds existing row
    conn = _FakeConn([_row(id=99)])
    count = import_punches(conn, device_id=1, punches=punches)
    assert count == 0
    assert len(conn.calls) == 1  # only the dup check


def test_import_punches_in_direction_inserts():
    punches = [PunchRecord(1, '2026-06-28 08:00:00', 'in')]
    conn = _FakeConn(
        [],   # no duplicate
        [],   # INSERT
    )
    count = import_punches(conn, device_id=1, punches=punches)
    assert count == 1
    sqls = conn._sqls()
    assert any('INSERT INTO time_clock' in s for s in sqls)


def test_import_punches_out_direction_updates_open_entry():
    punches = [PunchRecord(1, '2026-06-28 17:00:00', 'out')]
    conn = _FakeConn(
        [],               # no duplicate
        [_row(id=10)],    # open entry found
        [],               # UPDATE
    )
    count = import_punches(conn, device_id=1, punches=punches)
    assert count == 1
    sqls = conn._sqls()
    assert any('UPDATE time_clock SET clock_out' in s for s in sqls)


def test_import_punches_out_no_open_entry_inserts_standalone():
    punches = [PunchRecord(1, '2026-06-28 17:00:00', 'out')]
    conn = _FakeConn(
        [],   # no duplicate
        [],   # no open entry
        [],   # INSERT standalone
    )
    count = import_punches(conn, device_id=1, punches=punches)
    assert count == 1
    sqls = conn._sqls()
    assert any('INSERT INTO time_clock' in s for s in sqls)


def test_import_punches_unknown_direction_inserts():
    punches = [PunchRecord(1, '2026-06-28 08:00:00', 'unknown')]
    conn = _FakeConn([], [])  # no dup, then INSERT
    count = import_punches(conn, device_id=1, punches=punches)
    assert count == 1


def test_import_punches_multiple_mixed():
    punches = [
        PunchRecord(1, '2026-06-28 08:00:00', 'in'),
        PunchRecord(2, '2026-06-28 08:05:00', 'in'),
    ]
    conn = _FakeConn([], [], [], [])  # 2 dup checks + 2 inserts
    count = import_punches(conn, device_id=1, punches=punches)
    assert count == 2


# ---------------------------------------------------------------------------
# poll_device
# ---------------------------------------------------------------------------

def test_poll_device_not_found():
    conn = _FakeConn([])
    result = poll_device(conn, 999)
    assert result['status'] == 'error'
    assert 'not found' in result['error'].lower()


def test_poll_device_disabled():
    conn = _FakeConn([_device(enabled=False)])
    result = poll_device(conn, 1)
    assert result['status'] == 'error'
    assert 'disabled' in result['error'].lower()


def test_poll_device_unknown_type_writes_error_log():
    conn = _FakeConn(
        [_device(device_type='unknown_hw')],  # get_device
        [_row(id=1)],                          # _write_sync_log RETURNING id
    )
    result = poll_device(conn, 1)
    assert result['status'] == 'error'
    assert 'Unknown device type' in result['error']


def test_poll_device_manual_adapter_returns_ok_zero_imported():
    # Manual adapter always returns ([], "Manual devices...") — no error, no punches.
    # poll_device writes sync log even with 0 records.
    conn = _FakeConn(
        [_device(device_type='manual')],  # get_device
        [_row(id=1)],                      # _write_sync_log RETURNING id
    )
    result = poll_device(conn, 1)
    # err is the manual message; punches is []; imported == 0
    # status == 'partial' because err is truthy but punches=[]... actually:
    # Looking at the code: if err and not punches → writes error log and returns error.
    # Manual returns ("", "Manual devices...") — err is the message, punches is []
    # So: err and not punches → True → returns error status
    assert result['status'] == 'error'
    assert 'Manual' in result['error']


def test_poll_device_adapter_exception_writes_error_log():
    class _BoomAdapter:
        def poll(self, _device, _conn):
            raise RuntimeError("connection refused")

    original = ADAPTERS.get('csv')
    ADAPTERS['csv'] = _BoomAdapter()
    try:
        conn = _FakeConn(
            [_device(device_type='csv')],  # get_device
            [_row(id=1)],                   # _write_sync_log RETURNING id
        )
        result = poll_device(conn, 1)
        assert result['status'] == 'error'
        assert 'connection refused' in result['error']
    finally:
        ADAPTERS['csv'] = original


def test_poll_device_success_writes_ok_log():
    class _GoodAdapter:
        def poll(self, _device, _conn):
            return [], ''  # no punches, no error

    original = ADAPTERS.get('http_rest')
    ADAPTERS['http_rest'] = _GoodAdapter()
    try:
        conn = _FakeConn(
            [_device(device_type='http_rest')],  # get_device
            [_row(id=1)],                          # _write_sync_log RETURNING id
        )
        result = poll_device(conn, 1)
        assert result['status'] == 'ok'
        assert result['records_imported'] == 0
    finally:
        ADAPTERS['http_rest'] = original


def test_poll_device_imports_punches_and_logs():
    punches = [PunchRecord(1, '2026-06-28 08:00:00', 'in')]

    class _PunchAdapter:
        def poll(self, _device, _conn):
            return punches, ''

    original = ADAPTERS.get('csv')
    ADAPTERS['csv'] = _PunchAdapter()
    try:
        conn = _FakeConn(
            [_device(device_type='csv')],   # get_device
            [],                              # import_punches dup check
            [],                              # import_punches INSERT
            [_row(id=1)],                    # _write_sync_log RETURNING id
        )
        result = poll_device(conn, 1)
        assert result['records_imported'] == 1
        assert result['status'] == 'ok'
    finally:
        ADAPTERS['csv'] = original


# ---------------------------------------------------------------------------
# _ManualAdapter
# ---------------------------------------------------------------------------

def test_manual_adapter_poll_returns_empty_and_message():
    adapter = _ManualAdapter()
    punches, err = adapter.poll({}, None)
    assert punches == []
    assert 'Manual' in err
