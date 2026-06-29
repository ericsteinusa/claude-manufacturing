"""seed_sample_cs.py — sample Customer Service data.

Covers: CS tickets (calls2), improvement plans, returns/refunds,
knowledge base articles, and customer surveys with responses.
All rows are tagged so they can be removed without touching real data.

Note: calls2.customer_id is left NULL because CS tickets can exist
without a linked customer record.

Usage::

    python -m manufacturing.seeds.seed_sample_cs            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_cs --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_cs --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-CS-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
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
    """)
    conn.execute("""
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
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_return (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER,
            return_date TEXT,
            reason TEXT DEFAULT '',
            items_returned TEXT DEFAULT '',
            refund_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_kb_article (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT DEFAULT '',
            content TEXT DEFAULT '',
            author TEXT DEFAULT '',
            published_date TEXT,
            status TEXT DEFAULT 'Draft',
            tags TEXT DEFAULT '',
            view_count INTEGER DEFAULT 0,
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_survey (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            survey_type TEXT DEFAULT 'CSAT',
            status TEXT DEFAULT 'Draft',
            start_date TEXT,
            end_date TEXT,
            response_count INTEGER DEFAULT 0,
            avg_score REAL,
            created_by TEXT DEFAULT '',
            created_date TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cs_survey_response (
            id SERIAL PRIMARY KEY,
            survey_id INTEGER NOT NULL,
            customer_id INTEGER,
            score INTEGER,
            comments TEXT DEFAULT '',
            response_date TEXT
        )
    """)
    for tbl in ("calls2", "cs_improvement_plan"):
        conn.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    conn.commit()


# ---------------------------------------------------------------------------
# CS Tickets (calls2)
# ---------------------------------------------------------------------------

TICKETS = [
    # (call_ago, call_time, call_desc, comments, comp_ago, comp_time, completed)
    (-18, "09:15", "Customer unable to track order — shipment delayed 5 days",
     "Contacted shipping; updated customer with new ETA.", -17, "10:30", 1),
    (-14, "14:00", "Wrong item shipped — received shaft collar instead of valve assembly",
     "Issued return label; replacement shipped same day.", -13, "15:45", 1),
    (-10, "11:30", "Invoice shows incorrect unit price from quote",
     "Finance team corrected invoice; resent to customer.", -9, "13:00", 1),
    (-7, "08:45", "Product arrived damaged — packaging crushed in transit",
     "Filed freight claim; replacement ordered.", -6, "09:20", 1),
    (-5, "16:00", "Customer requesting technical specs for valve assembly batch",
     "", 0, "", 0),
    (-3, "10:00", "Complaint: sales rep not returning calls",
     "Escalated to Sales Manager for follow-up.", 0, "", 0),
    (-1, "14:30", "Requesting early delivery for emergency production run",
     "Coordinating with Production to expedite order.", 0, "", 0),
    (-15, "13:00", "Customer wants to modify existing blanket order quantities",
     "Updated order per customer request; confirmed pricing.", -14, "14:00", 1),
    (-20, "09:00", "Defective bearing — premature failure after 30 days",
     "Sent warranty replacement; engineering notified.", -19, "10:30", 1),
    (-30, "10:30", "Billing dispute — charged twice for same order",
     "Accounting confirmed duplicate; credit memo issued.", -29, "11:00", 1),
    (-2, "15:00", "Customer cannot find product documentation on portal",
     "", 0, "", 0),
    (-8, "11:00", "Request for custom part modification — non-standard thread",
     "Forwarded to Engineering for feasibility review.", -7, "12:15", 1),
]


def _seed_tickets(conn):
    for call_ago, call_time, call_desc, comments, comp_ago, comp_time, completed in TICKETS:
        if conn.execute(
            "SELECT 1 FROM calls2 WHERE call=%s AND created_by='seed'",
            (call_desc,)
        ).fetchone():
            continue
        comp_date = _d(comp_ago) if completed else ''
        conn.execute(
            "INSERT INTO calls2"
            " (customer_id, call, call_date, call_time,"
            "  completion_date, completion_time, comments_box, completion_box, created_by)"
            " VALUES (NULL,%s,%s,%s,%s,%s,%s,%s,'seed')",
            (call_desc, _d(call_ago), call_time, comp_date, comp_time,
             comments, 1 if completed else 0),
        )
    conn.commit()


def _remove_tickets(conn):
    conn.execute("DELETE FROM calls2 WHERE created_by='seed'")
    conn.commit()


# ---------------------------------------------------------------------------
# Improvement Plans
# ---------------------------------------------------------------------------

