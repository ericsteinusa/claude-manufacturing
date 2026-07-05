"""
schema.py — Single source of truth for the application's database schema.

Historically the core tables (people, passwd, roles, user_roles, dept,
dept_sub, position) were created with divergent ``CREATE TABLE IF NOT EXISTS``
statements scattered across half a dozen modules. Because ``IF NOT EXISTS``
means whichever statement runs first wins, the live schema depended on import
order. This module centralizes the canonical definitions.

Usage:
    from schema import init_schema

    init_schema()   # idempotent: safe to call on every startup

``init_schema`` both creates any missing tables and reconciles existing
tables created from an older, narrower definition by adding any missing
columns (``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``).
"""

from .audit_core import install_triggers
from .db_pg import get_db
from .log_utils import get_logger

log = get_logger(__name__)

# Ordered so a table is created before any table whose foreign keys
# reference it (people/dept/roles first).
_TABLES = [
    ("people", """
        CREATE TABLE IF NOT EXISTS people (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL DEFAULT '',
            last_name TEXT NOT NULL DEFAULT '',
            employee_id INTEGER NOT NULL DEFAULT 0,
            emp_id INTEGER,
            address TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '',
            zip_code TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            dept_id INTEGER,
            dept_sub_id INTEGER
        )
    """),
    ("dept", """
        CREATE TABLE IF NOT EXISTS dept (
            dept_id SERIAL PRIMARY KEY,
            dept_name TEXT NOT NULL UNIQUE
        )
    """),
    ("dept_sub", """
        CREATE TABLE IF NOT EXISTS dept_sub (
            dept_sub_id SERIAL PRIMARY KEY,
            dept_id INTEGER,
            dept_sub_name TEXT NOT NULL,
            FOREIGN KEY (dept_id) REFERENCES dept(dept_id)
        )
    """),
    ("roles", """
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            role_name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """),
    ("passwd", """
        CREATE TABLE IF NOT EXISTS passwd (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL UNIQUE,
            password TEXT NOT NULL,
            FOREIGN KEY (people_id) REFERENCES people(id)
        )
    """),
    ("user_roles", """
        CREATE TABLE IF NOT EXISTS user_roles (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL UNIQUE,
            role_id INTEGER NOT NULL,
            FOREIGN KEY (people_id) REFERENCES people(id),
            FOREIGN KEY (role_id) REFERENCES roles(id)
        )
    """),
    ("position", """
        CREATE TABLE IF NOT EXISTS position (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL UNIQUE,
            job_title TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (people_id) REFERENCES people(id)
        )
    """),
    ("location", """
        CREATE TABLE IF NOT EXISTS location (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """),
    ("time_off_request", """
        CREATE TABLE IF NOT EXISTS time_off_request (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL REFERENCES people(id),
            request_date TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            request_type TEXT NOT NULL DEFAULT 'Vacation',
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_by TEXT
        )
    """),
    ("time_clock", """
        CREATE TABLE IF NOT EXISTS time_clock (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL REFERENCES people(id),
            clock_in TEXT NOT NULL,
            clock_out TEXT,
            hours_worked REAL,
            notes TEXT DEFAULT '',
            created_by TEXT
        )
    """),
    ("time_clock_devices", """
        CREATE TABLE IF NOT EXISTS time_clock_devices (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            device_type TEXT NOT NULL DEFAULT 'manual',
            ip_address TEXT NOT NULL DEFAULT '',
            port INTEGER NOT NULL DEFAULT 0,
            config_json TEXT NOT NULL DEFAULT '{}',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_by TEXT
        )
    """),
    ("time_clock_sync_log", """
        CREATE TABLE IF NOT EXISTS time_clock_sync_log (
            id SERIAL PRIMARY KEY,
            device_id INTEGER NOT NULL REFERENCES time_clock_devices(id),
            synced_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ok',
            records_imported INTEGER NOT NULL DEFAULT 0,
            error_msg TEXT NOT NULL DEFAULT ''
        )
    """),
    ("po_approval", """
        CREATE TABLE IF NOT EXISTS po_approval (
            id SERIAL PRIMARY KEY,
            po_id INTEGER NOT NULL REFERENCES purchase_order(id),
            requested_by TEXT NOT NULL DEFAULT '',
            requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status TEXT NOT NULL DEFAULT 'pending',
            decided_by TEXT NOT NULL DEFAULT '',
            decided_at TIMESTAMPTZ,
            notes TEXT NOT NULL DEFAULT ''
        )
    """),
    ("closed_periods", """
        CREATE TABLE IF NOT EXISTS closed_periods (
            id SERIAL PRIMARY KEY,
            period_year INTEGER NOT NULL,
            period_month INTEGER NOT NULL,
            closed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            closed_by TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            UNIQUE(period_year, period_month)
        )
    """),
    ("audit_log", """
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGSERIAL PRIMARY KEY,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            action TEXT NOT NULL,
            changed_by TEXT NOT NULL DEFAULT '',
            changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            old_values JSONB,
            new_values JSONB
        )
    """),
    # --- Routing & labor tracking (Phase 1A) --------------------------------
    ("workcenter", """
        CREATE TABLE IF NOT EXISTS workcenter (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            dept TEXT NOT NULL DEFAULT '',
            capacity_hours_per_day REAL NOT NULL DEFAULT 8.0,
            labor_rate REAL NOT NULL DEFAULT 0.0,
            notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """),
    ("routing", """
        CREATE TABLE IF NOT EXISTS routing (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            operation_seq INTEGER NOT NULL DEFAULT 10,
            operation_name TEXT NOT NULL,
            workcenter_id INTEGER REFERENCES workcenter(id),
            std_hours REAL NOT NULL DEFAULT 0.0,
            notes TEXT,
            UNIQUE(product_id, operation_seq)
        )
    """),
    ("wo_operation", """
        CREATE TABLE IF NOT EXISTS wo_operation (
            id SERIAL PRIMARY KEY,
            wo_id INTEGER NOT NULL REFERENCES work_order(id),
            routing_id INTEGER REFERENCES routing(id),
            operation_seq INTEGER NOT NULL DEFAULT 10,
            operation_name TEXT NOT NULL,
            workcenter_id INTEGER REFERENCES workcenter(id),
            std_hours REAL NOT NULL DEFAULT 0.0,
            actual_hours REAL,
            scrap_qty REAL NOT NULL DEFAULT 0.0,
            rework_qty REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            completed_by TEXT,
            notes TEXT
        )
    """),
    # --- Lot & serial number tracking (Phase 1B) ----------------------------
    ("lot", """
        CREATE TABLE IF NOT EXISTS lot (
            id SERIAL PRIMARY KEY,
            lot_number TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL REFERENCES product(id),
            qty REAL NOT NULL DEFAULT 0.0,
            received_date TEXT,
            expiry_date TEXT,
            status TEXT NOT NULL DEFAULT 'available',
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
    ("serial_number", """
        CREATE TABLE IF NOT EXISTS serial_number (
            id SERIAL PRIMARY KEY,
            serial_number TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL REFERENCES product(id),
            lot_id INTEGER REFERENCES lot(id),
            status TEXT NOT NULL DEFAULT 'available',
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
    # --- SPC (Phase 6A) -------------------------------------------------------
    ("spc_control_limit", """
        CREATE TABLE IF NOT EXISTS spc_control_limit (
            id             SERIAL PRIMARY KEY,
            product_id     INTEGER REFERENCES product(id),
            characteristic TEXT NOT NULL,
            ucl            REAL NOT NULL,
            lcl            REAL NOT NULL,
            target         REAL,
            sigma          REAL,
            subgroup_size  INTEGER NOT NULL DEFAULT 5,
            is_active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_by     TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(product_id, characteristic)
        )
    """),
    ("spc_measurement", """
        CREATE TABLE IF NOT EXISTS spc_measurement (
            id             SERIAL PRIMARY KEY,
            product_id     INTEGER REFERENCES product(id),
            characteristic TEXT NOT NULL,
            measured_value REAL NOT NULL,
            measured_by    TEXT NOT NULL DEFAULT '',
            measured_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            wo_id          INTEGER REFERENCES work_order(id),
            lot_id         INTEGER REFERENCES lot(id),
            in_control     BOOLEAN NOT NULL DEFAULT TRUE,
            notes          TEXT NOT NULL DEFAULT '',
            created_by     TEXT NOT NULL DEFAULT ''
        )
    """),
    # --- Multi-level approval workflow (Phase 4C) ---------------------------
    ("approval_rule", """
        CREATE TABLE IF NOT EXISTS approval_rule (
            id                   SERIAL PRIMARY KEY,
            entity_type          TEXT NOT NULL,
            dept_key             TEXT NOT NULL DEFAULT '',
            threshold_amount     REAL NOT NULL DEFAULT 0.0,
            approver_role        TEXT NOT NULL,
            seq                  INTEGER NOT NULL DEFAULT 10,
            escalate_after_hours REAL NOT NULL DEFAULT 24.0,
            is_active            BOOLEAN NOT NULL DEFAULT TRUE,
            notes                TEXT NOT NULL DEFAULT ''
        )
    """),
    ("approval_step", """
        CREATE TABLE IF NOT EXISTS approval_step (
            id             SERIAL PRIMARY KEY,
            rule_id        INTEGER REFERENCES approval_rule(id),
            entity_type    TEXT NOT NULL,
            entity_id      INTEGER NOT NULL,
            seq            INTEGER NOT NULL DEFAULT 10,
            status         TEXT NOT NULL DEFAULT 'pending',
            approver_role  TEXT NOT NULL,
            decided_by     TEXT NOT NULL DEFAULT '',
            decided_at     TIMESTAMPTZ,
            notes          TEXT NOT NULL DEFAULT '',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
    # --- API token + rate limiting (Phase 4B) --------------------------------
    ("api_token", """
        CREATE TABLE IF NOT EXISTS api_token (
            token      TEXT PRIMARY KEY,
            people_id  INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT
        )
    """),
    ("api_login_attempt", """
        CREATE TABLE IF NOT EXISTS api_login_attempt (
            id           SERIAL PRIMARY KEY,
            identifier   TEXT NOT NULL,
            attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            success      BOOLEAN NOT NULL DEFAULT FALSE
        )
    """),
    ("api_totp_secret", """
        CREATE TABLE IF NOT EXISTS api_totp_secret (
            people_id  INTEGER PRIMARY KEY,
            secret_b32 TEXT NOT NULL,
            enabled    BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
    # --- GL segment codes / cost centers (Phase 3D) -------------------------
    ("cost_center", """
        CREATE TABLE IF NOT EXISTS cost_center (
            id SERIAL PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            dept_key TEXT NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """),
    # --- Bank reconciliation (Phase 3C) -------------------------------------
    ("bank_transaction", """
        CREATE TABLE IF NOT EXISTS bank_transaction (
            id SERIAL PRIMARY KEY,
            bank_account_id INTEGER NOT NULL REFERENCES bank_account(id),
            statement_id INTEGER REFERENCES bank_statement(id),
            trans_date TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            ref_number TEXT NOT NULL DEFAULT '',
            cleared BOOLEAN NOT NULL DEFAULT FALSE,
            matched_gl_line_id INTEGER REFERENCES gl_journal_line(id),
            created_by TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
    # --- IT module tables ---------------------------------------------------
    ("it_ticket", """
        CREATE TABLE IF NOT EXISTS it_ticket (
            id             SERIAL PRIMARY KEY,
            ticket_number  TEXT NOT NULL UNIQUE,
            requester      TEXT DEFAULT '',
            department     TEXT DEFAULT '',
            issue_type     TEXT DEFAULT '',
            description    TEXT DEFAULT '',
            priority       TEXT DEFAULT 'medium',
            assigned_to    TEXT DEFAULT '',
            submitted_date TEXT,
            due_date       TEXT,
            resolved_date  TEXT,
            status         TEXT DEFAULT 'open',
            notes          TEXT DEFAULT '',
            created_by     TEXT DEFAULT ''
        )
    """),
    ("it_asset", """
        CREATE TABLE IF NOT EXISTS it_asset (
            id            SERIAL PRIMARY KEY,
            asset_tag     TEXT NOT NULL UNIQUE,
            asset_type    TEXT DEFAULT '',
            make          TEXT DEFAULT '',
            model         TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            assigned_to   TEXT DEFAULT '',
            department    TEXT DEFAULT '',
            purchase_date TEXT,
            warranty_exp  TEXT,
            status        TEXT DEFAULT 'active',
            notes         TEXT DEFAULT '',
            created_by    TEXT DEFAULT ''
        )
    """),
    ("it_asset_history", """
        CREATE TABLE IF NOT EXISTS it_asset_history (
            id          SERIAL PRIMARY KEY,
            asset_tag   TEXT DEFAULT '',
            asset_id    INTEGER,
            event_type  TEXT DEFAULT '',
            description TEXT DEFAULT '',
            changed_by  TEXT DEFAULT '',
            changed_at  TIMESTAMP DEFAULT NOW()
        )
    """),
    ("it_repair", """
        CREATE TABLE IF NOT EXISTS it_repair (
            id               SERIAL PRIMARY KEY,
            asset_tag        TEXT DEFAULT '',
            problem_description TEXT DEFAULT '',
            reported_by      TEXT DEFAULT '',
            reported_date    DATE,
            assigned_to      TEXT DEFAULT '',
            priority         TEXT DEFAULT 'medium',
            status           TEXT DEFAULT 'open',
            resolution       TEXT DEFAULT '',
            completed_date   DATE,
            notes            TEXT DEFAULT '',
            created_by       TEXT DEFAULT ''
        )
    """),
    ("it_software_install", """
        CREATE TABLE IF NOT EXISTS it_software_install (
            id            SERIAL PRIMARY KEY,
            asset_tag     TEXT DEFAULT '',
            software_name TEXT DEFAULT '',
            version       TEXT DEFAULT '',
            vendor        TEXT DEFAULT '',
            install_date  DATE,
            status        TEXT DEFAULT 'installed',
            installed_by  TEXT DEFAULT '',
            notes         TEXT DEFAULT '',
            created_by    TEXT DEFAULT ''
        )
    """),
    ("it_license", """
        CREATE TABLE IF NOT EXISTS it_license (
            id            SERIAL PRIMARY KEY,
            software_name TEXT DEFAULT '',
            vendor        TEXT DEFAULT '',
            license_key   TEXT DEFAULT '',
            license_type  TEXT DEFAULT 'perpetual',
            seats         INTEGER DEFAULT 1,
            seats_used    INTEGER DEFAULT 0,
            purchase_date DATE,
            expiry_date   DATE,
            cost          REAL DEFAULT 0,
            status        TEXT DEFAULT 'active',
            notes         TEXT DEFAULT '',
            created_by    TEXT DEFAULT ''
        )
    """),
    ("it_network_device", """
        CREATE TABLE IF NOT EXISTS it_network_device (
            id           SERIAL PRIMARY KEY,
            hostname     TEXT DEFAULT '',
            ip_address   TEXT DEFAULT '',
            mac_address  TEXT DEFAULT '',
            device_type  TEXT DEFAULT '',
            manufacturer TEXT DEFAULT '',
            model        TEXT DEFAULT '',
            location     TEXT DEFAULT '',
            status       TEXT DEFAULT 'unknown',
            last_seen    DATE,
            notes        TEXT DEFAULT '',
            created_by   TEXT DEFAULT ''
        )
    """),
    ("it_network_incident", """
        CREATE TABLE IF NOT EXISTS it_network_incident (
            id               SERIAL PRIMARY KEY,
            title            TEXT DEFAULT '',
            severity         TEXT DEFAULT 'info',
            status           TEXT DEFAULT 'open',
            description      TEXT DEFAULT '',
            affected_systems TEXT DEFAULT '',
            reported_date    DATE,
            resolved_date    DATE,
            notes            TEXT DEFAULT '',
            created_by       TEXT DEFAULT ''
        )
    """),
    ("it_bandwidth_log", """
        CREATE TABLE IF NOT EXISTS it_bandwidth_log (
            id             SERIAL PRIMARY KEY,
            interface_name TEXT DEFAULT '',
            recorded_at    TIMESTAMP DEFAULT NOW(),
            mbps_in        REAL DEFAULT 0,
            mbps_out       REAL DEFAULT 0,
            notes          TEXT DEFAULT '',
            created_by     TEXT DEFAULT ''
        )
    """),
    ("it_task", """
        CREATE TABLE IF NOT EXISTS it_task (
            id             SERIAL PRIMARY KEY,
            task_number    TEXT NOT NULL UNIQUE,
            task_name      TEXT NOT NULL,
            task_type      TEXT,
            description    TEXT,
            assigned_to    TEXT,
            department     TEXT,
            priority       TEXT DEFAULT 'medium',
            scheduled_date TEXT,
            due_date       TEXT,
            completed_date TEXT,
            status         TEXT DEFAULT 'pending',
            notes          TEXT,
            created_by     TEXT
        )
    """),
    # --- MRP tables ---------------------------------------------------------
    ("mrp_run", """
        CREATE TABLE IF NOT EXISTS mrp_run (
            id SERIAL PRIMARY KEY,
            run_date TEXT,
            horizon_days INTEGER,
            notes TEXT,
            created_by TEXT
        )
    """),
    ("mrp_planned_order", """
        CREATE TABLE IF NOT EXISTS mrp_planned_order (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES mrp_run(id),
            product_id INTEGER NOT NULL,
            order_type TEXT,
            qty REAL,
            need_date TEXT,
            start_date TEXT,
            lead_time_days INTEGER DEFAULT 0,
            status TEXT DEFAULT 'suggested',
            released_ref TEXT
        )
    """),
    # --- Cost accounting (Phase 2) ------------------------------------------
    ("gl_account_map", """
        CREATE TABLE IF NOT EXISTS gl_account_map (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL UNIQUE,
            account_number TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """),
    ("cost_roll", """
        CREATE TABLE IF NOT EXISTS cost_roll (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            effective_date TEXT NOT NULL,
            std_material_cost REAL NOT NULL DEFAULT 0.0,
            std_labor_cost REAL NOT NULL DEFAULT 0.0,
            std_overhead_cost REAL NOT NULL DEFAULT 0.0,
            total_std_cost REAL NOT NULL DEFAULT 0.0,
            roll_notes TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
    ("wo_cost_actual", """
        CREATE TABLE IF NOT EXISTS wo_cost_actual (
            id SERIAL PRIMARY KEY,
            wo_id INTEGER NOT NULL UNIQUE REFERENCES work_order(id),
            actual_material_cost REAL NOT NULL DEFAULT 0.0,
            actual_labor_cost REAL NOT NULL DEFAULT 0.0,
            actual_overhead_cost REAL NOT NULL DEFAULT 0.0,
            total_actual_cost REAL NOT NULL DEFAULT 0.0,
            std_cost REAL NOT NULL DEFAULT 0.0,
            material_variance REAL NOT NULL DEFAULT 0.0,
            labor_variance REAL NOT NULL DEFAULT 0.0,
            total_variance REAL NOT NULL DEFAULT 0.0,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
]

_AUDIT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS audit_log_table_record "
    "ON audit_log(table_name, record_id)",
    "CREATE INDEX IF NOT EXISTS audit_log_changed_at "
    "ON audit_log(changed_at DESC)",
    "CREATE INDEX IF NOT EXISTS audit_log_changed_by "
    "ON audit_log(changed_by)",
    # Routing & lot indexes
    "CREATE INDEX IF NOT EXISTS wo_operation_wo_id ON wo_operation(wo_id)",
    "CREATE INDEX IF NOT EXISTS lot_product_id ON lot(product_id)",
    "CREATE INDEX IF NOT EXISTS sn_product_id ON serial_number(product_id)",
    # Cost accounting indexes
    "CREATE INDEX IF NOT EXISTS cost_roll_product "
    "ON cost_roll(product_id, effective_date DESC)",
    # Bank reconciliation indexes
    "CREATE INDEX IF NOT EXISTS bank_txn_statement "
    "ON bank_transaction(statement_id)",
    "CREATE INDEX IF NOT EXISTS bank_txn_cleared "
    "ON bank_transaction(statement_id, cleared)",
    # Approval workflow indexes
    "CREATE INDEX IF NOT EXISTS approval_step_entity "
    "ON approval_step(entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS approval_step_role_pending "
    "ON approval_step(approver_role, status)",
    # API rate limiting index
    "CREATE INDEX IF NOT EXISTS api_login_attempt_ident "
    "ON api_login_attempt(identifier, attempted_at DESC)",
    # SPC indexes (Phase 6A)
    "CREATE INDEX IF NOT EXISTS spc_meas_product_char "
    "ON spc_measurement(product_id, characteristic, measured_at DESC)",
    "CREATE INDEX IF NOT EXISTS spc_meas_out_of_control "
    "ON spc_measurement(in_control, measured_at DESC)",
]

# Columns backfilled onto pre-existing tables that may have been created from
# an older, narrower definition. Keyed by table; each entry is (name, def).
# Only additive columns are reconciled — constraints on existing tables are
# left untouched.
_RECONCILE = {
    "people": [
        ("first_name", "TEXT NOT NULL DEFAULT ''"),
        ("last_name", "TEXT NOT NULL DEFAULT ''"),
        ("employee_id", "INTEGER NOT NULL DEFAULT 0"),
        ("emp_id", "INTEGER"),
        ("address", "TEXT NOT NULL DEFAULT ''"),
        ("city", "TEXT NOT NULL DEFAULT ''"),
        ("state", "TEXT NOT NULL DEFAULT ''"),
        ("zip_code", "TEXT NOT NULL DEFAULT ''"),
        ("email", "TEXT NOT NULL DEFAULT ''"),
        ("dept_id", "INTEGER"),
        ("dept_sub_id", "INTEGER"),
        ("created_by", "TEXT"),
    ],
    "dept_sub": [
        ("dept_id", "INTEGER"),
    ],
    # Backfill lot tracking FK columns onto pre-existing tables
    "inventory_transaction": [
        ("lot_id", "INTEGER"),
    ],
    "wo_material": [
        ("lot_id", "INTEGER"),
    ],
    # Backfill overhead_rate onto workcenter (added in Phase 2)
    "workcenter": [
        ("overhead_rate", "REAL NOT NULL DEFAULT 0.0"),
    ],
    # Backfill asset hierarchy onto maint_equipment (Phase 6B)
    "maint_equipment": [
        ("parent_id", "INTEGER"),
    ],
    # Backfill equipment FK onto maint_part (Phase 6B)
    "maint_part": [
        ("equipment_id", "INTEGER"),
    ],
    # Backfill columns added to it_ticket after initial release
    "it_ticket": [
        ("created_by", "TEXT DEFAULT ''"),
        ("resolved_date", "TEXT"),
    ],
    # Backfill created_by onto it_asset
    "it_asset": [
        ("created_by", "TEXT DEFAULT ''"),
    ],
    # Backfill start_date / released_ref onto mrp_planned_order
    "mrp_planned_order": [
        ("start_date", "TEXT"),
        ("released_ref", "TEXT"),
        ("lead_time_days", "INTEGER DEFAULT 0"),
    ],
    # Backfill GL account link onto budget_line (Phase 3B)
    "budget_line": [
        ("gl_account_id", "INTEGER"),
    ],
    # Backfill cost_center_id onto gl_journal_line (Phase 3D)
    "gl_journal_line": [
        ("cost_center_id", "INTEGER"),
    ],
}


# Canonical role vocabulary — the single source of truth for the roles
# table. Seeded by init_schema(); both the desktop login (login_app) and
# the web layer (views) rely on these rather than defining their own set.
DEFAULT_LOCATIONS = [
    ('Main Plant', 'MAIN'),
    ('Warehouse', 'WH'),
    ('Office', 'OFF'),
]


DEFAULT_ROLES = [
    ('President', 'Full access — company president'),
    ('Vice President', 'Full access — company vice president'),
    ('Department Manager',
     'Full access to own department including management screens'),
    ('Supervisor', 'Access to own department operational screens'),
    ('Auditor',
     'Read-only browse access across all departments — cannot launch apps'),
    ('HR / Personnel', 'Full access to Personnel department'),
]


# Roles seeded by older builds, mapped to the canonical role that grants the
# same access level. init_schema() reassigns any user still holding a legacy
# role and then drops the orphaned legacy rows, so the obsolete vocabulary
# can't lock anyone out or linger in the role-admin UI.
_LEGACY_ROLE_MIGRATION = {
    'Admin': 'President',            # legacy superuser -> full access
    'Manager': 'Department Manager',
    'Employee': 'Supervisor',        # standard/general-staff access
    'Viewer': 'Auditor',             # read-only access
}


def _migrate_legacy_roles(conn):
    """Reassign users off legacy roles, then delete the orphaned rows.

    Idempotent and a no-op on databases that only ever had the canonical
    vocabulary: each statement matches nothing when the legacy role is
    absent. The canonical targets are guaranteed to exist because
    DEFAULT_ROLES is seeded immediately before this runs.
    """
    for legacy, canonical in _LEGACY_ROLE_MIGRATION.items():
        conn.execute(
            "UPDATE user_roles SET role_id = "
            "(SELECT id FROM roles WHERE role_name = %s) "
            "WHERE role_id = (SELECT id FROM roles WHERE role_name = %s)",
            (canonical, legacy))
        conn.execute(
            "DELETE FROM roles WHERE role_name = %s", (legacy,))


def init_schema():
    """Create and reconcile the core tables and seed default roles.

    Idempotent: safe to call on every startup.
    """
    conn = get_db()
    try:
        for _name, ddl in _TABLES:
            conn.execute(ddl)
        for table, columns in _RECONCILE.items():
            for col, col_def in columns:
                conn.execute(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN IF NOT EXISTS {col} {col_def}")
        for idx_sql in _AUDIT_INDEXES:
            conn.execute(idx_sql)
        for name, desc in DEFAULT_ROLES:
            conn.execute(
                "INSERT INTO roles (role_name, description) "
                "SELECT %s, %s WHERE NOT EXISTS "
                "(SELECT 1 FROM roles WHERE role_name = %s)",
                (name, desc, name))
        _migrate_legacy_roles(conn)
        for name, code in DEFAULT_LOCATIONS:
            conn.execute(
                "INSERT INTO location (name, code) "
                "SELECT %s, %s WHERE NOT EXISTS "
                "(SELECT 1 FROM location WHERE name = %s)",
                (name, code, name))
        conn.commit()
    finally:
        conn.close()
    install_triggers()
    log.debug(
        "Schema initialized and reconciled (%d tables, %d roles)",
        len(_TABLES), len(DEFAULT_ROLES))
