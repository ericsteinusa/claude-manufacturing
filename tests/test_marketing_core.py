"""Tests for manufacturing/marketing_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock

from manufacturing.marketing_core import get_marketing_dashboard

_CAMPAIGN_STATS = {'total': 12, 'active': 4, 'planned': 3}
_LEAD_STATS = {'total': 50, 'new_count': 10, 'qualified': 8}
_CONTENT_STATS = {'total': 30, 'draft': 7, 'published': 20}

_CAMPAIGN_ROW = {
    'id': 1, 'name': 'Summer Sale', 'channel': 'Email',
    'objective': 'Brand awareness', 'status': 'Active',
    'start_date': '2026-06-01', 'end_date': '2026-08-31', 'budget': 5000.0,
}


def _conn(campaign_stats=None, lead_stats=None, content_stats=None, recent=None):
    c = MagicMock()
    cs = campaign_stats if campaign_stats is not None else _CAMPAIGN_STATS
    ls = lead_stats if lead_stats is not None else _LEAD_STATS
    ct = content_stats if content_stats is not None else _CONTENT_STATS
    rec = recent if recent is not None else []
    c.execute.side_effect = [
        MagicMock(**{'fetchone.return_value': cs}),
        MagicMock(**{'fetchone.return_value': ls}),
        MagicMock(**{'fetchone.return_value': ct}),
        MagicMock(**{'fetchall.return_value': rec}),
    ]
    return c


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_returns_dict():
    assert isinstance(get_marketing_dashboard(_conn()), dict)


def test_has_campaigns_key():
    assert 'campaigns' in get_marketing_dashboard(_conn())


def test_has_leads_key():
    assert 'leads' in get_marketing_dashboard(_conn())


def test_has_content_key():
    assert 'content' in get_marketing_dashboard(_conn())


def test_has_recent_campaigns_key():
    assert 'recent_campaigns' in get_marketing_dashboard(_conn())


# ---------------------------------------------------------------------------
# campaigns stats
# ---------------------------------------------------------------------------

def test_campaigns_total():
    assert get_marketing_dashboard(_conn())['campaigns']['total'] == 12


def test_campaigns_active():
    assert get_marketing_dashboard(_conn())['campaigns']['active'] == 4


def test_campaigns_planned():
    assert get_marketing_dashboard(_conn())['campaigns']['planned'] == 3


# ---------------------------------------------------------------------------
# leads stats
# ---------------------------------------------------------------------------

def test_leads_total():
    assert get_marketing_dashboard(_conn())['leads']['total'] == 50


def test_leads_new_count():
    assert get_marketing_dashboard(_conn())['leads']['new_count'] == 10


def test_leads_qualified():
    assert get_marketing_dashboard(_conn())['leads']['qualified'] == 8


# ---------------------------------------------------------------------------
# content stats
# ---------------------------------------------------------------------------

def test_content_total():
    assert get_marketing_dashboard(_conn())['content']['total'] == 30


def test_content_draft():
    assert get_marketing_dashboard(_conn())['content']['draft'] == 7


def test_content_published():
    assert get_marketing_dashboard(_conn())['content']['published'] == 20


# ---------------------------------------------------------------------------
# recent_campaigns
# ---------------------------------------------------------------------------

def test_recent_campaigns_is_list():
    result = get_marketing_dashboard(_conn(recent=[_CAMPAIGN_ROW]))
    assert isinstance(result['recent_campaigns'], list)


def test_recent_campaigns_items_are_dicts():
    result = get_marketing_dashboard(_conn(recent=[_CAMPAIGN_ROW]))
    assert isinstance(result['recent_campaigns'][0], dict)


def test_recent_campaigns_have_name():
    result = get_marketing_dashboard(_conn(recent=[_CAMPAIGN_ROW]))
    assert result['recent_campaigns'][0]['name'] == 'Summer Sale'


def test_recent_campaigns_have_status():
    result = get_marketing_dashboard(_conn(recent=[_CAMPAIGN_ROW]))
    assert result['recent_campaigns'][0]['status'] == 'Active'


def test_recent_campaigns_have_budget():
    result = get_marketing_dashboard(_conn(recent=[_CAMPAIGN_ROW]))
    assert result['recent_campaigns'][0]['budget'] == 5000.0


def test_recent_campaigns_empty_when_no_rows():
    assert get_marketing_dashboard(_conn(recent=[]))['recent_campaigns'] == []


# ---------------------------------------------------------------------------
# SQL sanity
# ---------------------------------------------------------------------------

def test_sql_first_query_hits_marketing_campaign():
    c = _conn()
    get_marketing_dashboard(c)
    assert 'marketing_campaign' in c.execute.call_args_list[0][0][0]


def test_sql_second_query_hits_marketing_lead():
    c = _conn()
    get_marketing_dashboard(c)
    assert 'marketing_lead' in c.execute.call_args_list[1][0][0]


def test_sql_third_query_hits_marketing_content():
    c = _conn()
    get_marketing_dashboard(c)
    assert 'marketing_content' in c.execute.call_args_list[2][0][0]


def test_sql_recent_uses_limit_8():
    c = _conn()
    get_marketing_dashboard(c)
    assert 'LIMIT 8' in c.execute.call_args_list[3][0][0]
