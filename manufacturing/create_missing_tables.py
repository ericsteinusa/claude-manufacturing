"""
One-time migration: create all tables defined in the codebase that are missing
from the local database.  Safe to run repeatedly (all statements use
CREATE TABLE IF NOT EXISTS).

Usage:
    python -m manufacturing.create_missing_tables
"""

from manufacturing.db_pg import get_db_connection

# Ordered so FK parents come before children.
STATEMENTS = [
    # ------------------------------------------------------------------ Legal
    """CREATE TABLE IF NOT EXISTS legal_contract (
        id            SERIAL PRIMARY KEY,
        title         TEXT    NOT NULL,
        counterparty  TEXT    DEFAULT '',
        contract_type TEXT    DEFAULT '',
        value         REAL    DEFAULT 0,
        start_date    TEXT    DEFAULT '',
        end_date      TEXT    DEFAULT '',
        owner         TEXT    DEFAULT '',
        status        TEXT    DEFAULT 'Draft',
        notes         TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS legal_compliance (
        id             SERIAL PRIMARY KEY,
        requirement    TEXT    NOT NULL,
        regulation     TEXT    DEFAULT '',
        owner          TEXT    DEFAULT '',
        due_date       TEXT    DEFAULT '',
        completed_date TEXT    DEFAULT '',
        status         TEXT    DEFAULT 'Pending',
        notes          TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS legal_litigation (
        id             SERIAL PRIMARY KEY,
        case_name      TEXT    NOT NULL,
        opposing_party TEXT    DEFAULT '',
        court          TEXT    DEFAULT '',
        case_type      TEXT    DEFAULT '',
        filed_date     TEXT    DEFAULT '',
        status         TEXT    DEFAULT 'Open',
        outcome        TEXT    DEFAULT '',
        notes          TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS legal_ip (
        id              SERIAL PRIMARY KEY,
        title           TEXT    NOT NULL,
        ip_type         TEXT    DEFAULT '',
        registration_no TEXT    DEFAULT '',
        jurisdiction    TEXT    DEFAULT '',
        filed_date      TEXT    DEFAULT '',
        expiry_date     TEXT    DEFAULT '',
        status          TEXT    DEFAULT 'Pending',
        notes           TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS legal_employment (
        id          SERIAL PRIMARY KEY,
        matter      TEXT    NOT NULL,
        employee    TEXT    DEFAULT '',
        matter_type TEXT    DEFAULT '',
        owner       TEXT    DEFAULT '',
        opened_date TEXT    DEFAULT '',
        closed_date TEXT    DEFAULT '',
        status      TEXT    DEFAULT 'Open',
        notes       TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS legal_governance (
        id        SERIAL PRIMARY KEY,
        item      TEXT    NOT NULL,
        category  TEXT    DEFAULT '',
        owner     TEXT    DEFAULT '',
        ref_date  TEXT    DEFAULT '',
        reference TEXT    DEFAULT '',
        status    TEXT    DEFAULT 'Active',
        notes     TEXT    DEFAULT ''
    )""",

    # ---------------------------------------------------------- Maintenance
    """CREATE TABLE IF NOT EXISTS maint_equipment (
        id           SERIAL PRIMARY KEY,
        name         TEXT    NOT NULL,
        asset_tag    TEXT    DEFAULT '',
        location     TEXT    DEFAULT '',
        manufacturer TEXT    DEFAULT '',
        install_date TEXT    DEFAULT '',
        last_service TEXT    DEFAULT '',
        status       TEXT    DEFAULT 'Operational',
        notes        TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS maint_work_order (
        id             SERIAL PRIMARY KEY,
        title          TEXT    NOT NULL,
        equipment      TEXT    DEFAULT '',
        work_type      TEXT    DEFAULT '',
        priority       TEXT    DEFAULT 'Medium',
        assigned_to    TEXT    DEFAULT '',
        requested_date TEXT    DEFAULT '',
        due_date       TEXT    DEFAULT '',
        completed_date TEXT    DEFAULT '',
        status         TEXT    DEFAULT 'Open',
        notes          TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS maint_part (
        id            SERIAL PRIMARY KEY,
        name          TEXT    NOT NULL,
        part_number   TEXT    DEFAULT '',
        category      TEXT    DEFAULT '',
        location      TEXT    DEFAULT '',
        quantity      TEXT    DEFAULT '',
        reorder_level TEXT    DEFAULT '',
        unit_cost     REAL    DEFAULT 0,
        status        TEXT    DEFAULT 'In Stock',
        notes         TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS maint_schedule (
        id          SERIAL PRIMARY KEY,
        task        TEXT    NOT NULL,
        equipment   TEXT    DEFAULT '',
        frequency   TEXT    DEFAULT '',
        assigned_to TEXT    DEFAULT '',
        last_done   TEXT    DEFAULT '',
        next_due    TEXT    DEFAULT '',
        status      TEXT    DEFAULT 'Scheduled',
        notes       TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS maint_inspection (
        id              SERIAL PRIMARY KEY,
        area            TEXT    NOT NULL,
        inspection_type TEXT    DEFAULT '',
        inspector       TEXT    DEFAULT '',
        scheduled_date  TEXT    DEFAULT '',
        completed_date  TEXT    DEFAULT '',
        result          TEXT    DEFAULT '',
        status          TEXT    DEFAULT 'Scheduled',
        notes           TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS maint_downtime (
        id        SERIAL PRIMARY KEY,
        equipment TEXT    NOT NULL,
        reason    TEXT    DEFAULT '',
        category  TEXT    DEFAULT '',
        down_date TEXT    DEFAULT '',
        hours     TEXT    DEFAULT '',
        cost      REAL    DEFAULT 0,
        status    TEXT    DEFAULT 'Ongoing',
        notes     TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS maint_mechanic (
        id     SERIAL PRIMARY KEY,
        name   TEXT    NOT NULL,
        trade  TEXT    DEFAULT '',
        shift  TEXT    DEFAULT '',
        phone  TEXT    DEFAULT '',
        status TEXT    DEFAULT 'Active',
        notes  TEXT    DEFAULT ''
    )""",

    # --------------------------------------------------------------- Marketing
    """CREATE TABLE IF NOT EXISTS marketing_campaign (
        id         SERIAL PRIMARY KEY,
        name       TEXT    NOT NULL,
        channel    TEXT    DEFAULT '',
        objective  TEXT    DEFAULT '',
        owner      TEXT    DEFAULT '',
        start_date TEXT    DEFAULT '',
        end_date   TEXT    DEFAULT '',
        budget     REAL    DEFAULT 0,
        status     TEXT    DEFAULT 'Planned',
        notes      TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS marketing_lead (
        id            SERIAL PRIMARY KEY,
        name          TEXT    NOT NULL,
        company       TEXT    DEFAULT '',
        email         TEXT    DEFAULT '',
        source        TEXT    DEFAULT '',
        owner         TEXT    DEFAULT '',
        captured_date TEXT    DEFAULT '',
        status        TEXT    DEFAULT 'New',
        notes         TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS marketing_research (
        id             SERIAL PRIMARY KEY,
        title          TEXT    NOT NULL,
        research_type  TEXT    DEFAULT '',
        description    TEXT    DEFAULT '',
        owner          TEXT    DEFAULT '',
        start_date     DATE,
        end_date       DATE,
        status         TEXT    DEFAULT 'Planned',
        findings       TEXT    DEFAULT '',
        budget         REAL    DEFAULT 0,
        notes          TEXT    DEFAULT '',
        created_by     TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS marketing_content (
        id           SERIAL PRIMARY KEY,
        title        TEXT    NOT NULL,
        content_type TEXT    DEFAULT '',
        channel      TEXT    DEFAULT '',
        author       TEXT    DEFAULT '',
        due_date     TEXT    DEFAULT '',
        publish_date TEXT    DEFAULT '',
        status       TEXT    DEFAULT 'Draft',
        notes        TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS marketing_analytics (
        id            SERIAL PRIMARY KEY,
        metric        TEXT    NOT NULL,
        campaign      TEXT    DEFAULT '',
        channel       TEXT    DEFAULT '',
        target        TEXT    DEFAULT '',
        actual        TEXT    DEFAULT '',
        measured_date TEXT    DEFAULT '',
        status        TEXT    DEFAULT 'On Track',
        notes         TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS marketing_budget (
        id           SERIAL PRIMARY KEY,
        item         TEXT    NOT NULL,
        campaign     TEXT    DEFAULT '',
        category     TEXT    DEFAULT '',
        amount       REAL    DEFAULT 0,
        requested_by TEXT    DEFAULT '',
        request_date TEXT    DEFAULT '',
        status       TEXT    DEFAULT 'Pending',
        notes        TEXT    DEFAULT ''
    )""",

    # -------------------------------------------------------------------- MRP
    """CREATE TABLE IF NOT EXISTS mrp_run (
        id           SERIAL PRIMARY KEY,
        run_date     TEXT,
        horizon_days INTEGER,
        notes        TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mrp_planned_order (
        id             SERIAL PRIMARY KEY,
        run_id         INTEGER NOT NULL REFERENCES mrp_run(id),
        product_id     INTEGER NOT NULL,
        order_type     TEXT,
        qty            REAL,
        need_date      TEXT,
        lead_time_days INTEGER DEFAULT 0,
        status         TEXT    DEFAULT 'suggested',
        released_ref   TEXT
    )""",

    # ------------------------------------------------- Purchase Requisitions
    """CREATE TABLE IF NOT EXISTS purchase_requisition (
        id            SERIAL PRIMARY KEY,
        req_number    TEXT    NOT NULL UNIQUE,
        requester_id  INTEGER,
        dept_id       INTEGER,
        dept_sub_id   INTEGER,
        needed_date   TEXT,
        justification TEXT,
        status        TEXT    DEFAULT 'draft',
        created_date  TEXT,
        po_id         INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS requisition_item (
        id             SERIAL PRIMARY KEY,
        req_id         INTEGER NOT NULL REFERENCES purchase_requisition(id),
        description    TEXT    NOT NULL,
        product_id     INTEGER,
        qty            INTEGER DEFAULT 1,
        est_unit_price REAL    DEFAULT 0.0
    )""",
    """CREATE TABLE IF NOT EXISTS requisition_approval (
        id           SERIAL PRIMARY KEY,
        req_id       INTEGER NOT NULL REFERENCES purchase_requisition(id),
        level        TEXT,
        approver_id  INTEGER,
        decision     TEXT,
        comment      TEXT,
        decided_date TEXT
    )""",

    # -------------------------------------------------------------------- QA
    """CREATE TABLE IF NOT EXISTS qa_ncr (
        id            SERIAL PRIMARY KEY,
        title         TEXT    NOT NULL,
        source        TEXT    DEFAULT '',
        severity      TEXT    DEFAULT '',
        product       TEXT    DEFAULT '',
        detected_date TEXT    DEFAULT '',
        disposition   TEXT    DEFAULT 'Pending',
        owner         TEXT    DEFAULT '',
        closed_date   TEXT    DEFAULT '',
        status        TEXT    DEFAULT 'Open',
        notes         TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS qa_capa (
        id             SERIAL PRIMARY KEY,
        title          TEXT    NOT NULL,
        capa_type      TEXT    DEFAULT '',
        ncr_ref        TEXT    DEFAULT '',
        owner          TEXT    DEFAULT '',
        due_date       TEXT    DEFAULT '',
        completed_date TEXT    DEFAULT '',
        status         TEXT    DEFAULT 'Open',
        action_plan    TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS qa_audit (
        id             SERIAL PRIMARY KEY,
        title          TEXT    NOT NULL,
        audit_type     TEXT    DEFAULT '',
        auditor        TEXT    DEFAULT '',
        scheduled_date TEXT    DEFAULT '',
        completed_date TEXT    DEFAULT '',
        result         TEXT    DEFAULT '',
        status         TEXT    DEFAULT 'Scheduled',
        findings       TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS qa_supplier (
        id         SERIAL PRIMARY KEY,
        supplier   TEXT    NOT NULL,
        material   TEXT    DEFAULT '',
        rating     TEXT    DEFAULT '',
        ppm        TEXT    DEFAULT '',
        last_audit TEXT    DEFAULT '',
        status     TEXT    DEFAULT 'Pending',
        notes      TEXT    DEFAULT ''
    )""",

    # ------------------------------------------------------------------ Risk
    """CREATE TABLE IF NOT EXISTS risk_assessment (
        id            SERIAL PRIMARY KEY,
        title         TEXT    NOT NULL,
        category      TEXT    DEFAULT '',
        likelihood    TEXT    DEFAULT '',
        impact        TEXT    DEFAULT '',
        risk_level    TEXT    DEFAULT '',
        owner         TEXT    DEFAULT '',
        assessed_date TEXT    DEFAULT '',
        status        TEXT    DEFAULT 'Identified',
        notes         TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS risk_register (
        id          SERIAL PRIMARY KEY,
        risk        TEXT    NOT NULL,
        category    TEXT    DEFAULT '',
        severity    TEXT    DEFAULT '',
        response    TEXT    DEFAULT '',
        owner       TEXT    DEFAULT '',
        target_date TEXT    DEFAULT '',
        status      TEXT    DEFAULT 'Open',
        mitigation  TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS risk_insurance (
        id          SERIAL PRIMARY KEY,
        policy      TEXT    NOT NULL,
        insurer     TEXT    DEFAULT '',
        policy_type TEXT    DEFAULT '',
        coverage    REAL    DEFAULT 0,
        premium     REAL    DEFAULT 0,
        start_date  TEXT    DEFAULT '',
        end_date    TEXT    DEFAULT '',
        status      TEXT    DEFAULT 'Active',
        notes       TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS risk_continuity (
        id          SERIAL PRIMARY KEY,
        plan        TEXT    NOT NULL,
        scope       TEXT    DEFAULT '',
        criticality TEXT    DEFAULT '',
        owner       TEXT    DEFAULT '',
        last_tested TEXT    DEFAULT '',
        next_test   TEXT    DEFAULT '',
        status      TEXT    DEFAULT 'Draft',
        notes       TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS risk_audit (
        id             SERIAL PRIMARY KEY,
        audit          TEXT    NOT NULL,
        framework      TEXT    DEFAULT '',
        auditor        TEXT    DEFAULT '',
        scheduled_date TEXT    DEFAULT '',
        completed_date TEXT    DEFAULT '',
        finding        TEXT    DEFAULT '',
        status         TEXT    DEFAULT 'Scheduled',
        notes          TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS risk_kri (
        id            SERIAL PRIMARY KEY,
        indicator     TEXT    NOT NULL,
        category      TEXT    DEFAULT '',
        threshold     TEXT    DEFAULT '',
        current_value TEXT    DEFAULT '',
        owner         TEXT    DEFAULT '',
        measured_date TEXT    DEFAULT '',
        status        TEXT    DEFAULT 'Normal',
        notes         TEXT    DEFAULT ''
    )""",

    # ------------------------------------------------------------------ Sales
    """CREATE TABLE IF NOT EXISTS sales_quote (
        id          SERIAL PRIMARY KEY,
        customer    TEXT    NOT NULL,
        description TEXT    DEFAULT '',
        amount      REAL    DEFAULT 0,
        owner       TEXT    DEFAULT '',
        quote_date  TEXT    DEFAULT '',
        valid_until TEXT    DEFAULT '',
        status      TEXT    DEFAULT 'Draft',
        notes       TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS sales_customer (
        id      SERIAL PRIMARY KEY,
        name    TEXT    NOT NULL,
        contact TEXT    DEFAULT '',
        email   TEXT    DEFAULT '',
        phone   TEXT    DEFAULT '',
        segment TEXT    DEFAULT '',
        region  TEXT    DEFAULT '',
        owner   TEXT    DEFAULT '',
        status  TEXT    DEFAULT 'Prospect',
        notes   TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS sales_target (
        id      SERIAL PRIMARY KEY,
        rep     TEXT    NOT NULL,
        period  TEXT    DEFAULT '',
        target  REAL    DEFAULT 0,
        actual  REAL    DEFAULT 0,
        region  TEXT    DEFAULT '',
        status  TEXT    DEFAULT 'On Track',
        notes   TEXT    DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS sales_commission (
        id           SERIAL PRIMARY KEY,
        rep          TEXT    NOT NULL,
        period       TEXT    DEFAULT '',
        plan_id      INTEGER,
        sale_amount  REAL    DEFAULT 0,
        commission   REAL    DEFAULT 0,
        status       TEXT    DEFAULT 'Pending',
        notes        TEXT    DEFAULT '',
        created_by   TEXT    DEFAULT '',
        created_date TEXT    DEFAULT ''
    )""",

    # ------------------------------------------------------------ Time / HR
    """CREATE TABLE IF NOT EXISTS time_off_request (
        id           SERIAL PRIMARY KEY,
        people_id    INTEGER NOT NULL,
        request_date TEXT    NOT NULL,
        start_date   TEXT    NOT NULL,
        end_date     TEXT    NOT NULL,
        request_type TEXT    DEFAULT 'Vacation',
        status       TEXT    DEFAULT 'pending',
        notes        TEXT    DEFAULT ''
    )""",

    # ---------------------------------------------------------- Legacy / misc
    """CREATE TABLE IF NOT EXISTS tax (
        id      INTEGER,
        state   TEXT,
        percent INTEGER
    )""",
]


def main():
    conn = get_db_connection()
    created = []
    skipped = []

    for sql in STATEMENTS:
        # Extract table name for reporting
        name = sql.strip().split()[5]
        try:
            conn.execute(sql)
            conn.commit()
            created.append(name)
            print(f"  OK  {name}")
        except Exception as exc:
            conn._conn.rollback()
            skipped.append(name)
            print(f"  !!  {name}: {exc}")

    conn.close()
    print(f"\nDone — {len(created)} created, {len(skipped)} failed.")


if __name__ == "__main__":
    main()
