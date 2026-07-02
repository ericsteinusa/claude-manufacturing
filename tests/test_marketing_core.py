"""Tests for manufacturing/marketing_core.py — pure unit tests, no Qt, no DB."""

from unittest.mock import MagicMock

from manufacturing.marketing_core import (
    get_marketing_dashboard,
    list_campaigns, get_campaign, create_campaign, update_campaign,
    list_leads, get_lead, create_lead, update_lead,
    list_content, get_content_item, create_content, update_content,
    CHANNELS, OBJECTIVES, CAMPAIGN_STATUSES,
    LEAD_SOURCES, LEAD_STATUSES, CONTENT_TYPES, CONTENT_STATUSES,
)

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
        MagicMock(fetchone=MagicMock(return_value=cs)),
        MagicMock(fetchone=MagicMock(return_value=ls)),
        MagicMock(fetchone=MagicMock(return_value=ct)),
        MagicMock(fetchall=MagicMock(return_value=rec)),
    ]
    return c


def _list_conn(rows):
    c = MagicMock()
    c.execute.return_value.fetchall.return_value = rows
    return c


# ---------------------------------------------------------------------------
# Dashboard return structure
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
# Dashboard campaign stats
# ---------------------------------------------------------------------------

def test_campaigns_total():
    assert get_marketing_dashboard(_conn())['campaigns']['total'] == 12

def test_campaigns_active():
    assert get_marketing_dashboard(_conn())['campaigns']['active'] == 4

def test_campaigns_planned():
    assert get_marketing_dashboard(_conn())['campaigns']['planned'] == 3


# ---------------------------------------------------------------------------
# Dashboard lead stats
# ---------------------------------------------------------------------------

def test_leads_total():
    assert get_marketing_dashboard(_conn())['leads']['total'] == 50

def test_leads_new_count():
    assert get_marketing_dashboard(_conn())['leads']['new_count'] == 10

def test_leads_qualified():
    assert get_marketing_dashboard(_conn())['leads']['qualified'] == 8


# ---------------------------------------------------------------------------
# Dashboard content stats
# ---------------------------------------------------------------------------

def test_content_total():
    assert get_marketing_dashboard(_conn())['content']['total'] == 30

def test_content_draft():
    assert get_marketing_dashboard(_conn())['content']['draft'] == 7

def test_content_published():
    assert get_marketing_dashboard(_conn())['content']['published'] == 20


# ---------------------------------------------------------------------------
# Dashboard recent_campaigns
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
# Dashboard SQL sanity
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_campaign_statuses_has_active():
    assert 'Active' in CAMPAIGN_STATUSES

def test_campaign_statuses_has_planned():
    assert 'Planned' in CAMPAIGN_STATUSES

def test_campaign_statuses_has_cancelled():
    assert 'Cancelled' in CAMPAIGN_STATUSES

def test_channels_has_email():
    assert 'Email' in CHANNELS

def test_channels_has_social():
    assert 'Social' in CHANNELS

def test_objectives_has_awareness():
    assert 'Awareness' in OBJECTIVES

def test_lead_statuses_has_new():
    assert 'New' in LEAD_STATUSES

def test_lead_statuses_has_converted():
    assert 'Converted' in LEAD_STATUSES

def test_lead_sources_has_web():
    assert 'Web' in LEAD_SOURCES

def test_content_statuses_has_draft():
    assert 'Draft' in CONTENT_STATUSES

def test_content_statuses_has_published():
    assert 'Published' in CONTENT_STATUSES

def test_content_types_has_blog():
    assert 'Blog' in CONTENT_TYPES


# ---------------------------------------------------------------------------
# list_campaigns
# ---------------------------------------------------------------------------

def test_list_campaigns_returns_list():
    assert isinstance(list_campaigns(_list_conn([])), list)

def test_list_campaigns_status_filter():
    c = _list_conn([])
    list_campaigns(c, status='Active')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Active' in params

def test_list_campaigns_channel_filter():
    c = _list_conn([])
    list_campaigns(c, channel='Email')
    sql, params = c.execute.call_args[0]
    assert 'channel' in sql and 'Email' in params

def test_list_campaigns_search_filter():
    c = _list_conn([])
    list_campaigns(c, search='spring')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('spring' in str(p) for p in params)

def test_list_campaigns_no_filter_no_params():
    c = _list_conn([])
    list_campaigns(c)
    _, params = c.execute.call_args[0]
    assert params == []

def test_list_campaigns_converts_to_dicts():
    row = {'id': 1, 'name': 'Q1 Push', 'channel': 'Email', 'status': 'Active',
           'objective': 'Lead Gen', 'owner': 'Alice', 'start_date': '', 'end_date': '', 'budget': 0}
    assert list_campaigns(_list_conn([row]))[0]['name'] == 'Q1 Push'


# ---------------------------------------------------------------------------
# get_campaign
# ---------------------------------------------------------------------------

