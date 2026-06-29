"""seed_sample_marketing.py — sample Marketing data.

Covers: campaigns, leads, content, ads, and market research.
All rows are tagged so they can be removed without touching real data.

Usage::

    python -m manufacturing.seeds.seed_sample_marketing            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_marketing --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_marketing --remove    # remove only
"""

import argparse
from datetime import date, timedelta

from ..db_pg import get_db_connection

TAG = "SMPL-MKT-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marketing_campaign (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            channel TEXT DEFAULT '',
            objective TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            start_date DATE,
            end_date DATE,
            budget REAL DEFAULT 0,
            status TEXT DEFAULT 'Planned',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marketing_lead (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            company TEXT DEFAULT '',
            email TEXT DEFAULT '',
            source TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            captured_date DATE,
            status TEXT DEFAULT 'New',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marketing_content (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content_type TEXT DEFAULT '',
            channel TEXT DEFAULT '',
            author TEXT DEFAULT '',
            due_date DATE,
            publish_date DATE,
            status TEXT DEFAULT 'Draft',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marketing_ad (
            id SERIAL PRIMARY KEY,
            name TEXT DEFAULT '',
            channel TEXT DEFAULT '',
            campaign_name TEXT DEFAULT '',
            budget REAL DEFAULT 0,
            spend REAL DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            start_date DATE,
            end_date DATE,
            status TEXT DEFAULT 'Draft',
            owner TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marketing_research (
            id SERIAL PRIMARY KEY,
            title TEXT DEFAULT '',
            research_type TEXT DEFAULT '',
            description TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            start_date DATE,
            end_date DATE,
            status TEXT DEFAULT 'Planned',
            findings TEXT DEFAULT '',
            budget REAL DEFAULT 0,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("ALTER TABLE marketing_research ADD COLUMN IF NOT EXISTS created_by TEXT DEFAULT ''")
    conn.commit()


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

CAMPAIGNS = [
    # (name, channel, objective, owner, start_ago, end_offset, budget, status)
    (f"{TAG}Summer Product Launch 2026",     "Email",      "Launch",    "Priya Nair",   -45,  45,   18000, "Active"),
    (f"{TAG}Trade Show Spring Circuit",      "Event",      "Lead Gen",  "Marco Reyes",  -90,  -30,  32000, "Completed"),
    (f"{TAG}Q3 LinkedIn Brand Awareness",    "Social",     "Awareness", "Priya Nair",   -15,  75,    9500, "Active"),
    (f"{TAG}Google Search — Valve Parts",    "Search",     "Conversion","Marco Reyes",  -30,  60,   14000, "Active"),
    (f"{TAG}Partner Newsletter Co-marketing","Email",      "Lead Gen",  "Priya Nair",   -60,  -15,   5500, "Completed"),
    (f"{TAG}Product Webinar Series Q2",      "Webinar",    "Retention", "Marco Reyes",  -20,  10,    7200, "Active"),
    (f"{TAG}Holiday Promo Direct Mail",      "Direct Mail","Conversion","Priya Nair",    30,  90,   11000, "Planned"),
    (f"{TAG}Industry Expo Q4",               "Event",      "Lead Gen",  "Marco Reyes",  60,   120,  28000, "Planned"),
]


def _seed_campaigns(conn):
    for name, channel, objective, owner, start_ago, end_off, budget, status in CAMPAIGNS:
        if conn.execute("SELECT 1 FROM marketing_campaign WHERE name=%s", (name,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO marketing_campaign"
            " (name, channel, objective, owner, start_date, end_date, budget, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Sample data')",
            (name, channel, objective, owner, _d(start_ago), _d(start_ago + end_off),
             budget, status),
        )
    conn.commit()


def _remove_campaigns(conn):
    conn.execute("DELETE FROM marketing_campaign WHERE name LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

LEADS = [
    # (name, company, email, source, owner, captured_ago, status)
    ("Daniel Park", "Summit Fab", "d.park@summit.example", "Event", "Priya Nair", -5, "New"),
    ("Rachel Cho", "Pacific Tools Inc.", "r.cho@pactools.example", "Web", "Marco Reyes", -12, "Contacted"),
    ("Omar Hassan", "NW Manufacturing", "o.hassan@nwmfg.example", "Ad", "Priya Nair", -3, "New"),
    ("Tanya Birch", "BlueRidge Systems", "t.birch@blueridge.example",
     "Referral", "Marco Reyes", -20, "Qualified"),
    ("Chen Wei", "Inova Parts", "c.wei@inovaparts.example", "Social", "Priya Nair", -8, "Contacted"),
    ("Fatima Al-Said", "Gulf Industrial", "f.alsaid@gulfindu.example",
     "Event", "Marco Reyes", -45, "Converted"),
    ("Greg Nelson", "Lakeside Assembly", "g.nelson@lakeside.example",
     "Partner", "Priya Nair", -60, "Nurturing"),
    ("Sandra Lee", "Coastal Precision", "s.lee@coastalprec.example",
     "Cold Outreach", "Marco Reyes", -90, "Lost"),
    ("Victor Osei", "Accra Engineering", "v.osei@accra-eng.example", "Social", "Priya Nair", -1, "New"),
    ("Hannah Brandt", "Rhine Components", "h.brandt@rhinecomp.example",
     "Referral", "Marco Reyes", -7, "Qualified"),
]


def _seed_leads(conn):
    for name, company, email, source, owner, captured_ago, status in LEADS:
        if conn.execute("SELECT 1 FROM marketing_lead WHERE email=%s", (email,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO marketing_lead"
            " (name, company, email, source, owner, captured_date, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data')",
            (name, company, email, source, owner, _d(captured_ago), status),
        )
    conn.commit()


def _remove_leads(conn):
    conn.execute("DELETE FROM marketing_lead WHERE notes='Sample data'")
    conn.commit()


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

CONTENT = [
    # (title, content_type, channel, author, due_ago, pub_ago, status)
    (f"{TAG}5 Ways to Extend Valve Life", "Blog", "Email", "Priya Nair", -30, -28, "Published"),
    (f"{TAG}Precision Parts Buyer's Guide 2026",
     "Whitepaper", "Content", "Marco Reyes", -20, -15, "Published"),
    (f"{TAG}Summer Launch — Social Post Series",
     "Social Post", "Social", "Priya Nair", -10, -8, "Published"),
    (f"{TAG}Webinar Slide Deck — Q2", "Video", "Webinar", "Marco Reyes", -5, -3, "Published"),
    (f"{TAG}Customer Success Story — Apex Mfg.",
     "Case Study", "Email", "Priya Nair", 5, None, "In Review"),
    (f"{TAG}Q3 Email Newsletter Draft", "Email", "Email", "Marco Reyes", 10, None, "Draft"),
    (f"{TAG}Product Comparison Infographic",
     "Infographic", "Social", "Priya Nair", 15, None, "Draft"),
    (f"{TAG}Holiday Promo Landing Page",
     "Landing Page", "Display", "Marco Reyes", 25, None, "Draft"),
    (f"{TAG}Industry Expo Ad Copy", "Ad Copy", "Display", "Priya Nair", 40, None, "Draft"),
]


def _seed_content(conn):
    for title, ctype, channel, author, due_ago, pub_ago, status in CONTENT:
        if conn.execute("SELECT 1 FROM marketing_content WHERE title=%s", (title,)).fetchone():
            continue
        pub = _d(pub_ago) if pub_ago is not None else None
        conn.execute(
            "INSERT INTO marketing_content"
            " (title, content_type, channel, author, due_date, publish_date, status, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'Sample data')",
            (title, ctype, channel, author, _d(due_ago), pub, status),
        )
    conn.commit()


def _remove_content(conn):
    conn.execute("DELETE FROM marketing_content WHERE title LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Ads
# ---------------------------------------------------------------------------

ADS = [
    # (name, channel, campaign_name, budget, spend, impressions,
    #  clicks, conv, start_ago, end_off, status, owner)
    (f"{TAG}Google Search — Valve Q2", "Google Ads",
     f"{TAG}Google Search — Valve Parts",
     5000, 3820, 128000, 640, 24, -30, 60, "Active", "Marco Reyes"),
    (f"{TAG}LinkedIn Brand Q3 — Banner", "LinkedIn",
     f"{TAG}Q3 LinkedIn Brand Awareness",
     3000, 1450, 92000, 320, 8, -15, 75, "Active", "Priya Nair"),
    (f"{TAG}Spring Trade Show Display Ad", "Display",
     f"{TAG}Trade Show Spring Circuit",
     2500, 2500, 54000, 180, 12, -90, -30, "Completed", "Marco Reyes"),
    (f"{TAG}Facebook Retargeting — Launch", "Facebook",
     f"{TAG}Summer Product Launch 2026",
     4000, 2100, 76000, 420, 18, -45, 45, "Active", "Priya Nair"),
    (f"{TAG}Email Promo — Partner Co-brand", "Email",
     f"{TAG}Partner Newsletter Co-marketing",
     1500, 1500, 41000, 920, 31, -60, -15, "Completed", "Priya Nair"),
    (f"{TAG}Holiday Display Banner Set", "Display",
     f"{TAG}Holiday Promo Direct Mail",
     3500, 0, 0, 0, 0, 30, 90, "Scheduled", "Marco Reyes"),
]


def _seed_ads(conn):
    for name, channel, campaign, budget, spend, impressions, clicks, conv, start_ago, end_off, status, owner in ADS:
        if conn.execute("SELECT 1 FROM marketing_ad WHERE name=%s", (name,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO marketing_ad"
            " (name, channel, campaign_name, budget, spend, impressions, clicks, conversions,"
            "  start_date, end_date, status, owner, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Sample data')",
            (name, channel, campaign, budget, spend, impressions, clicks, conv,
             _d(start_ago), _d(start_ago + end_off), status, owner),
        )
    conn.commit()


def _remove_ads(conn):
    conn.execute("DELETE FROM marketing_ad WHERE name LIKE %s", (f"{TAG}%",))
    conn.commit()


# ---------------------------------------------------------------------------
# Market Research
# ---------------------------------------------------------------------------

RESEARCH = [
    # (title, research_type, methodology, owner, start_ago, comp_offset, status)
    (f"{TAG}Q2 Customer Satisfaction Survey", "Survey",
     "Online survey via email to all Q1 customers",
     "Priya Nair", -45, -15, "Completed"),
    (f"{TAG}Competitor Pricing Analysis 2026", "Competitor Analysis",
     "Benchmark pricing against top 3 competitors",
     "Marco Reyes", -60, -20, "Completed"),
    (f"{TAG}New Market — Aerospace Segment", "Market Trend",
     "Secondary research + interviews with aerospace buyers",
     "Priya Nair", -30, None, "In Progress"),
    (f"{TAG}Trade Show Lead Quality A/B Test", "A/B Test",
     "Compare lead conversion from Spring vs Fall trade shows",
     "Marco Reyes", -90, -60, "Completed"),
    (f"{TAG}Product Naming Focus Group", "Focus Group",
     "3 focus groups, 7 participants each, recorded sessions",
     "Priya Nair", -10, None, "In Progress"),
    (f"{TAG}Q3 Market Sizing — Southeast US", "Market Trend",
     "Industry reports + CRM deal data analysis",
     "Marco Reyes", 15, None, "Planned"),
]


def _seed_research(conn):
    for title, rtype, methodology, owner, start_ago, comp_off, status in RESEARCH:
        if conn.execute("SELECT 1 FROM marketing_research WHERE title=%s", (title,)).fetchone():
            continue
        comp = _d(comp_off) if comp_off is not None else None
        conn.execute(
            "INSERT INTO marketing_research"
            " (title, research_type, methodology, owner, start_date, completed_date, status, findings, created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'','seed')",
            (title, rtype, methodology, owner, _d(start_ago), comp, status),
        )
    conn.commit()


def _remove_research(conn):
    conn.execute("DELETE FROM marketing_research WHERE created_by='seed'")
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(conn):
    _ensure_tables(conn)
    _seed_campaigns(conn)
    _seed_leads(conn)
    _seed_content(conn)
    _seed_ads(conn)
    _seed_research(conn)
    print("Marketing sample data seeded.")


def remove(conn):
    _remove_ads(conn)
    _remove_research(conn)
    _remove_content(conn)
    _remove_leads(conn)
    _remove_campaigns(conn)
    print("Marketing sample data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Marketing sample data")
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