PLANS = [
    # (title, description, owner, due_offset, status)
    (f"{TAG}Reduce Average Resolution Time",
     "Target: reduce avg ticket resolution from 4.2 days to 2.5 days by end of Q3.",
     "Rachel Green", 60, "In Progress"),
    (f"{TAG}Implement Self-Service Knowledge Base",
     "Launch customer-facing KB portal to reduce repeat inquiries by 30%.",
     "Rachel Green", 90, "Open"),
    (f"{TAG}Escalation Response SLA Update",
     "Revise escalation SLA from 48hrs to 24hrs for critical-priority tickets.",
     "Rachel Green", 30, "Open"),
    (f"{TAG}CS Staff Cross-Training Program",
     "Cross-train all CS reps on Tier-2 technical troubleshooting to reduce referrals.",
     "Rachel Green", 120, "Open"),
    (f"{TAG}Post-Call Survey Rollout",
     "Deploy automated CSAT survey after every resolved ticket.",
     "Rachel Green", -15, "Completed"),
]


def _seed_plans(conn):
    for title, desc, owner, due_off, status in PLANS:
        if conn.execute(
            "SELECT 1 FROM cs_improvement_plan WHERE title=%s", (title,)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO cs_improvement_plan"
            " (title, description, owner, target_date, status, created_date, created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s,'seed')",
            (title, desc, owner, _d(due_off), status, TODAY.isoformat()),
        )
    conn.commit()