def test_get_campaign_returns_dict():
    row = {'id': 1, 'name': 'Spring Sale', 'status': 'Active'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_campaign(c, 1) == row

def test_get_campaign_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_campaign(c, 99) is None


# ---------------------------------------------------------------------------
# create_campaign
# ---------------------------------------------------------------------------

def test_create_campaign_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [7]
    result = create_campaign(c, 'Summer Push', 'Email', 'Awareness', 'Alice',
                             '2026-06-01', '2026-08-31', 10000.0, 'Planned', '')
    assert result == 7

def test_create_campaign_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_campaign(c, 'Test', 'Social', 'Lead Gen', '', '', '', 0, 'Planned', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'marketing_campaign' in sql


# ---------------------------------------------------------------------------
# update_campaign
# ---------------------------------------------------------------------------

def test_update_campaign_builds_set_clause():
    c = MagicMock()
    update_campaign(c, 1, status='Active', channel='Social')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE marketing_campaign' in sql and 'status' in sql

def test_update_campaign_ignores_unknown_fields():
    c = MagicMock()
    update_campaign(c, 1, bogus='x')
    c.execute.assert_not_called()

def test_update_campaign_noop_when_no_fields():
    c = MagicMock()
    update_campaign(c, 1)
    c.execute.assert_not_called()


# ---------------------------------------------------------------------------
# list_leads
# ---------------------------------------------------------------------------

def test_list_leads_returns_list():
    assert isinstance(list_leads(_list_conn([])), list)

def test_list_leads_status_filter():
    c = _list_conn([])
    list_leads(c, status='Qualified')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Qualified' in params

def test_list_leads_source_filter():
    c = _list_conn([])
    list_leads(c, source='Web')
    sql, params = c.execute.call_args[0]
    assert 'source' in sql and 'Web' in params

def test_list_leads_search_filter():
    c = _list_conn([])
    list_leads(c, search='acme')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('acme' in str(p) for p in params)

def test_list_leads_ordered_by_captured_date():
    c = _list_conn([])
    list_leads(c)
    sql, _ = c.execute.call_args[0]
    assert 'captured_date' in sql


# ---------------------------------------------------------------------------
# get_lead
# ---------------------------------------------------------------------------

def test_get_lead_returns_dict():
    row = {'id': 3, 'name': 'Jane Doe', 'status': 'New'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_lead(c, 3) == row

def test_get_lead_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_lead(c, 99) is None


# ---------------------------------------------------------------------------
# create_lead
# ---------------------------------------------------------------------------

def test_create_lead_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [4]
    result = create_lead(c, 'Jane Doe', 'Acme', 'jane@acme.com', 'Web',
                         'Alice', '2026-06-01', 'New', '')
    assert result == 4

def test_create_lead_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_lead(c, 'Lead', '', '', 'Web', '', '', 'New', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'marketing_lead' in sql


# ---------------------------------------------------------------------------
# update_lead
# ---------------------------------------------------------------------------

def test_update_lead_builds_set_clause():
    c = MagicMock()
    update_lead(c, 1, status='Qualified', owner='Bob')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE marketing_lead' in sql and 'status' in sql

def test_update_lead_ignores_unknown_fields():
    c = MagicMock()
    update_lead(c, 1, bogus='x')
    c.execute.assert_not_called()

def test_update_lead_noop_when_no_fields():
    c = MagicMock()
    update_lead(c, 1)
    c.execute.assert_not_called()


# ---------------------------------------------------------------------------
# list_content
# ---------------------------------------------------------------------------

def test_list_content_returns_list():
    assert isinstance(list_content(_list_conn([])), list)

def test_list_content_status_filter():
    c = _list_conn([])
    list_content(c, status='Published')
    sql, params = c.execute.call_args[0]
    assert 'status' in sql and 'Published' in params

def test_list_content_type_filter():
    c = _list_conn([])
    list_content(c, content_type='Blog')
    sql, params = c.execute.call_args[0]
    assert 'content_type' in sql and 'Blog' in params

def test_list_content_search_filter():
    c = _list_conn([])
    list_content(c, search='launch')
    sql, params = c.execute.call_args[0]
    assert 'ILIKE' in sql and any('launch' in str(p) for p in params)

def test_list_content_ordered_by_due_date():
    c = _list_conn([])
    list_content(c)
    sql, _ = c.execute.call_args[0]
    assert 'due_date' in sql


# ---------------------------------------------------------------------------
# get_content_item
# ---------------------------------------------------------------------------

def test_get_content_item_returns_dict():
    row = {'id': 2, 'title': 'How We Work', 'status': 'Draft'}
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = row
    assert get_content_item(c, 2) == row

def test_get_content_item_returns_none_when_missing():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = None
    assert get_content_item(c, 99) is None


# ---------------------------------------------------------------------------
# create_content
# ---------------------------------------------------------------------------

def test_create_content_returns_id():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [6]
    result = create_content(c, 'Intro Blog', 'Blog', 'Email', 'Alice',
                            '2026-07-01', '', 'Draft', '')
    assert result == 6

def test_create_content_uses_insert():
    c = MagicMock()
    c.execute.return_value.fetchone.return_value = [1]
    create_content(c, 'Post', 'Blog', 'Social', '', '', '', 'Draft', '')
    sql = c.execute.call_args[0][0]
    assert 'INSERT' in sql and 'marketing_content' in sql


# ---------------------------------------------------------------------------
# update_content
# ---------------------------------------------------------------------------

def test_update_content_builds_set_clause():
    c = MagicMock()
    update_content(c, 1, status='Published', publish_date='2026-07-15')
    sql = c.execute.call_args[0][0]
    assert 'UPDATE marketing_content' in sql and 'status' in sql

def test_update_content_ignores_unknown_fields():
    c = MagicMock()
    update_content(c, 1, bogus='x')
    c.execute.assert_not_called()

def test_update_content_noop_when_no_fields():
    c = MagicMock()
    update_content(c, 1)
    c.execute.assert_not_called()
