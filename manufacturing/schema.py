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
from .purchase_orders_core import ensure_po_tables
from .sales_orders_core import ensure_so_tables
from .work_orders_core import ensure_wo_tables

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
    # --- Tables that historically only ever had a CREATE TABLE in a sample-
    # data seed script, never in real application code — found via a real
    # fresh-database boot (Phase 1's docker-compose verification), not a
    # stale schema.py gap for existing dev DBs, which all happened to have
    # these from a seed run at some point. DDL below is copied from the
    # relevant seed script (the more actively-maintained source — cross-
    # checked against each table's real *_core.py query usage), not
    # reinvented. -------------------------------------------------------
    ("gl_account", """
        CREATE TABLE IF NOT EXISTS gl_account (
            id SERIAL PRIMARY KEY,
            account_number TEXT NOT NULL UNIQUE,
            account_name TEXT NOT NULL,
            account_type TEXT DEFAULT 'Expense',
            account_sub TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT ''
        )
    """),
    ("gl_journal", """
        CREATE TABLE IF NOT EXISTS gl_journal (
            id SERIAL PRIMARY KEY,
            journal_date TEXT DEFAULT '',
            reference TEXT DEFAULT '',
            description TEXT DEFAULT '',
            posted INTEGER DEFAULT 0,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """),
    ("gl_journal_line", """
        CREATE TABLE IF NOT EXISTS gl_journal_line (
            id SERIAL PRIMARY KEY,
            journal_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            memo TEXT DEFAULT ''
        )
    """),
    ("ap_invoice", """
        CREATE TABLE IF NOT EXISTS ap_invoice (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER,
            invoice_number TEXT NOT NULL UNIQUE,
            invoice_date TEXT DEFAULT '',
            due_date TEXT,
            amount REAL DEFAULT 0,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_by TEXT DEFAULT ''
        )
    """),
    ("ap_payment", """
        CREATE TABLE IF NOT EXISTS ap_payment (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL,
            payment_date TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            payment_method TEXT DEFAULT 'Check',
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """),
    ("ar_invoice", """
        CREATE TABLE IF NOT EXISTS ar_invoice (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER,
            invoice_number TEXT NOT NULL UNIQUE,
            invoice_date TEXT DEFAULT '',
            due_date TEXT,
            amount REAL DEFAULT 0,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_by TEXT DEFAULT ''
        )
    """),
    ("ar_payment", """
        CREATE TABLE IF NOT EXISTS ar_payment (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL,
            payment_date TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            payment_method TEXT DEFAULT 'Check',
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """),
    ("bank_account", """
        CREATE TABLE IF NOT EXISTS bank_account (
            id SERIAL PRIMARY KEY,
            account_name TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            account_number TEXT DEFAULT '',
            routing_number TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT ''
        )
    """),
    ("bank_statement", """
        CREATE TABLE IF NOT EXISTS bank_statement (
            id SERIAL PRIMARY KEY,
            bank_account_id INTEGER NOT NULL,
            statement_date TEXT NOT NULL,
            beginning_balance REAL DEFAULT 0,
            ending_balance REAL DEFAULT 0,
            status TEXT DEFAULT 'Open',
            reconciled_by TEXT DEFAULT '',
            reconciled_at TEXT DEFAULT ''
        )
    """),
    ("budget", """
        CREATE TABLE IF NOT EXISTS budget (
            id SERIAL PRIMARY KEY,
            budget_name TEXT NOT NULL,
            fiscal_year INTEGER,
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("budget_line", """
        CREATE TABLE IF NOT EXISTS budget_line (
            id SERIAL PRIMARY KEY,
            budget_id INTEGER NOT NULL,
            category TEXT DEFAULT '',
            description TEXT DEFAULT '',
            budgeted_amount REAL DEFAULT 0,
            notes TEXT DEFAULT ''
        )
    """),
    ("audit_schedule", """
        CREATE TABLE IF NOT EXISTS audit_schedule (
            id SERIAL PRIMARY KEY,
            audit_name TEXT NOT NULL,
            audit_type TEXT DEFAULT '',
            department TEXT DEFAULT '',
            auditor TEXT DEFAULT '',
            scheduled TEXT,
            completed TEXT,
            status TEXT DEFAULT 'Scheduled',
            notes TEXT DEFAULT ''
        )
    """),
    ("audit_finding", """
        CREATE TABLE IF NOT EXISTS audit_finding (
            id SERIAL PRIMARY KEY,
            audit_id INTEGER NOT NULL,
            finding_ref TEXT DEFAULT '',
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'Minor',
            department TEXT DEFAULT '',
            found_date TEXT,
            status TEXT DEFAULT 'Open',
            notes TEXT DEFAULT ''
        )
    """),
    ("tax_filing", """
        CREATE TABLE IF NOT EXISTS tax_filing (
            id SERIAL PRIMARY KEY,
            tax_type TEXT NOT NULL,
            jurisdiction TEXT DEFAULT '',
            period TEXT DEFAULT '',
            amount_due REAL DEFAULT 0,
            amount_paid REAL DEFAULT 0,
            filed_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Pending',
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """),
    ("tax_calendar", """
        CREATE TABLE IF NOT EXISTS tax_calendar (
            id SERIAL PRIMARY KEY,
            tax_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_date TEXT,
            status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT ''
        )
    """),
    ("customer", """
        CREATE TABLE IF NOT EXISTS customer (
            id SERIAL PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            company_name TEXT,
            phone_number TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            email TEXT,
            created_by TEXT
        )
    """),
    ("supplier", """
        CREATE TABLE IF NOT EXISTS supplier (
            id SERIAL PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            company_name TEXT,
            phone_number TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            email TEXT,
            created_by TEXT
        )
    """),
    ("bom", """
        CREATE TABLE IF NOT EXISTS bom (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            qty_required REAL DEFAULT 1.0,
            unit TEXT,
            notes TEXT,
            scrap_pct REAL DEFAULT 0.0
        )
    """),
    ("calls2", """
        CREATE TABLE IF NOT EXISTS calls2 (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER,
            call TEXT DEFAULT '',
            call_date TEXT DEFAULT '',
            call_time TEXT DEFAULT '',
            completion_date TEXT DEFAULT '',
            completion_time TEXT DEFAULT '',
            comments_box TEXT DEFAULT '',
            completion_box INTEGER DEFAULT 0,
            created_by TEXT DEFAULT ''
        )
    """),
    ("cs_improvement_plan", """
        CREATE TABLE IF NOT EXISTS cs_improvement_plan (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            target_date TEXT DEFAULT '',
            status TEXT DEFAULT 'Open',
            created_date TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("eng_project", """
        CREATE TABLE IF NOT EXISTS eng_project (
            id SERIAL PRIMARY KEY,
            project_number TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            product_id INTEGER,
            engineer TEXT DEFAULT '',
            start_date TEXT DEFAULT '',
            due_date TEXT,
            status TEXT DEFAULT 'planning',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("eng_task", """
        CREATE TABLE IF NOT EXISTS eng_task (
            id SERIAL PRIMARY KEY,
            project_id INTEGER,
            task_name TEXT NOT NULL,
            assigned_to TEXT DEFAULT '',
            due_date TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("eng_design_review", """
        CREATE TABLE IF NOT EXISTS eng_design_review (
            id SERIAL PRIMARY KEY,
            ecr_number TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            product_id INTEGER,
            project_id INTEGER,
            requested_by TEXT DEFAULT '',
            review_date TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("qa_inspection", """
        CREATE TABLE IF NOT EXISTS qa_inspection (
            id SERIAL PRIMARY KEY, insp_number TEXT NOT NULL UNIQUE,
            product_id INTEGER, wo_id INTEGER,
            insp_date TEXT DEFAULT '', inspector TEXT DEFAULT '',
            result TEXT DEFAULT 'pending', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("qa_defect", """
        CREATE TABLE IF NOT EXISTS qa_defect (
            id SERIAL PRIMARY KEY, insp_id INTEGER NOT NULL,
            defect_type TEXT DEFAULT '', severity TEXT DEFAULT 'minor',
            description TEXT NOT NULL, resolved INTEGER DEFAULT 0,
            created_by TEXT DEFAULT ''
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
    # --- Quality, Maintenance, Legal, Marketing, Sales, Risk: these used to
    # exist only via their sample-data seed script's own CREATE TABLE IF NOT
    # EXISTS, so a fresh database only had them once someone had run that
    # exact seed -- any real page (or dashboard tile) touching them first
    # crashed with psycopg2.errors.UndefinedTable. Centralizing them here
    # means they always exist by the time any view runs, same as every other
    # table above. Column sets copied from each seed's own (richer, already
    # battle-tested) definition, not manufacturing/create_missing_tables.py's
    # leaner version -- that one is missing `created_by`, which the real
    # quality_core.py/maintenance_core.py/sales_core.py insert functions all
    # require, so using it here as-is would have traded UndefinedTable for
    # UndefinedColumn the first time someone created a record by hand instead
    # of via a seed. purchase_requisition/requisition_item/requisition_approval
    # are deliberately left out of this pass: the live purchase_requisition
    # table has picked up at least one column (`purpose`, used by the mobile
    # API) that isn't in any CREATE TABLE statement in the codebase, so its
    # true schema can't be reconstructed with confidence here -- it still
    # only gets created via seed_sample_purchasing for now.
    ("qa_ncr", """
        CREATE TABLE IF NOT EXISTS qa_ncr (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, source TEXT DEFAULT '',
            severity TEXT DEFAULT 'Minor', product TEXT DEFAULT '',
            detected_date TEXT DEFAULT '', disposition TEXT DEFAULT 'Pending',
            owner TEXT DEFAULT '', status TEXT DEFAULT 'Open',
            notes TEXT DEFAULT '', created_by TEXT DEFAULT '',
            closed_date TEXT DEFAULT ''
        )
    """),
    ("qa_capa", """
        CREATE TABLE IF NOT EXISTS qa_capa (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            capa_type TEXT DEFAULT 'Corrective', ncr_ref TEXT DEFAULT '',
            owner TEXT DEFAULT '', due_date TEXT DEFAULT '',
            completed_date TEXT DEFAULT '', status TEXT DEFAULT 'Open',
            action_plan TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """),
    ("qa_audit", """
        CREATE TABLE IF NOT EXISTS qa_audit (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            audit_type TEXT DEFAULT '', auditor TEXT DEFAULT '',
            scheduled_date TEXT DEFAULT '', completed_date TEXT DEFAULT '',
            result TEXT DEFAULT '', status TEXT DEFAULT 'Scheduled',
            findings TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """),
    ("qa_supplier", """
        CREATE TABLE IF NOT EXISTS qa_supplier (
            id SERIAL PRIMARY KEY, supplier TEXT NOT NULL,
            material TEXT DEFAULT '', rating TEXT DEFAULT 'B',
            ppm TEXT DEFAULT '0', last_audit TEXT DEFAULT '',
            status TEXT DEFAULT 'Pending', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("maint_mechanic", """
        CREATE TABLE IF NOT EXISTS maint_mechanic (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, trade TEXT DEFAULT '',
            shift TEXT DEFAULT 'Day', phone TEXT DEFAULT '',
            status TEXT DEFAULT 'Active', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("maint_equipment", """
        CREATE TABLE IF NOT EXISTS maint_equipment (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, asset_tag TEXT DEFAULT '',
            location TEXT DEFAULT '', manufacturer TEXT DEFAULT '',
            install_date TEXT DEFAULT '', last_service TEXT DEFAULT '',
            status TEXT DEFAULT 'Operational', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("maint_work_order", """
        CREATE TABLE IF NOT EXISTS maint_work_order (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL, equipment TEXT DEFAULT '',
            work_type TEXT DEFAULT '', priority TEXT DEFAULT 'Medium',
            assigned_to TEXT DEFAULT '', requested_date TEXT DEFAULT '',
            due_date TEXT DEFAULT '', completed_date TEXT DEFAULT '',
            status TEXT DEFAULT 'Open', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("maint_schedule", """
        CREATE TABLE IF NOT EXISTS maint_schedule (
            id SERIAL PRIMARY KEY, task TEXT NOT NULL, equipment TEXT DEFAULT '',
            frequency TEXT DEFAULT '', assigned_to TEXT DEFAULT '',
            last_done TEXT DEFAULT '', next_due TEXT DEFAULT '',
            status TEXT DEFAULT 'Scheduled', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("maint_inspection", """
        CREATE TABLE IF NOT EXISTS maint_inspection (
            id SERIAL PRIMARY KEY, area TEXT NOT NULL,
            inspection_type TEXT DEFAULT '', inspector TEXT DEFAULT '',
            scheduled_date TEXT DEFAULT '', completed_date TEXT DEFAULT '',
            result TEXT DEFAULT '', status TEXT DEFAULT 'Scheduled',
            notes TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """),
    ("maint_downtime", """
        CREATE TABLE IF NOT EXISTS maint_downtime (
            id SERIAL PRIMARY KEY, equipment TEXT NOT NULL,
            reason TEXT DEFAULT '', category TEXT DEFAULT '',
            down_date TEXT DEFAULT '', hours TEXT DEFAULT '',
            cost REAL DEFAULT 0, status TEXT DEFAULT 'Ongoing',
            notes TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """),
    ("maint_part", """
        CREATE TABLE IF NOT EXISTS maint_part (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            part_number TEXT DEFAULT '', category TEXT DEFAULT '',
            location TEXT DEFAULT '', quantity TEXT DEFAULT '0',
            reorder_level TEXT DEFAULT '5', unit_cost REAL DEFAULT 0,
            status TEXT DEFAULT 'In Stock', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("legal_contract", """
        CREATE TABLE IF NOT EXISTS legal_contract (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            counterparty TEXT DEFAULT '', contract_type TEXT DEFAULT '',
            value REAL DEFAULT 0, start_date TEXT, end_date TEXT,
            owner TEXT DEFAULT '', status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT ''
        )
    """),
    ("legal_compliance", """
        CREATE TABLE IF NOT EXISTS legal_compliance (
            id SERIAL PRIMARY KEY, requirement TEXT NOT NULL,
            regulation TEXT DEFAULT '', owner TEXT DEFAULT '',
            due_date TEXT, completed_date TEXT,
            status TEXT DEFAULT 'Pending', notes TEXT DEFAULT ''
        )
    """),
    ("legal_litigation", """
        CREATE TABLE IF NOT EXISTS legal_litigation (
            id SERIAL PRIMARY KEY, case_name TEXT NOT NULL,
            opposing_party TEXT DEFAULT '', court TEXT DEFAULT '',
            case_type TEXT DEFAULT '', filed_date TEXT,
            status TEXT DEFAULT 'Open', outcome TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """),
    ("legal_ip", """
        CREATE TABLE IF NOT EXISTS legal_ip (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            ip_type TEXT DEFAULT '', registration_no TEXT DEFAULT '',
            jurisdiction TEXT DEFAULT '', filed_date TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '', status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT ''
        )
    """),
    ("legal_employment", """
        CREATE TABLE IF NOT EXISTS legal_employment (
            id SERIAL PRIMARY KEY, matter TEXT NOT NULL,
            employee TEXT DEFAULT '', matter_type TEXT DEFAULT '',
            owner TEXT DEFAULT '', opened_date TEXT DEFAULT '',
            closed_date TEXT DEFAULT '', status TEXT DEFAULT 'Open',
            notes TEXT DEFAULT ''
        )
    """),
    ("legal_governance", """
        CREATE TABLE IF NOT EXISTS legal_governance (
            id SERIAL PRIMARY KEY, item TEXT NOT NULL,
            category TEXT DEFAULT '', owner TEXT DEFAULT '',
            ref_date TEXT DEFAULT '', reference TEXT DEFAULT '',
            status TEXT DEFAULT 'Active', notes TEXT DEFAULT ''
        )
    """),
    ("marketing_campaign", """
        CREATE TABLE IF NOT EXISTS marketing_campaign (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            channel TEXT DEFAULT '', objective TEXT DEFAULT '',
            owner TEXT DEFAULT '', start_date DATE, end_date DATE,
            budget REAL DEFAULT 0, status TEXT DEFAULT 'Planned',
            notes TEXT DEFAULT ''
        )
    """),
    ("marketing_lead", """
        CREATE TABLE IF NOT EXISTS marketing_lead (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL,
            company TEXT DEFAULT '', email TEXT DEFAULT '',
            source TEXT DEFAULT '', owner TEXT DEFAULT '',
            captured_date DATE, status TEXT DEFAULT 'New',
            notes TEXT DEFAULT ''
        )
    """),
    ("marketing_content", """
        CREATE TABLE IF NOT EXISTS marketing_content (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            content_type TEXT DEFAULT '', channel TEXT DEFAULT '',
            author TEXT DEFAULT '', due_date DATE, publish_date DATE,
            status TEXT DEFAULT 'Draft', notes TEXT DEFAULT ''
        )
    """),
    ("sales_quote", """
        CREATE TABLE IF NOT EXISTS sales_quote (
            id SERIAL PRIMARY KEY, customer TEXT NOT NULL,
            description TEXT DEFAULT '', amount REAL DEFAULT 0,
            owner TEXT DEFAULT '', quote_date TEXT DEFAULT '',
            valid_until TEXT DEFAULT '', status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT '', created_by TEXT DEFAULT ''
        )
    """),
    ("sales_target", """
        CREATE TABLE IF NOT EXISTS sales_target (
            id SERIAL PRIMARY KEY, rep TEXT NOT NULL,
            period TEXT DEFAULT '', target REAL DEFAULT 0,
            actual REAL DEFAULT 0, region TEXT DEFAULT '',
            status TEXT DEFAULT 'On Track', notes TEXT DEFAULT '',
            created_by TEXT DEFAULT ''
        )
    """),
    ("risk_assessment", """
        CREATE TABLE IF NOT EXISTS risk_assessment (
            id SERIAL PRIMARY KEY, title TEXT NOT NULL,
            category TEXT DEFAULT '', likelihood TEXT DEFAULT '',
            impact TEXT DEFAULT '', risk_level TEXT DEFAULT '',
            owner TEXT DEFAULT '', assessed_date TEXT DEFAULT '',
            status TEXT DEFAULT 'Identified', notes TEXT DEFAULT ''
        )
    """),
    ("risk_register", """
        CREATE TABLE IF NOT EXISTS risk_register (
            id SERIAL PRIMARY KEY, risk TEXT NOT NULL,
            category TEXT DEFAULT '', severity TEXT DEFAULT '',
            response TEXT DEFAULT '', owner TEXT DEFAULT '',
            target_date TEXT DEFAULT '', status TEXT DEFAULT 'Open',
            mitigation TEXT DEFAULT ''
        )
    """),
    ("risk_insurance", """
        CREATE TABLE IF NOT EXISTS risk_insurance (
            id SERIAL PRIMARY KEY, policy TEXT NOT NULL,
            insurer TEXT DEFAULT '', policy_type TEXT DEFAULT '',
            coverage REAL DEFAULT 0, premium REAL DEFAULT 0,
            start_date TEXT DEFAULT '', end_date TEXT DEFAULT '',
            status TEXT DEFAULT 'Active', notes TEXT DEFAULT ''
        )
    """),
    ("risk_continuity", """
        CREATE TABLE IF NOT EXISTS risk_continuity (
            id SERIAL PRIMARY KEY, plan TEXT NOT NULL,
            scope TEXT DEFAULT '', criticality TEXT DEFAULT '',
            owner TEXT DEFAULT '', last_tested TEXT DEFAULT '',
            next_test TEXT DEFAULT '', status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT ''
        )
    """),
    ("risk_audit", """
        CREATE TABLE IF NOT EXISTS risk_audit (
            id SERIAL PRIMARY KEY, audit TEXT NOT NULL,
            framework TEXT DEFAULT '', auditor TEXT DEFAULT '',
            scheduled_date TEXT DEFAULT '', completed_date TEXT DEFAULT '',
            finding TEXT DEFAULT '', status TEXT DEFAULT 'Scheduled',
            notes TEXT DEFAULT ''
        )
    """),
    ("risk_kri", """
        CREATE TABLE IF NOT EXISTS risk_kri (
            id SERIAL PRIMARY KEY, indicator TEXT NOT NULL,
            category TEXT DEFAULT '', threshold TEXT DEFAULT '',
            current_value TEXT DEFAULT '', owner TEXT DEFAULT '',
            measured_date TEXT DEFAULT '', status TEXT DEFAULT 'Normal',
            notes TEXT DEFAULT ''
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
    # Backfill a mailing address onto dept, matching the address/city/state/
    # zip_code convention already used on people/customer/supplier.
    "dept": [
        ("address", "TEXT NOT NULL DEFAULT ''"),
        ("city", "TEXT NOT NULL DEFAULT ''"),
        ("state", "TEXT NOT NULL DEFAULT ''"),
        ("zip_code", "TEXT NOT NULL DEFAULT ''"),
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
    # Backfill hourly labor rate onto maint_mechanic, so Maintenance WOs get
    # a real per-mechanic cost instead of falling back to workcenter rate
    # (WO time/cost variance reports).
    "maint_mechanic": [
        ("hourly_rate", "REAL NOT NULL DEFAULT 0.0"),
    ],
    # Backfill actual/estimated hours onto maint_work_order — mirrors
    # wo_operation.std_hours/actual_hours on the Production side, entered
    # manually since maintenance WOs have no routing-equivalent template
    # (WO time/cost variance reports).
    "maint_work_order": [
        ("actual_hours", "REAL"),
        ("estimated_hours", "REAL"),
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
    # Backfill department link onto budget, so budgets can be scoped to a
    # department (nullable — a budget can still be company-wide/unassigned)
    "budget": [
        ("department_id", "INTEGER"),
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
        # product/work_order/purchase_order/po_item are created lazily by
        # their own modules (work_orders_core.py / purchase_orders_core.py),
        # not centrally here — but several tables in _TABLES below have a
        # hard FK REFERENCES to them (po_approval -> purchase_order,
        # wo_operation -> work_order, several -> product), so they must exist
        # *before* the _TABLES loop runs on a completely fresh database.
        # Every existing dev DB already had these from years of ad-hoc use,
        # which is why this ordering bug was never caught before a real
        # fresh-database boot (Phase 1's docker-compose verification).
        #
        # `product` is pre-created here (duplicating ensure_wo_tables' own
        # CREATE TABLE, harmless since IF NOT EXISTS) because
        # inventory_transaction needs it to exist, and inventory_transaction
        # itself must exist *before* ensure_wo_tables runs: that function
        # internally calls lot_core.ensure_lot_tables, which ALTERs
        # inventory_transaction and would otherwise crash on a fresh DB too.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product (
                id SERIAL PRIMARY KEY,
                supplier_id INTEGER, name TEXT NOT NULL,
                purchase_date TEXT, purchase_price REAL DEFAULT 0.0,
                bin TEXT, amount INTEGER DEFAULT 0, reorder_point INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transaction (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES product(id),
                trans_date TEXT,
                trans_type TEXT,
                quantity REAL DEFAULT 0,
                reference TEXT,
                notes TEXT,
                created_by TEXT
            )
        """)
        ensure_po_tables(conn)
        ensure_wo_tables(conn)
        # sales_order/so_item: same class of gap as above — ensure_so_tables
        # is real and already handles the "created_by column missing because
        # an older seed script created the table first" drift itself (its
        # own defensive ALTER), but was never actually called at startup.
        ensure_so_tables(conn)

        for _name, ddl in _TABLES:
            conn.execute(ddl)
        for table, columns in _RECONCILE.items():
            for col, col_def in columns:
                # A handful of _RECONCILE entries (maint_equipment, maint_part)
                # target tables from departments not yet centrally bootstrapped
                # here (Maintenance/Legal/Marketing/Risk — still only created
                # via seed scripts or the standalone create_missing_tables.py
                # migration, a separate, larger follow-up). Skip via savepoint
                # rather than crash init_schema() entirely on a fresh DB; once
                # that table exists, this reconciles normally on the next
                # startup.
                conn.execute(f"SAVEPOINT reconcile_{table}")
                try:
                    conn.execute(
                        f"ALTER TABLE {table} "
                        f"ADD COLUMN IF NOT EXISTS {col} {col_def}")
                    conn.execute(f"RELEASE SAVEPOINT reconcile_{table}")
                except Exception:
                    conn.execute(f"ROLLBACK TO SAVEPOINT reconcile_{table}")
                    conn.execute(f"RELEASE SAVEPOINT reconcile_{table}")
        for idx_sql in _AUDIT_INDEXES:
            conn.execute(idx_sql)
        # Reconcile SERIAL sequences that can drift behind MAX(id) when rows
        # are seeded with explicit ids (see seeds/seed_sample_data.py's own
        # dept/dept_sub comment on this) -- otherwise the next INSERT relying
        # on the sequence default collides with an existing row ("duplicate
        # key value violates unique constraint"). Safe/idempotent: a no-op
        # once the sequence has caught up.
        for _seq_table, _seq_col in (("dept", "dept_id"), ("dept_sub", "dept_sub_id")):
            conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{_seq_table}', '{_seq_col}'), "
                f"GREATEST((SELECT COALESCE(MAX({_seq_col}), 0) FROM {_seq_table}), 1))"
            )
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