def _remove_plans(conn):
    conn.execute("DELETE FROM cs_improvement_plan WHERE title LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Returns & Refunds
# ---------------------------------------------------------------------------

RETURNS = [
    # (return_ago, reason, items_returned, refund_amount, status)
    (-20, "Wrong Item",             "3x Shaft Collar A-200 (returned)",        186.00,  "Refunded"),
    (-15, "Defective",              "1x Bearing 6205 lot — premature failure",  52.50,  "Approved"),
    (-10, "Damaged in Shipping",    "5x Valve Assembly V-100",                1245.00,  "Approved"),
    (-5,  "Not as Described",       "10x M10 Bolt Pack (wrong grade)",           85.00,  "Pending"),
    (-30, "Changed Mind",           "2x Hydraulic Hose kit",                   160.00,  "Refunded"),
    (-45, "Defective",              "1x Custom Fixture CF-204 — dimensional",  880.00,  "Closed"),
    (-2,  "Duplicate Order",        "Full order — customer placed twice",       3200.00, "Pending"),
]


def _seed_returns(conn):
    for ret_ago, reason, items, amount, status in RETURNS:
        if conn.execute(
            "SELECT 1 FROM cs_return WHERE reason=%s AND items_returned=%s AND created_by='seed'",
            (reason, items)
        ).fetchone():
            continue
        conn.execute(
            "INSERT INTO cs_return"
            " (customer_id, return_date, reason, items_returned, refund_amount,"
            "  status, notes, created_by, created_date)"
            " VALUES (NULL,%s,%s,%s,%s,%s,'Sample data','seed',CURRENT_DATE)",
            (_d(ret_ago), reason, items, amount, status),
        )
    conn.commit()


def _remove_returns(conn):
    conn.execute("DELETE FROM cs_return WHERE created_by='seed' AND notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Knowledge Base Articles
# ---------------------------------------------------------------------------

ARTICLES = [
    # (title, category, author, pub_ago, status, tags, view_count)
    (f"{TAG}How to Track Your Order Status", "Shipping", "Rachel Green",
     -30, "Published", "order,tracking,shipping", 142),
    (f"{TAG}Initiating a Return or Exchange", "Returns", "Rachel Green",
     -25, "Published", "return,refund,exchange", 98),
    (f"{TAG}Reading Your Invoice — Common Questions", "Billing", "Rachel Green",
     -20, "Published", "invoice,billing,payment", 73),
    (f"{TAG}Valve Assembly Technical Specifications", "Product", "Rachel Green",
     -15, "Published", "valve,specs,technical,datasheet", 210),
    (f"{TAG}Warranty Policy Overview", "Policy", "Rachel Green",
     -10, "Published", "warranty,defective,replacement", 88),
    (f"{TAG}How to Set Up Your Customer Portal Account", "Account", "Rachel Green",
     -5, "Published", "portal,account,login", 156),
    (f"{TAG}Frequently Asked Questions — Shipping Times", "FAQ", "Rachel Green",
     -3, "Published", "FAQ,shipping,lead time", 44),
    (f"{TAG}Bearing Installation Best Practices", "Technical", "Rachel Green",
     -1, "In Review", "bearing,installation,technical", 0),
    (f"{TAG}Custom Part Request Process", "Product", "Rachel Green",
     3, "Draft", "custom,special,engineering", 0),
]


def _seed_kb(conn):
    for title, cat, author, pub_ago, status, tags, views in ARTICLES:
        if conn.execute("SELECT 1 FROM cs_kb_article WHERE title=%s", (title,)).fetchone():
            continue
        pub = _d(pub_ago) if status == "Published" else None
        conn.execute(
            "INSERT INTO cs_kb_article"
            " (title, category, content, author, published_date, status,"
            "  tags, view_count, created_by, created_date)"
            " VALUES (%s,%s,'',%s,%s,%s,%s,%s,'seed',CURRENT_DATE)",
            (title, cat, author, pub, status, tags, views),
        )
    conn.commit()


def _remove_kb(conn):
    conn.execute("DELETE FROM cs_kb_article WHERE title LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Surveys + Responses
# ---------------------------------------------------------------------------

SURVEYS = [
    # (title, description, survey_type, status, start_ago, end_offset)
    (f"{TAG}Q1 Customer Satisfaction Survey", "Post-purchase CSAT — Q1 closed orders",
     "CSAT", "Closed", -90, -60),
    (f"{TAG}Q2 Net Promoter Score", "NPS survey sent to all active accounts",
     "NPS", "Closed", -45, -15),
    (f"{TAG}Post-Purchase Survey — June", "Automated survey after order completion",
     "Post-Purchase", "Active", -20, 10),
    (f"{TAG}Product Quality Feedback", "Targeted survey for valve assembly buyers",
     "Product", "Draft", -5, 30),
]

SURVEY_RESPONSES = {
    f"{TAG}Q1 Customer Satisfaction Survey": [
        (8,  "Fast shipping, product was exactly as described.", -85),
        (9,  "Excellent quality and on-time delivery.",          -82),
        (6,  "Packaging could be better — minor damage.",        -80),
        (10, "Best supplier we've worked with.",                 -78),
        (7,  "Good product but had to follow up on the order.",  -75),
        (9,  "Smooth transaction, will order again.",            -72),
    ],
    f"{TAG}Q2 Net Promoter Score": [
        (9,  "Would definitely recommend.",                      -40),
        (8,  "Good quality, competitive pricing.",               -38),
        (10, "Outstanding service and product quality.",         -35),
        (5,  "Delivery was two days late.",                      -33),
        (7,  "Product quality is solid.",                        -30),
        (9,  "Very responsive to our needs.",                    -28),
        (10, "Top-tier supplier.",                               -25),
        (6,  "Pricing is a bit high versus competitors.",        -20),
    ],
}


def _seed_surveys(conn):
    survey_ids = {}
    for title, desc, stype, status, start_ago, end_off in SURVEYS:
        existing = conn.execute("SELECT id FROM cs_survey WHERE title=%s", (title,)).fetchone()
        if existing:
            survey_ids[title] = existing["id"]
            continue
        row = conn.execute(
            "INSERT INTO cs_survey"
            " (title, description, survey_type, status, start_date, end_date,"
            "  response_count, avg_score, created_by, created_date)"
            " VALUES (%s,%s,%s,%s,%s,%s,0,NULL,'seed',CURRENT_DATE) RETURNING id",
            (title, desc, stype, status, _d(start_ago), _d(start_ago + end_off)),
        ).fetchone()
        survey_ids[title] = row["id"]
    conn.commit()

    for title, responses in SURVEY_RESPONSES.items():
        survey_id = survey_ids.get(title)
        if not survey_id:
            continue
        existing = conn.execute(
            "SELECT COUNT(*) FROM cs_survey_response WHERE survey_id=%s", (survey_id,)
        ).fetchone()[0]
        if existing:
            continue
        for score, comment, resp_ago in responses:
            conn.execute(
                "INSERT INTO cs_survey_response (survey_id, customer_id, score, comments, response_date)"
                " VALUES (%s,NULL,%s,%s,%s)",
                (survey_id, score, comment, _d(resp_ago)),
            )
        # Update aggregate on the survey row
        conn.execute(
            "UPDATE cs_survey SET "
            "response_count=(SELECT COUNT(*) FROM cs_survey_response WHERE survey_id=%s), "
            "avg_score=(SELECT ROUND(AVG(score)::numeric,1) FROM cs_survey_response WHERE survey_id=%s) "
            "WHERE id=%s",
            (survey_id, survey_id, survey_id),
        )
    conn.commit()


def _remove_surveys(conn):
    rows = conn.execute(
        "SELECT id FROM cs_survey WHERE title LIKE %s", (f"{TAG}%",)
    ).fetchall()
    for r in rows:
        conn.execute("DELETE FROM cs_survey_response WHERE survey_id=%s", (r["id"],))
    conn.execute("DELETE FROM cs_survey WHERE title LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_tickets(conn)
    _seed_plans(conn)
    _seed_returns(conn)
    _seed_kb(conn)
    _seed_surveys(conn)
    print("Customer Service sample data seeded.")


def remove(conn):
    _remove_surveys(conn)
    _remove_kb(conn)
    _remove_returns(conn)
    _remove_plans(conn)
    _remove_tickets(conn)
    print("Customer Service sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Customer Service sample data")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--reset",  action="store_true", help="Remove then re-add")
    grp.add_argument("--remove", action="store_true", help="Remove only")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        if args.remove:
            remove(conn)
        elif args.reset:
            remove(conn)
            seed(conn)
        else:
            seed(conn)
    finally:
        conn.close()


