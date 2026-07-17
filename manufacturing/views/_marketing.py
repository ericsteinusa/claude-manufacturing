"""Views: marketing domain."""

import json
from datetime import date

from django.shortcuts import render, redirect
from ..db_pg import get_db_connection
from ..auth_decorators import dept_required
from ..log_utils import get_logger
from ..accounts import READ_ONLY_ROLES
from ..csv_export import export_response

from ..marketing_core import (
    get_marketing_dashboard,
    list_campaigns, get_campaign, create_campaign, update_campaign,
    list_leads, get_lead, create_lead, update_lead,
    list_content, get_content_item, create_content, update_content,
    CHANNELS, OBJECTIVES, CAMPAIGN_STATUSES,
    LEAD_SOURCES, LEAD_STATUSES, CONTENT_TYPES, CONTENT_STATUSES,
    list_ads, get_ad, create_ad, update_ad, AD_CHANNELS, AD_STATUSES,
    list_research, get_research_project, create_research, update_research,
    RESEARCH_TYPES, RESEARCH_STATUSES,
    get_analytics_data,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Marketing dashboard
# ---------------------------------------------------------------------------

def _mkt_ctx(request, **extra):
    return {
        'user_email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        **extra,
    }


@dept_required('marketing')
def mkt_dashboard(request):
    with get_db_connection() as conn:
        data = get_marketing_dashboard(conn)

        campaign_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM marketing_campaign
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        campaign_status_json = json.dumps([dict(r) for r in campaign_status_rows])

        campaign_channel_rows = conn.execute("""
            SELECT channel, COUNT(*) AS cnt FROM marketing_campaign
            WHERE channel IS NOT NULL AND channel != ''
            GROUP BY channel ORDER BY cnt DESC
        """).fetchall()
        campaign_channel_json = json.dumps([dict(r) for r in campaign_channel_rows])

        budget_channel_rows = conn.execute("""
            SELECT channel, SUM(budget) AS total_budget FROM marketing_campaign
            WHERE channel IS NOT NULL AND channel != ''
            GROUP BY channel ORDER BY total_budget DESC
        """).fetchall()
        budget_channel_json = json.dumps([dict(r) for r in budget_channel_rows])

        lead_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM marketing_lead
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        lead_status_json = json.dumps([dict(r) for r in lead_status_rows])

        lead_source_rows = conn.execute("""
            SELECT source, COUNT(*) AS cnt FROM marketing_lead
            WHERE source IS NOT NULL AND source != ''
            GROUP BY source ORDER BY cnt DESC
        """).fetchall()
        lead_source_json = json.dumps([dict(r) for r in lead_source_rows])

        content_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM marketing_content
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        content_status_json = json.dumps([dict(r) for r in content_status_rows])

    ctx = _mkt_ctx(request, **data,
                    campaign_status_json=campaign_status_json,
                    campaign_channel_json=campaign_channel_json,
                    budget_channel_json=budget_channel_json,
                    lead_status_json=lead_status_json,
                    lead_source_json=lead_source_json,
                    content_status_json=content_status_json)
    return render(request, 'marketing_dashboard.html', ctx)


@dept_required('marketing')
def mkt_campaign_list(request):
    status_f = request.GET.get('status', '').strip()
    channel_f = request.GET.get('channel', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        campaigns = list_campaigns(conn, status=status_f or None,
                                   channel=channel_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_campaign(
                    conn,
                    name=request.POST.get('name', ''),
                    channel=request.POST.get('channel', ''),
                    objective=request.POST.get('objective', ''),
                    owner=request.POST.get('owner', ''),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    budget=float(request.POST.get('budget', 0) or 0),
                    status=request.POST.get('status', 'Planned'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('mkt_campaign_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                campaigns = list_campaigns(conn, status=status_f or None,
                                           channel=channel_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'mkt_campaigns', [
            ('name', 'Name'), ('channel', 'Channel'), ('objective', 'Objective'),
            ('owner', 'Owner'), ('start_date', 'Start Date'),
            ('end_date', 'End Date'), ('budget', 'Budget'), ('status', 'Status'),
        ], campaigns)

    return render(request, 'mkt_campaign_list.html', _mkt_ctx(
        request, campaigns=campaigns, status_filter=status_f, channel_filter=channel_f,
        search=search, campaign_statuses=CAMPAIGN_STATUSES, channels=CHANNELS,
        objectives=OBJECTIVES, error=error, success=success,
    ))


@dept_required('marketing')
def mkt_campaign_detail(request, campaign_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    campaign = None
    try:
        campaign = get_campaign(conn, campaign_id)
        if not campaign:
            return redirect('mkt_campaign_list')
        if request.method == 'POST' and can_edit:
            try:
                update_campaign(
                    conn, campaign_id,
                    name=request.POST.get('name', ''),
                    channel=request.POST.get('channel', ''),
                    objective=request.POST.get('objective', ''),
                    owner=request.POST.get('owner', ''),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    budget=float(request.POST.get('budget', 0) or 0),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Campaign updated.'
                campaign = get_campaign(conn, campaign_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'mkt_campaign_detail.html', _mkt_ctx(
        request, campaign=campaign, can_edit=can_edit,
        campaign_statuses=CAMPAIGN_STATUSES, channels=CHANNELS, objectives=OBJECTIVES,
        error=error, success=success,
    ))


@dept_required('marketing')
def mkt_lead_list(request):
    status_f = request.GET.get('status', '').strip()
    source_f = request.GET.get('source', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        leads = list_leads(conn, status=status_f or None,
                           source=source_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_lead(
                    conn,
                    name=request.POST.get('name', ''),
                    company=request.POST.get('company', ''),
                    email=request.POST.get('email', ''),
                    source=request.POST.get('source', ''),
                    owner=request.POST.get('owner', ''),
                    captured_date=request.POST.get('captured_date', ''),
                    status=request.POST.get('status', 'New'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('mkt_lead_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                leads = list_leads(conn, status=status_f or None,
                                   source=source_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'mkt_leads', [
            ('name', 'Name'), ('company', 'Company'), ('email', 'Email'),
            ('source', 'Source'), ('owner', 'Owner'),
            ('captured_date', 'Captured Date'), ('status', 'Status'),
        ], leads)

    return render(request, 'mkt_lead_list.html', _mkt_ctx(
        request, leads=leads, status_filter=status_f, source_filter=source_f,
        search=search, lead_statuses=LEAD_STATUSES, lead_sources=LEAD_SOURCES,
        error=error, success=success,
    ))


@dept_required('marketing')
def mkt_lead_detail(request, lead_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    lead = None
    try:
        lead = get_lead(conn, lead_id)
        if not lead:
            return redirect('mkt_lead_list')
        if request.method == 'POST' and can_edit:
            try:
                update_lead(
                    conn, lead_id,
                    name=request.POST.get('name', ''),
                    company=request.POST.get('company', ''),
                    email=request.POST.get('email', ''),
                    source=request.POST.get('source', ''),
                    owner=request.POST.get('owner', ''),
                    captured_date=request.POST.get('captured_date', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Lead updated.'
                lead = get_lead(conn, lead_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'mkt_lead_detail.html', _mkt_ctx(
        request, lead=lead, can_edit=can_edit,
        lead_statuses=LEAD_STATUSES, lead_sources=LEAD_SOURCES,
        error=error, success=success,
    ))


@dept_required('marketing')
def mkt_content_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('content_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        items = list_content(conn, status=status_f or None,
                             content_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_content(
                    conn,
                    title=request.POST.get('title', ''),
                    content_type=request.POST.get('content_type', ''),
                    channel=request.POST.get('channel', ''),
                    author=request.POST.get('author', ''),
                    due_date=request.POST.get('due_date', ''),
                    publish_date=request.POST.get('publish_date', ''),
                    status=request.POST.get('status', 'Draft'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('mkt_content_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                items = list_content(conn, status=status_f or None,
                                     content_type=type_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'mkt_content_list.html', _mkt_ctx(
        request, items=items, status_filter=status_f, type_filter=type_f,
        search=search, content_statuses=CONTENT_STATUSES, content_types=CONTENT_TYPES,
        channels=CHANNELS, error=error, success=success,
    ))


@dept_required('marketing')
def mkt_content_detail(request, item_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    item = None
    try:
        item = get_content_item(conn, item_id)
        if not item:
            return redirect('mkt_content_list')
        if request.method == 'POST' and can_edit:
            try:
                update_content(
                    conn, item_id,
                    title=request.POST.get('title', ''),
                    content_type=request.POST.get('content_type', ''),
                    channel=request.POST.get('channel', ''),
                    author=request.POST.get('author', ''),
                    due_date=request.POST.get('due_date', ''),
                    publish_date=request.POST.get('publish_date', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Content updated.'
                item = get_content_item(conn, item_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'mkt_content_detail.html', _mkt_ctx(
        request, item=item, can_edit=can_edit,
        content_statuses=CONTENT_STATUSES, content_types=CONTENT_TYPES,
        channels=CHANNELS, error=error, success=success,
    ))


@dept_required('marketing')
def mkt_ad_list(request):
    status_f = request.GET.get('status', '').strip()
    channel_f = request.GET.get('channel', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        ads = list_ads(conn, status=status_f or None,
                       channel=channel_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_ad(
                    conn,
                    name=request.POST.get('name', ''),
                    channel=request.POST.get('channel', ''),
                    campaign_name=request.POST.get('campaign_name', ''),
                    budget=float(request.POST.get('budget', 0) or 0),
                    spend=float(request.POST.get('spend', 0) or 0),
                    impressions=int(request.POST.get('impressions', 0) or 0),
                    clicks=int(request.POST.get('clicks', 0) or 0),
                    conversions=int(request.POST.get('conversions', 0) or 0),
                    start_date=request.POST.get('start_date', '') or None,
                    end_date=request.POST.get('end_date', '') or None,
                    status=request.POST.get('status', 'Draft'),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('mkt_ad_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                ads = list_ads(conn, status=status_f or None,
                               channel=channel_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'mkt_ads', [
            ('name', 'Name'), ('channel', 'Channel'), ('campaign_name', 'Campaign'),
            ('budget', 'Budget'), ('spend', 'Spend'), ('status', 'Status'),
        ], ads)

    return render(request, 'mkt_ad_list.html', _mkt_ctx(
        request, ads=ads, status_filter=status_f, channel_filter=channel_f,
        search=search, ad_statuses=AD_STATUSES, ad_channels=AD_CHANNELS,
        today=date.today().isoformat(), error=error, success=success,
    ))


@dept_required('marketing')
def mkt_ad_detail(request, ad_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    ad = None
    try:
        ad = get_ad(conn, ad_id)
        if not ad:
            return redirect('mkt_ad_list')
        if request.method == 'POST' and can_edit:
            try:
                update_ad(
                    conn, ad_id,
                    name=request.POST.get('name', ''),
                    channel=request.POST.get('channel', ''),
                    campaign_name=request.POST.get('campaign_name', ''),
                    budget=float(request.POST.get('budget', 0) or 0),
                    spend=float(request.POST.get('spend', 0) or 0),
                    impressions=int(request.POST.get('impressions', 0) or 0),
                    clicks=int(request.POST.get('clicks', 0) or 0),
                    conversions=int(request.POST.get('conversions', 0) or 0),
                    start_date=request.POST.get('start_date', '') or None,
                    end_date=request.POST.get('end_date', '') or None,
                    status=request.POST.get('status', ''),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Ad updated.'
                ad = get_ad(conn, ad_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'mkt_ad_detail.html', _mkt_ctx(
        request, ad=ad, can_edit=can_edit,
        ad_statuses=AD_STATUSES, ad_channels=AD_CHANNELS,
        error=error, success=success,
    ))


@dept_required('marketing')
def mkt_research_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('research_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        projects = list_research(conn, status=status_f or None,
                                 research_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_research(
                    conn,
                    title=request.POST.get('title', ''),
                    research_type=request.POST.get('research_type', ''),
                    description=request.POST.get('description', ''),
                    owner=request.POST.get('owner', ''),
                    start_date=request.POST.get('start_date', '') or None,
                    end_date=request.POST.get('end_date', '') or None,
                    status=request.POST.get('status', 'Planned'),
                    budget=float(request.POST.get('budget', 0) or 0),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('mkt_research_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                projects = list_research(conn, status=status_f or None,
                                         research_type=type_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'mkt_research', [
            ('title', 'Title'), ('research_type', 'Type'), ('owner', 'Owner'),
            ('start_date', 'Start Date'), ('end_date', 'End Date'), ('status', 'Status'),
        ], projects)

    return render(request, 'mkt_research_list.html', _mkt_ctx(
        request, projects=projects, status_filter=status_f, type_filter=type_f,
        search=search, research_types=RESEARCH_TYPES, research_statuses=RESEARCH_STATUSES,
        today=date.today().isoformat(), error=error, success=success,
    ))


@dept_required('marketing')
def mkt_research_detail(request, project_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    project = None
    try:
        project = get_research_project(conn, project_id)
        if not project:
            return redirect('mkt_research_list')
        if request.method == 'POST' and can_edit:
            try:
                update_research(
                    conn, project_id,
                    title=request.POST.get('title', ''),
                    research_type=request.POST.get('research_type', ''),
                    description=request.POST.get('description', ''),
                    owner=request.POST.get('owner', ''),
                    start_date=request.POST.get('start_date', '') or None,
                    end_date=request.POST.get('end_date', '') or None,
                    status=request.POST.get('status', ''),
                    findings=request.POST.get('findings', ''),
                    budget=float(request.POST.get('budget', 0) or 0),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Project updated.'
                project = get_research_project(conn, project_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'mkt_research_detail.html', _mkt_ctx(
        request, project=project, can_edit=can_edit,
        research_types=RESEARCH_TYPES, research_statuses=RESEARCH_STATUSES,
        error=error, success=success,
    ))


@dept_required('marketing')
def mkt_analytics(request):
    with get_db_connection() as conn:
        data = get_analytics_data(conn)
    return render(request, 'mkt_analytics.html', _mkt_ctx(request, **data))


