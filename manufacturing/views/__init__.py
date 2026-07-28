"""Django HTTP handlers for login, navigation, and account management.

Menu data lives in :mod:`manufacturing.menus`; authentication and role
persistence live in :mod:`manufacturing.accounts`.
"""

import json
from datetime import date, timedelta

import psycopg2

from django.shortcuts import render, redirect
from django.urls import reverse

from ..log_utils import get_logger
from ..schema import init_schema
from ..db_pg import get_db_connection
from ..csv_export import export_response
from ..audit_core import get_recent, get_history, AUDITED_TABLES
from ..approval_core import (
    needs_approval, request_approval, approve_po, reject_po,
    get_pending_approvals, count_pending, get_po_approval,
    get_approval_by_id,
    APPROVAL_THRESHOLD, APPROVAL_ROLES,
)
from ..notify_core import notify_approval_requested, notify_approval_decided
from ..bom_web_core import (
    list_products, get_product, get_bom, explode_bom,
    add_bom_line, update_bom_line, delete_bom_line,
    update_item_master, ITEM_TYPES,
)
from ..mrp_web_core import (
    get_demand_details, get_scheduled_receipts_detail,
    run_mrp_dated, release_plan as mrp_release_plan,
)
from ..inventory_core import (
    TRANS_TYPES,
    list_products as inv_list_products,
    get_product as inv_get_product,
    get_transactions, get_alert_counts,
    load_suppliers as inv_load_suppliers,
    record_transaction, create_product as inv_create_product,
    update_product as inv_update_product,
)
from .. import lot_core, routing_core, costing_core, capacity_planning_core
from ..contacts_core import (
    list_customers, get_customer, create_customer, update_customer,
    get_customer_orders,
    list_suppliers as contacts_list_suppliers,
    get_supplier, create_supplier, update_supplier,
    get_supplier_orders,
)
from ..price_list_core import (
    ensure_price_list_tables, list_price_lists, assign_customer_price_list,
    get_customer_price_tiers,
)
from ..discount_core import ensure_discount_tables, get_promotion_tiers_for_customer
from ..cs_calls_core import (
    validate_call, PLAN_STATUSES,
    load_customers_for_cs,
    list_tickets, get_ticket, create_ticket, update_ticket, close_ticket,
    get_escalations, get_summary_stats, get_monthly_volume,
    list_plans as cs_list_plans, create_plan as cs_create_plan,
    update_plan as cs_update_plan,
    RETURN_STATUSES, RETURN_REASONS,
    list_returns, get_return, create_return, update_return,
    KB_STATUSES, KB_CATEGORIES,
    list_kb_articles, get_kb_article, create_kb_article, update_kb_article,
    SURVEY_TYPES, SURVEY_STATUSES,
    list_surveys, get_survey, get_survey_responses,
    create_survey, update_survey, add_survey_response,
    init_return_table, init_kb_table, init_survey_tables,
)
from ..period_locking_core import (
    is_period_locked, close_period, reopen_period,
    list_periods, recent_months, period_label, PERIOD_ADMIN_ROLES,
)
from ..purchase_orders_core import (
    PO_STATUSES, PO_STATUS_COLORS, PO_STATUS_ACTION_LABELS,
    list_pos, get_po, get_po_items,
    next_po_number, load_suppliers, load_products,
    create_po, update_po, add_po_item, delete_po_item,
    allowed_transitions, can_transition, set_po_status, receive_po_item,
)
from ..wms_core import ensure_wms_tables, credit_unassigned_receipt
from ..landed_cost_core import ensure_landed_cost_tables, list_landed_costs
from ..time_clock_core import (
    get_current_entry, clock_in as tc_clock_in, clock_out_entry,
    list_entries, total_hours as tc_total_hours,
    get_period_dates, get_attendance,
)
from ..time_clock_web_core import (
    get_ot_report, get_ot_report_all, get_schedule_summary,
)
from ..time_clock_poller_core import (
    DEVICE_TYPES, DEVICE_TYPE_LABELS,
    list_devices, get_device, create_device, update_device, delete_device,
    list_sync_log, poll_device,
)
from ..personnel_core import (
    TIME_OFF_STATUSES, TIME_OFF_TYPES,
    list_people, get_person, get_person_by_email,
    create_person, update_person,
    load_depts, load_dept_subs, list_dept_subs_with_dept,
    create_dept, update_dept,
    create_dept_sub, update_dept_sub,
    list_time_off_requests, get_time_off_request,
    create_time_off_request, set_time_off_status,
    REVIEW_STATUSES, REVIEW_TYPES, REVIEW_RATINGS,
    list_reviews, get_review, create_review, update_review, init_review_table,
    TRAINING_STATUSES, TRAINING_TYPES,
    list_trainings, get_training, create_training, update_training, init_training_table,
    get_personnel_dashboard,
)
from ..workforce_analytics_core import ensure_workforce_columns
from ..sales_orders_core import (
    SO_STATUSES, SO_STATUS_COLORS, SO_STATUS_ACTION_LABELS,
    list_sos, get_so, get_so_items,
    next_so_number, load_customers, load_products as load_so_products,
    create_so, update_so, add_so_item, delete_so_item,
    allowed_transitions as so_allowed_transitions,
    can_transition as so_can_transition,
    set_so_status,
)
from ..atp_core import get_atp_qty_for_products, check_so_atp
from ..capable_to_promise_core import check_so_capacity
from ..work_orders_core import (
    WO_STATUSES, WO_STATUS_COLORS, WO_STATUS_ACTION_LABELS,  # noqa: F811
    list_wos, get_wo, get_wo_materials,
    next_wo_number, load_products as load_wo_products,
    create_wo, update_wo, add_wo_material, set_wo_status,
    can_transition as wo_can_transition,
    allowed_transitions as wo_allowed_transitions,
)
from ..reports_core import (
    po_summary, wo_summary, inventory_alerts, cs_summary,
)
from ..menus import (
    DASHBOARD_DEPARTMENTS,
    MANAGER_MENU_KEYS,
    _walk_tree,
)
from ..accounts import (
    FULL_ACCESS_ROLES,
    READ_ONLY_ROLES,
    _ROLE_ADMIN_ROLES,
    _get_user_profile,
    _is_full_access,
    _verify_login,
    _email_exists,
    _create_user,
    _reset_password,
    _get_all_users_with_roles,
    _get_all_roles,
    _set_user_role,
    _remove_user_role,
)
from ..auth_decorators import dept_required, login_required, role_required

from ..production_core import (
    get_production_dashboard,
    get_daily_output_trend,
    get_wo_status_breakdown,
    list_scheduled_wos,
    get_prod_reports,
    SHIPMENT_STATUSES,
    list_shipments, get_shipment, get_shipment_items,
    create_shipment, update_shipment, add_shipment_item,
    init_shipment_tables,
    get_tracking_dashboard,
    get_delivery_status,
    get_daily_report,
    get_performance_report,
    RMA_STATUSES, RMA_REASONS,
    init_rma_table,
    list_rmas, get_rma, create_rma, update_rma,
    get_rma_reports,
)
from ..currency_core import (
    init_currency_schema, list_currencies, upsert_currency,
    get_base_currency, COMMON_CURRENCIES,
)
from ..fixed_asset_core import (
    init_fixed_asset_tables, list_fixed_assets, get_fixed_asset,
    create_fixed_asset, update_fixed_asset, next_asset_number,
    log_fixed_asset_event, list_fixed_asset_events, get_fixed_asset_summary,
    FIXED_ASSET_TYPES, FIXED_ASSET_STATUSES, DEPRECIATION_METHODS,
)
from ..purchasing_core import (
    get_purchasing_dashboard,
    CONTRACT_STATUSES as PURCH_CONTRACT_STATUSES,
    CONTRACT_CATEGORIES as PURCH_CONTRACT_CATEGORIES,
    list_contracts as list_purch_contracts,
    get_contract as get_purch_contract,
    create_contract as create_purch_contract,
    update_contract as update_purch_contract,
    init_purch_contract_table,
    get_purch_reports,
)
# Aliased: ats_core (job requisitions) also exports list_requisitions/
# get_requisition/create_requisition, and `from ._ats import *` below would
# otherwise silently shadow these with the wrong (ATS) functions.
from ..purchase_requisitions_core import (
    REQ_STATUSES,
    is_manager as req_is_manager, can_authorize as req_can_authorize,
    list_requisitions as list_purchase_reqs,
    get_requisition as get_purchase_req,
    list_requisition_items, list_requisition_approvals,
    create_requisition as create_purchase_req,
    add_requisition_item,
    submit_requisition, decide_requisition,
)
from ..finance_core import (
    get_finance_dashboard, get_revenue_expense_by_month,
    get_top_ar_customers, get_invoice_status_mix,
    BUDGET_STATUSES, FIN_AUDIT_TYPES, FIN_AUDIT_STATUSES, FINDING_SEVERITIES,
    TAX_TYPES, TAX_FILING_STATUSES, BANK_STATEMENT_STATUSES,
    list_budgets, get_budget, get_budget_lines,
    create_budget, update_budget, create_budget_line, delete_budget_line,
    list_audits as list_fin_audits, get_audit_record, get_audit_findings,
    create_audit as create_fin_audit, update_audit_record, create_audit_finding,
    list_bank_accounts, get_bank_account, list_bank_statements,
    create_bank_account, update_bank_account,
    list_tax_filings, get_tax_filing,
    create_tax_filing, update_tax_filing,
    get_cash_position,
)
from ..cash_flow_core import get_cash_forecast_13wk

# Domain views extracted to sub-modules for maintainability
from ._quality import *  # noqa: F401,F403
from ._maintenance import *  # noqa: F401,F403
from ._payroll import *  # noqa: F401,F403
from ._it import *  # noqa: F401,F403
from ._barcode import *  # noqa: F401,F403
from ._legal import *  # noqa: F401,F403
from ._budget_dash import budget_dashboard  # noqa: F401
from ._risk_dash import *  # noqa: F401,F403
from ._marketing import *  # noqa: F401,F403
from ._cycle_count import *  # noqa: F401,F403
from ._price_list import *  # noqa: F401,F403
from ._rfq import *  # noqa: F401,F403
from ._gantt import *  # noqa: F401,F403
from ._supplier_scorecard import *  # noqa: F401,F403
from ._cash_flow import *  # noqa: F401,F403
from ._sampling_plan import *  # noqa: F401,F403
from ._atp import *  # noqa: F401,F403
from ._ctp import *  # noqa: F401,F403
from ._document_control import *  # noqa: F401,F403
from ._ess import *  # noqa: F401,F403
from ._capacity_planning import *  # noqa: F401,F403
from ._wms import *  # noqa: F401,F403
from ._landed_cost import *  # noqa: F401,F403
from ._blanket_po import *  # noqa: F401,F403
from ._portal import *  # noqa: F401,F403
from ._multi_entity import *  # noqa: F401,F403
from ._shop_floor import *  # noqa: F401,F403
from ._demand_forecast import *  # noqa: F401,F403
from ._predictive_maintenance import *  # noqa: F401,F403
from ._edi import *  # noqa: F401,F403
from ._ecommerce import *  # noqa: F401,F403
from ._report_builder import *  # noqa: F401,F403
from ._carbon import *  # noqa: F401,F403
from ._costing_layers import *  # noqa: F401,F403
from ._consignment import *  # noqa: F401,F403
from ._scenario_planning import *  # noqa: F401,F403
from ._fmea import *  # noqa: F401,F403
from ._abc_costing import *  # noqa: F401,F403
from ._discount import *  # noqa: F401,F403
from ._coa import *  # noqa: F401,F403
from ._skills_matrix import *  # noqa: F401,F403
from ._benefits import *  # noqa: F401,F403
from ._regulatory_compliance import *  # noqa: F401,F403
from ._workforce_analytics import *  # noqa: F401,F403
from ._terminations import *  # noqa: F401,F403
from ._ats import *  # noqa: F401,F403
from ._supplier_portal import *  # noqa: F401,F403
from ._cto import *  # noqa: F401,F403
from ._recipe import *  # noqa: F401,F403
from ._repetitive import *  # noqa: F401,F403
from ._technician_routing import *  # noqa: F401,F403
from ._apm import *  # noqa: F401,F403
from ._batch_record import *  # noqa: F401,F403
from ._ai_insights import *  # noqa: F401,F403
from ._approval_rules import *  # noqa: F401,F403
from ._health import healthz  # noqa: F401
from ._notifications import *  # noqa: F401,F403
from ._webhooks import *  # noqa: F401,F403
from ._sso import sso_login, sso_callback  # noqa: F401

log = get_logger(__name__)


# Every menu leaf's web page. Keyed by (dept, leaf_key) -> URL. The PO
# viewer (open/status/history) all land on the filterable list.
WEB_LEAF_URLS = {
    ('purchasing', 'new_po'): '/po/new/',
    ('purchasing', 'open_pos'): '/po/',
    ('purchasing', 'po_status'): '/po/',
    ('purchasing', 'po_hist'): '/po/',
    ('reports', 'rpt_dashboard'): '/reports/',
    ('accounting', 'companies'): '/companies/',
    ('accounting', 'intercompany'): '/intercompany/',
    ('accounting', 'consol_fin'): '/consolidated-financials/',
    ('production', 'sf_entry'): '/shop-floor/entry/',
    ('production', 'sf_shift_plan'): '/shop-floor/plan/',
    ('production', 'sf_dashboard'): '/shop-floor/',
    ('production', 'sf_tv'): '/shop-floor/tv/',
    ('production', 'create_wo'): '/wo/new/',
    ('production', 'open_wo'): '/wo/?status=open',
    ('production', 'inprog_wo'): '/wo/?status=in_progress',
    ('production', 'comp_wo'): '/wo/?status=completed',
    ('sales', 'demand_forecast'): '/demand-forecast/',
    ('sales', 'new_order'): '/so/new/',
    ('sales', 'open_orders'): '/so/?status=confirmed',
    ('sales', 'order_hist'): '/so/',
    ('sales', 'order_stat'): '/so/',
    # Sales quotes
    ('sales', 'new_quote'):  '/sales/quotes/',
    ('sales', 'act_quotes'): '/sales/quotes/',
    ('sales', 'quote_hist'): '/sales/quotes/',
    ('sales', 'conv_order'): '/sales/quotes/',
    # Sales reports
    ('sales', 'daily_sales'): '/sales/reports/?period=day',
    ('sales', 'month_sales'): '/sales/reports/?period=month',
    ('sales', 'annual_rpt'):  '/sales/reports/?period=year',
    ('sales', 'by_rep'):      '/sales/performance/',
    # Leads & Opportunities
    ('sales', 'new_lead'):  '/sales/leads/',
    ('sales', 'act_leads'): '/sales/leads/',
    ('sales', 'opp_pipe'):  '/sales/leads/',
    ('sales', 'lead_rpts'): '/sales/leads/',
    # Sales Contracts
    ('sales', 'act_cont'):   '/sales/contracts/',
    ('sales', 'new_cont'):   '/sales/contracts/',
    ('sales', 'cont_renew'): '/sales/contracts/',
    ('sales', 'cont_arch'):  '/sales/contracts/',
    # Forecasting
    ('sales', 'cur_fore'):  '/sales/forecast/',
    ('sales', 'fore_rep'):  '/sales/forecast/',
    ('sales', 'fore_prod'): '/sales/forecast/',
    ('sales', 'fore_rpts'): '/sales/forecast/',
    # Sales Targets (manager sub-menu)
    ('sales', 'set_tgt'):   '/sales/targets/',
    ('sales', 'tgt_act'):   '/sales/targets/',
    ('sales', 'tgt_rep'):   '/sales/targets/',
    ('sales', 'tgt_rpts'):  '/sales/targets/',
    # Territory Management
    ('sales', 'terr_map'):    '/sales/territories/',
    ('sales', 'terr_assign'): '/sales/territories/',
    ('sales', 'terr_perf'):   '/sales/territories/performance/',
    ('sales', 'terr_rpts'):   '/sales/territories/',
    # Commission Tracking
    ('sales', 'comm_calc'):  '/sales/commissions/',
    ('sales', 'comm_rpts'):  '/sales/commissions/',
    ('sales', 'pay_hist'):   '/sales/commissions/history/',
    ('sales', 'comm_plans'): '/sales/commissions/plans/',
    # Staff Performance
    ('sales', 'perf_dash'):  '/sales/performance/',
    ('sales', 'rep_rank'):   '/sales/performance/',
    ('sales', 'perf_revs'):  '/sales/performance/reviews/',
    ('sales', 'coaching'):   '/sales/performance/coaching/',
    ('personnel', 'view_recs'): '/people/',
    ('personnel', 'new_emp'): '/people/new/',
    ('personnel', 'upd_rec'): '/people/',
    ('personnel', 'emp_hist'): '/people/',
    ('personnel', 'disp_dept'): '/people/',
    ('personnel', 'submit_req'): '/time-off/new/',
    ('personnel', 'pend_req'): '/time-off/?status=pending',
    ('personnel', 'appr_req'): '/time-off/?status=approved',
    ('personnel', 'req_hist'): '/time-off/',
    ('personnel', 'punch_in'): '/time-clock/',
    ('personnel', 'punch_out'): '/time-clock/',
    ('personnel', 'cur_status'): '/time-clock/',
    ('personnel', 'today_hrs'): '/time-clock/hours/',
    ('personnel', 'week_hrs'): '/time-clock/hours/?period=week',
    ('personnel', 'month_hrs'): '/time-clock/hours/?period=month',
    ('personnel', 'period_hrs'): '/time-clock/hours/?period=month',
    ('personnel', 'daily_att'): '/time-clock/attendance/',
    ('personnel', 'tard_rpt'): '/time-clock/attendance/',
    ('personnel', 'abs_rpt'): '/time-clock/attendance/',
    # Time clock — schedules
    ('personnel', 'my_sched'):  '/time-clock/schedule/',
    ('personnel', 'upcoming'):  '/time-clock/schedule/',
    ('personnel', 'sched_cal'): '/time-clock/schedule/',
    ('personnel', 'swap_req'):  '/time-clock/schedule/',
    # Time clock — overtime reports
    ('personnel', 'cur_ot'):    '/time-clock/ot/',
    ('personnel', 'hist_ot'):   '/time-clock/ot/',
    ('personnel', 'ot_by_emp'): '/time-clock/ot/?mode=all',
    ('personnel', 'ot_appr'):   '/time-clock/ot/?mode=all',
    # Time clock — shift management
    ('personnel', 'view_shfts'):  '/time-clock/schedule/',
    ('personnel', 'assign_emp'):  '/time-clock/schedule/',
    ('personnel', 'shft_tmpl'):   '/time-clock/schedule/',
    ('personnel', 'swap_mgmt'):   '/time-clock/schedule/',
    ('engineering', 'bom_list'): '/bom/',
    ('engineering', 'new_bom'): '/bom/',
    ('engineering', 'bom_rev'): '/bom/',
    ('engineering', 'bom_rpts'): '/bom/',
    ('engineering', 'eng_mgr'): '/eng/',
    ('engineering', 'engineers'): '/eng/',
    ('engineering', 'proj_mgmt'): '/eng/projects/',
    ('engineering', 'design_docs'): '/eng/ecrs/',
    ('engineering', 'bom'): '/bom/',
    ('engineering', 'chg_orders'): '/eng/ecrs/',
    ('engineering', 'test_val'): '/eng/projects/?status=in_progress',
    ('engineering', 'eng_reports'): '/eng/reports/',
    ('engineering', 'standards'): '/eng/reports/',
    # Engineering Projects (engineer menu)
    ('engineering', 'act_proj'):   '/eng/projects/',
    ('engineering', 'new_proj'):   '/eng/projects/',
    ('engineering', 'proj_time'):  '/eng/projects/',
    ('engineering', 'proj_rpts'):  '/eng/projects/',
    # Design Documents (Document Control, P2-F)
    ('engineering', 'doc_lib'):    '/documents/',
    ('engineering', 'new_doc'):    '/documents/new/',
    ('engineering', 'doc_review'): '/documents/?status=in_review',
    ('engineering', 'archive'):    '/documents/?status=obsolete',
    ('engineering', 'new_co'):     '/eng/ecrs/',
    ('engineering', 'appr_chg'):   '/eng/ecrs/',
    ('engineering', 'chg_hist'):   '/eng/ecrs/',
    # Test & Validation → tasks
    ('engineering', 'test_plans'): '/eng/tasks/',
    ('engineering', 'test_res'):   '/eng/tasks/',
    ('engineering', 'val_rpts'):   '/eng/tasks/',
    ('engineering', 'issue_track'): '/eng/tasks/',
    # Engineering Reports
    ('engineering', 'proj_stat'):  '/eng/reports/',
    ('engineering', 'design_rev'): '/eng/reports/',
    ('engineering', 'res_rpt'):    '/eng/reports/',
    ('engineering', 'cust_rpts'):  '/eng/reports/',
    # Standards & Compliance
    ('engineering', 'std_lib'):    '/eng/specs/',
    ('engineering', 'comp_chk'):   '/eng/specs/',
    ('engineering', 'audit_res'):  '/eng/specs/',
    ('engineering', 'reg_upd'):    '/eng/specs/',
    # Manager: Project Approvals
    ('engineering', 'pend_appr'):  '/eng/projects/',
    ('engineering', 'appr_proj'):  '/eng/projects/',
    ('engineering', 'rej_proj'):   '/eng/projects/',
    ('engineering', 'appr_hist'):  '/eng/projects/',
    # Manager: Resource Management
    ('engineering', 'res_alloc'):  '/eng/',
    ('engineering', 'cap_plan'):   '/eng/',
    ('engineering', 'res_rpts'):   '/eng/reports/',
    ('engineering', 'avail_cal'):  '/eng/',
    # Manager: Budget
    ('engineering', 'eng_budg'):   '/fin/budgets/',
    ('engineering', 'budg_act'):   '/fin/budgets/',
    ('engineering', 'cost_rpts'):  '/fin/budgets/',
    ('engineering', 'budg_req'):   '/fin/budgets/',
    # Manager: Engineering Reports
    ('engineering', 'res_util'):   '/eng/reports/',
    ('engineering', 'kpi_dash'):   '/eng/reports/',
    ('engineering', 'month_rpts'): '/eng/reports/',
    ('sales', 'sales_mgr'): '/sales/',
    ('sales', 'sales'): '/sales/orders/',
    ('production', 'prod_mgr'): '/prod/',
    ('production', 'prod'): '/wo/',
    ('production', 'shipping'): '/wo/',
    ('production', 'bom_list'): '/bom/',
    ('production', 'mrp_home'): '/mrp/',
    ('production', 'run_mrp'): '/mrp/',
    ('production', 'mrp_demand'): '/mrp/',
    ('production', 'mrp_rpts'): '/mrp/',
    ('production', 'raw_mat'): '/inventory/?item_type=buy',
    ('production', 'fin_goods'): '/inventory/?item_type=make',
    ('production', 'wip_inv'): '/inventory/',
    ('production', 'inv_rpts'): '/inventory/',
    ('production', 'cost_valuation'): '/inventory/valuation/',
    # Production Schedule
    ('production', 'daily_sched'):  '/prod/schedule/',
    ('production', 'week_sched'):   '/prod/schedule/',
    ('production', 'month_sched'):  '/prod/schedule/',
    ('production', 'sched_cal'):    '/prod/schedule/',
    ('production', 'gantt_sched'):  '/prod/schedule/gantt/',
    # Equipment Status → Maintenance
    ('production', 'equip_list'):   '/maint/equipment/',
    ('production', 'stat_dash'):    '/maint/',
    ('production', 'down_log'):     '/maint/downtime/',
    ('production', 'maint_req'):    '/maint/wo/',
    # Quality Control → QA
    ('production', 'insp_res'):     '/qa/inspections/',
    ('production', 'non_conf'):     '/qa/ncr/',
    ('production', 'qc_rpts'):      '/qa/',
    ('production', 'rej_analy'):    '/qa/ncr/',
    # Production Reports
    ('production', 'daily_prod'):   '/prod/reports/',
    ('production', 'week_sum'):     '/prod/reports/',
    ('production', 'eff_rpt'):      '/prod/reports/',
    ('production', 'scrap_rpt'):    '/prod/reports/',
    ('production', 'eff_rpts'):     '/prod/reports/',
    ('production', 'kpi_dash'):     '/prod/reports/',
    # Labor Tracking → Reports
    ('production', 'cur_labor'):    '/prod/reports/',
    ('production', 'labor_shft'):   '/prod/reports/',
    ('production', 'labor_job'):    '/prod/reports/',
    ('production', 'labor_rpts'):   '/prod/reports/',
    # Resource Management
    ('production', 'res_alloc'):    '/prod/',
    ('production', 'cap_plan'):     '/prod/schedule/capacity/',
    ('production', 'res_rpts'):     '/prod/reports/',
    ('production', 'wf_plan'):      '/prod/',
    # Budget → Finance
    ('production', 'prod_budg'):    '/fin/budgets/',
    ('production', 'cost_analy'):   '/fin/budgets/',
    ('production', 'budg_act'):     '/fin/budgets/',
    ('production', 'budg_rpts'):    '/fin/budgets/',
    # Shipping
    ('production', 'new_ship'):     '/prod/shipping/',
    ('production', 'pend_ship'):    '/prod/shipping/?status=pending',
    ('production', 'shipped'):      '/prod/shipping/?status=delivered',
    ('production', 'deliv_conf'):   '/prod/shipping/',
    ('production', 'today_sched'):  '/prod/schedule/',
    ('production', 'rush_orders'):  '/prod/schedule/',
    ('production', 'carr_list'):    '/prod/shipping/',
    ('production', 'carr_rates'):   '/prod/shipping/',
    ('production', 'perf_rpts'):    '/prod/reports/',
    ('production', 'carr_cont'):    '/prod/shipping/',
    # Receiving → PO receipts
    ('production', 'inbound'):      '/po/',
    ('production', 'recv_items'):   '/wms/receive/',
    ('production', 'recv_rpts'):    '/po/',
    ('production', 'disc_rpts'):    '/po/',
    # Tracking
    ('production', 'track_ship'):   '/prod/shipping/',
    ('production', 'ship_hist'):    '/prod/shipping/',
    ('production', 'del_conf'):     '/prod/shipping/',
    ('production', 'exc_rpts'):     '/prod/shipping/',
    # Tracking dashboard & delivery status
    ('production', 'track_dash'):   '/prod/tracking/',
    ('production', 'deliv_stat'):   '/prod/delivery-status/',
    # Daily & performance reports
    ('production', 'daily_rpt'):    '/prod/daily-report/',
    ('production', 'perf_rpt'):     '/prod/performance/',
    # Returns / RMA
    ('production', 'new_return'):   '/prod/returns/new/',
    ('production', 'pend_ret'):     '/prod/returns/?status=pending',
    ('production', 'ret_hist'):     '/prod/returns/',
    ('production', 'ret_rpts'):     '/prod/returns/reports/',

    ('production', 'warehouses'):    '/wms/warehouses/',
    ('production', 'bin_master'):    '/wms/bins/',
    ('production', 'putaway_rules'): '/wms/putaway-rules/',
    ('production', 'pick_lists'):    '/wms/picks/',
    ('production', 'wave_picking'):  '/wms/waves/',
    ('production', 'pack_station'):  '/wms/picks/?status=picked',
    ('production', 'transfers'):     '/wms/transfers/',
    ('production', 'rfid_readers'):  '/wms/rfid/readers/',
    ('production', 'rfid_tags'):     '/wms/rfid/tags/',
    # Maintenance
    ('maintenance', 'predictive_maint'): '/predictive-maintenance/',
    ('maintenance', 'maint'): '/maint/',
    ('maintenance', 'maint_mgr'): '/maint/',
    ('maintenance', 'create_wo'): '/maint/wo/',
    ('maintenance', 'open_wo'): '/maint/wo/?status=Open',
    ('maintenance', 'inprog_wo'): '/maint/wo/?status=In+Progress',
    ('maintenance', 'comp_wo'): '/maint/wo/?status=Completed',
    ('maintenance', 'daily_sched'): '/maint/schedule/',
    ('maintenance', 'week_sched'): '/maint/schedule/',
    ('maintenance', 'month_sched'): '/maint/schedule/',
    ('maintenance', 'annual_plan'): '/maint/schedule/',
    ('maintenance', 'equip_list'): '/maint/equipment/',
    ('maintenance', 'maint_hist'): '/maint/equipment/',
    ('maintenance', 'svc_records'): '/maint/equipment/',
    ('maintenance', 'equip_stat'): '/maint/equipment/',
    ('maintenance', 'view_inv'): '/maint/parts/',
    ('maintenance', 'parts_req'): '/maint/parts/',
    ('maintenance', 'reorder'): '/maint/parts/?status=Low+Stock',
    ('maintenance', 'parts_hist'): '/maint/parts/',
    ('maintenance', 'daily_rpt'): '/maint/oee/?period=day',
    ('maintenance', 'week_rpt'): '/maint/oee/?period=week',
    ('maintenance', 'cost_analy'): '/maint/downtime/',
    ('maintenance', 'down_rpt'): '/maint/downtime/',
    ('maintenance', 'sched_insp'): '/maint/inspections/?status=Scheduled',
    ('maintenance', 'insp_chk'): '/maint/inspections/',
    ('maintenance', 'insp_res'): '/maint/inspections/',
    ('maintenance', 'corr_act'): '/maint/inspections/?status=Follow-up',
    ('maintenance', 'pm_sched'): '/maint/schedule/',
    ('maintenance', 'pm_chk'): '/maint/schedule/',
    ('maintenance', 'pm_hist'): '/maint/schedule/?status=Completed',
    ('maintenance', 'pm_rpts'): '/maint/schedule/',
    ('maintenance', 'pend_appr'): '/maint/wo/?status=Open',
    ('maintenance', 'appr_wo'): '/maint/wo/',
    ('maintenance', 'rej_wo'): '/maint/wo/',
    ('maintenance', 'appr_hist'): '/maint/wo/?status=Completed',
    ('maintenance', 'maint_budg'): '/fin/budgets/',
    ('maintenance', 'budg_act'): '/fin/budgets/',
    ('maintenance', 'budg_req'): '/fin/budgets/',
    ('maintenance', 'month_sum'): '/maint/oee/?period=month',
    ('maintenance', 'equip_rpts'): '/maint/equipment/',
    ('maintenance', 'cost_rpts'): '/maint/downtime/',
    ('maintenance', 'maint_rpts'): '/maint/',
    # Quality Assurance
    ('quality_assurance', 'qa_mgr'): '/qa/',
    ('quality_assurance', 'qa_menu'): '/qa/',
    ('quality_assurance', 'qa_lab'): '/qa/inspections/',
    ('quality_assurance', 'new_req'): '/qa/inspections/',
    ('quality_assurance', 'pend_req'): '/qa/inspections/?result=pending',
    ('quality_assurance', 'inprog_req'): '/qa/inspections/',
    ('quality_assurance', 'comp_tests'): '/qa/inspections/?result=passed',
    ('quality_assurance', 'recent_res'): '/qa/inspections/',
    ('quality_assurance', 'search_res'): '/qa/inspections/',
    ('quality_assurance', 'failed'): '/qa/inspections/?result=failed',
    ('quality_assurance', 'new_ncr'): '/qa/ncr/',
    ('quality_assurance', 'open_ncrs'): '/qa/ncr/?status=Open',
    ('quality_assurance', 'ncr_hist'): '/qa/ncr/',
    ('quality_assurance', 'ncr_rpts'): '/qa/ncr/',
    ('quality_assurance', 'audit_sched'): '/qa/audits/?status=Scheduled',
    ('quality_assurance', 'act_audits'): '/qa/audits/?status=In+Progress',
    ('quality_assurance', 'findings'): '/qa/audits/',
    ('quality_assurance', 'corr_act'): '/qa/capa/',
    ('quality_assurance', 'open_cars'): '/qa/capa/?status=Open',
    ('quality_assurance', 'inprog_cars'): '/qa/capa/?status=In+Progress',
    ('quality_assurance', 'closed_cars'): '/qa/capa/?status=Closed',
    ('quality_assurance', 'car_rpts'): '/qa/capa/',
    ('quality_assurance', 'daily_qa'): '/qa/reports/',
    ('quality_assurance', 'week_sum'): '/qa/reports/',
    ('quality_assurance', 'month_rpt'): '/qa/reports/',
    ('quality_assurance', 'kpi_dash'): '/qa/reports/',
    ('quality_assurance', 'supp_score'): '/suppliers/scorecard/',
    ('quality_assurance', 'inc_insp'): '/qa/inspections/',
    ('quality_assurance', 'sampling_plans'): '/sampling-plans/',
    ('quality_assurance', 'supp_audit'): '/qa/suppliers/',
    ('quality_assurance', 'supp_rpts'): '/qa/suppliers/',
    ('quality_assurance', 'new_comp'): '/qa/ncr/',
    ('quality_assurance', 'open_comp'): '/qa/ncr/?status=Open',
    # QA lab: inspection / lab reports / calibration / sample management
    ('quality_assurance', 'res_rpts'):    '/qa/reports/',
    ('quality_assurance', 'create_rpt'):  '/qa/inspections/',
    ('quality_assurance', 'pend_rpts'):   '/qa/inspections/?result=pending',
    ('quality_assurance', 'rpt_arch'):    '/qa/inspections/',
    ('quality_assurance', 'rpt_sum'):     '/qa/reports/',
    ('quality_assurance', 'cal_sched'):   '/qa/inspections/',
    ('quality_assurance', 'cal_records'): '/qa/inspections/',
    ('quality_assurance', 'overdue'):     '/qa/inspections/?result=on_hold',
    ('quality_assurance', 'cal_rpts'):    '/qa/reports/',
    ('quality_assurance', 'recv_sample'): '/qa/inspections/',
    ('quality_assurance', 'samp_track'):  '/qa/inspections/',
    ('quality_assurance', 'samp_disp'):   '/qa/inspections/',
    ('quality_assurance', 'samp_rpts'):   '/qa/reports/',
    ('quality_assurance', 'daily_rpts'):  '/qa/reports/',
    ('quality_assurance', 'cust_rpts'):   '/qa/reports/',
    # QA compliance / customer complaints / document control
    ('quality_assurance', 'comp_dash'):   '/qa/reports/',
    ('quality_assurance', 'reg_req'):     '/qa/audits/',
    ('quality_assurance', 'comp_rpts'):   '/qa/reports/',
    ('quality_assurance', 'non_comp'):    '/qa/ncr/',
    ('quality_assurance', 'res_track'):   '/qa/capa/',
    ('quality_assurance', 'doc_lib'):     '/documents/',
    ('quality_assurance', 'new_doc'):     '/documents/new/',
    ('quality_assurance', 'doc_review'):  '/documents/?status=in_review',
    ('quality_assurance', 'rev_hist'):    '/documents/',
    # Customer Service tickets
    ('customer_service', 'all_tickets'): '/cs/',
    ('customer_service', 'my_tickets'): '/cs/?my=1',
    ('customer_service', 'hi_pri'): '/cs/escalations/',
    ('customer_service', 'tick_search'): '/cs/',
    ('customer_service', 'new_return'): '/cs/new/',
    # Customers
    ('customers', 'acct_list'): '/customers/',
    ('customers', 'new_acct'): '/customers/new/',
    ('customers', 'acct_det'): '/customers/',
    ('customers', 'acct_hist'): '/customers/',
    ('customer_service', 'cust_entry'): '/customers/new/',
    ('customer_service', 'acct_list'): '/customers/',
    ('customer_service', 'new_acct'): '/customers/new/',
    ('customer_service', 'acct_det'): '/customers/',
    ('customer_service', 'acct_hist'): '/customers/',
    ('sales', 'acct_list'): '/customers/',
    ('sales', 'new_acct'): '/customers/new/',
    ('sales', 'acct_det'): '/customers/',
    ('sales', 'acct_hist'): '/customers/',
    # Suppliers / Vendors
    ('customers', 'sup_entry'): '/suppliers/new/',
    ('customers', 'vend_list'): '/suppliers/',
    ('customers', 'new_vend'): '/suppliers/new/',
    ('purchasing', 'sup_entry'): '/suppliers/new/',
    ('purchasing', 'vend_list'): '/suppliers/',
    ('purchasing', 'new_vend'): '/suppliers/new/',
    # Payroll
    ('accounting', 'payroll'):    '/payroll/',
    ('accounting', 'pay'):        '/payroll/',
    ('accounting', 'pay_rates'):  '/payroll/pay-rates/',
    ('accounting', 'deductions'): '/payroll/deductions/',
    ('accounting', 'run_payroll'): '/payroll/',
    ('accounting', 'pay_stubs'):  '/payroll/history/',
    ('accounting', 'ytd_rpt'):    '/payroll/ytd/',
    ('accounting', 'pay_hist'):   '/payroll/history/',
    ('personnel', 'pay_rates'):   '/payroll/pay-rates/',
    ('personnel', 'deductions'):  '/payroll/deductions/',
    # Accounting dashboard
    ('accounting', 'acct_mgr'):   '/acct/',
    # Accounts Payable
    ('accounting', 'acct_pay'):   '/ap/',
    ('accounting', 'ap'):         '/ap/',
    ('accounting', 'acct_rcv'):   '/ar/',
    ('accounting', 'rcv'):        '/ar/',
    # General Ledger / Financial Reports
    ('accounting', 'inc_stmt'):   '/gl/income-statement/',
    ('accounting', 'bal_sheet'):  '/gl/balance-sheet/',
    ('accounting', 'cash_flow'):  '/gl/cash-flow/',
    ('accounting', 'cust_rpts'):  '/gl/',
    ('accounting', 'fin_reports'): '/gl/',
    ('accounting', 'credit'):     '/gl/',
    ('finance', 'fin_plan'):       '/fin/budgets/',
    ('finance', 'fin_forecast'):   '/fin/budgets/',
    ('finance', 'fin_analysis'):   '/fin/audits/',
    ('finance', 'fin_reporting'):  '/fin/audits/',
    ('finance', 'treasury_ops'):   '/fin/bank-rec/',
    ('finance', 'capital_mgmt'):   '/fin/',
    ('finance', 'tax_planning'):   '/fin/tax/',
    ('finance', 'treasury_mgmt'):  '/fin/bank-rec/',
    ('finance', 'invest_mgmt'):    '/fin/',
    ('finance', 'fin_rpts_mgr'):   '/gl/',
    # Purchasing dashboard
    ('purchasing', 'prod_entry'):  '/inventory/new/',
    ('purchasing', 'vend_eval'):   '/suppliers/',
    ('purchasing', 'vend_perf'):   '/suppliers/scorecard/',
    ('purchasing', 'vend_cont'):   '/suppliers/',
    ('purchasing', 'spend_sum'):   '/purch/reports/',
    ('purchasing', 'po_rpts'):     '/purch/reports/',
    ('purchasing', 'budg_act'):    '/purch/reports/',
    ('purchasing', 'cat_rpts'):    '/purch/reports/',
    ('purchasing', 'act_cont'):    '/purch/contracts/',
    ('purchasing', 'new_cont'):    '/purch/contracts/',
    ('purchasing', 'cont_renew'):  '/purch/contracts/',
    ('purchasing', 'cont_arch'):   '/purch/contracts/',
    ('purchasing', 'pend_recv'):   '/po/',
    ('purchasing', 'recv_items'):  '/po/',
    ('purchasing', 'disc_rpts'):   '/po/',
    ('purchasing', 'recv_hist'):   '/po/',
    ('purchasing', 'req_hist'):    '/purch/requisitions/',
    ('purchasing', 'new_req'):     '/purch/requisitions/',
    ('purchasing', 'pend_appr'):   '/purch/requisitions/?status=submitted',
    ('purchasing', 'appr_reqs'):   '/purch/requisitions/?status=dept_approved',
    ('purchasing', 'appr_pos'):    '/po/',
    ('purchasing', 'rej_pos'):     '/po/',
    ('purchasing', 'appr_hist'):   '/po/',
    ('purchasing', 'purch_budg'):  '/purch/reports/',
    ('purchasing', 'budg_rpts'):   '/purch/reports/',
    ('purchasing', 'spend_analy'): '/purch/reports/',
    ('purchasing', 'vend_rpt'):    '/purch/reports/',
    ('purchasing', 'cat_analy'):   '/purch/reports/',
    ('purchasing', 'month_sum'):   '/purch/reports/',
    ('purchasing', 'spend_rpt'):   '/purch/reports/',
    ('purchasing', 'pend_renew'):  '/purch/contracts/',
    ('purchasing', 'cont_rpts'):   '/purch/contracts/',
    ('purchasing', 'appr_vend'):   '/suppliers/',
    # Personnel dashboard
    ('personnel', 'pers_crm'):     '/people/',
    ('personnel', 'reg_form'):     '/register/',
    ('personnel', 'upd_pass'):     '/change-password/',
    ('personnel', 'dept_entry'):   '/pers/depts/',
    ('personnel', 'dept_sub'):     '/pers/depts/',
    ('personnel', 'ben_enroll'):   '/benefits/',
    ('personnel', 'ben_sum'):      '/benefits/',
    ('personnel', 'cobra'):        '/benefits/',
    ('personnel', 'ben_rpts'):     '/benefits/',
    ('personnel', 'sched_rev'):    '/pers/reviews/',
    ('personnel', 'pend_revs'):    '/pers/reviews/?status=Scheduled',
    ('personnel', 'rev_hist'):     '/pers/reviews/?status=Completed',
    ('personnel', 'perf_rpts'):    '/pers/reviews/',
    ('personnel', 'new_rec'):      '/pers/reviews/',
    ('personnel', 'rec_hist'):     '/pers/reviews/',
    ('personnel', 'disc_rpts'):    '/pers/reviews/',
    ('personnel', 'train_cal'):    '/pers/training/',
    ('personnel', 'train_recs'):   '/pers/training/',
    ('personnel', 'course_mgmt'):  '/pers/training/',
    ('personnel', 'cert_track'):   '/pers/training/?type=Certification',
    ('personnel', 'hire_chk'):     '/pers/training/?type=Compliance',
    ('personnel', 'onb_stat'):     '/pers/training/',
    ('personnel', 'doc_coll'):     '/pers/training/',
    ('personnel', 'onb_rpts'):     '/pers/training/',
    ('personnel', 'open_pos'):     '/ats/requisitions/',
    ('personnel', 'appl_track'):   '/ats/candidates/',
    ('personnel', 'int_sched'):    '/ats/',
    ('personnel', 'offer_mgmt'):   '/ats/',
    ('personnel', 'term_proc'):    '/pers/terminations/',
    ('personnel', 'exit_int'):     '/pers/exit-interviews/',
    ('personnel', 'final_pay'):    '/payroll/',
    ('personnel', 'offboard'):     '/pers/offboarding/',
    ('personnel', 'sal_review'):   '/payroll/pay-rates/',
    ('personnel', 'sal_adj'):      '/payroll/pay-rates/',
    ('personnel', 'comp_rpts'):    '/payroll/',
    ('personnel', 'pay_grades'):   '/payroll/pay-rates/',
    ('personnel', 'hd_rpt'):       '/workforce/',
    ('personnel', 'turn_rpt'):     '/workforce/',
    ('personnel', 'month_sum'):    '/workforce/',
    # Customer Service dashboard
    # Marketing dashboard + sub-pages
    ('marketing', 'act_camp'):    '/mkt/campaigns/',
    ('marketing', 'new_camp'):    '/mkt/campaigns/',
    ('marketing', 'camp_cal'):    '/mkt/campaigns/',
    ('marketing', 'camp_res'):    '/mkt/campaigns/',
    ('marketing', 'res_proj'):    '/mkt/research/',
    ('marketing', 'comp_analy'):  '/mkt/research/',
    ('marketing', 'surv_mgmt'):   '/mkt/research/',
    ('marketing', 'mkt_trends'):  '/mkt/research/',
    ('marketing', 'ad_mgmt'):     '/mkt/ads/',
    ('marketing', 'ad_budget'):   '/mkt/ads/',
    ('marketing', 'ad_perf'):     '/mkt/ads/',
    ('marketing', 'ad_cal'):      '/mkt/ads/',
    ('marketing', 'web_analy'):   '/mkt/analytics/',
    ('marketing', 'camp_analy'):  '/mkt/analytics/',
    ('marketing', 'sales_analy'): '/mkt/analytics/',
    ('marketing', 'cust_rpts'):   '/mkt/analytics/',
    ('marketing', 'cont_cal'):    '/mkt/content/',
    ('marketing', 'blog'):        '/mkt/content/',
    ('marketing', 'mkt_mat'):     '/mkt/content/',
    ('marketing', 'cont_arch'):   '/mkt/content/',
    ('marketing', 'post_mgmt'):   '/mkt/content/',
    ('marketing', 'social_cal'):  '/mkt/content/',
    ('marketing', 'eng_rpts'):    '/mkt/analytics/',
    ('marketing', 'acct_mgmt'):   '/mkt/content/',
    ('marketing', 'email_camp'):  '/mkt/campaigns/',
    ('marketing', 'sub_lists'):   '/mkt/leads/',
    ('marketing', 'email_tmpl'):  '/mkt/content/',
    ('marketing', 'email_analy'): '/mkt/analytics/',
    ('marketing', 'pend_appr'):   '/mkt/campaigns/',
    ('marketing', 'appr_camp'):   '/mkt/campaigns/',
    ('marketing', 'camp_arch'):   '/mkt/campaigns/',
    ('marketing', 'appr_hist'):   '/mkt/campaigns/',
    ('marketing', 'camp_perf'):   '/mkt/analytics/',
    ('marketing', 'roi_rpts'):    '/mkt/analytics/',
    ('marketing', 'month_sum'):   '/mkt/analytics/',
    ('marketing', 'kpi_dash'):    '/mkt/analytics/',
    ('marketing', 'budg_over'):   '/mkt/budget/',
    ('marketing', 'budg_camp'):   '/mkt/budget/',
    ('marketing', 'budg_act'):    '/mkt/budget/',
    ('marketing', 'budg_req'):    '/mkt/budget/',
    # Accounting — General Ledger & sub-menus
    ('accounting', 'gen_ledger'):    '/gl/',
    ('accounting', 'budget_mgmt'):   '/fin/budgets/',
    ('accounting', 'budg_plan'):     '/fin/budgets/',
    ('accounting', 'budg_act'):      '/fin/budgets/',
    ('accounting', 'budg_amend'):    '/fin/budgets/',
    ('accounting', 'budg_rpts'):     '/fin/budgets/',
    ('accounting', 'tax_mgmt'):      '/fin/tax/',
    ('accounting', 'tax_cal'):       '/fin/tax/',
    ('accounting', 'tax_filing'):    '/fin/tax/',
    ('accounting', 'tax_pay'):       '/fin/tax/',
    ('accounting', 'tax_rpts'):      '/fin/tax/',
    ('accounting', 'exp_reports'):   '/ap/',
    ('accounting', 'sub_exp'):       '/ap/',
    ('accounting', 'pend_appr'):     '/ap/',
    ('accounting', 'appr_exp'):      '/ap/',
    ('accounting', 'exp_sum'):       '/ap/',
    ('accounting', 'bank_recon'):    '/fin/bank-rec/',
    ('accounting', 'recon_acct'):    '/fin/bank-rec/',
    ('accounting', 'pend_items'):    '/fin/bank-rec/',
    ('accounting', 'recon_hist'):    '/fin/bank-rec/',
    ('accounting', 'bank_rpts'):     '/fin/bank-rec/',
    ('accounting', 'audit_mgmt'):    '/fin/audits/',
    ('accounting', 'audit_sched'):   '/fin/audits/',
    ('accounting', 'findings'):      '/fin/audits/',
    ('accounting', 'corr_act'):      '/fin/audits/',
    ('accounting', 'audit_rpts'):    '/fin/audits/',
    # Budget Management department
    ('budget_management', 'bud_overview'):  '/fin/budgets/',
    ('budget_management', 'bud_detail_mgr'): '/fin/budgets/',
    ('budget_management', 'bva_mgr'):       '/fin/budgets/',
    ('budget_management', 'variance_mgr'):  '/fin/budgets/',
    ('budget_management', 'dept_summary'):  '/fin/budgets/',
    ('budget_management', 'approval_wf'):   '/fin/budgets/',
    ('budget_management', 'budgets'):       '/fin/budgets/',
    ('budget_management', 'bud_detail'):    '/fin/budgets/',
    ('budget_management', 'bva'):           '/fin/budgets/',
    ('budget_management', 'variance'):      '/fin/budgets/',
    # Finance — manager + top-level leaves
    ('finance', 'fin_mgr'):          '/fin/',
    # Legal / Risk Management dashboard
    ('legal', 'contracts'):          '/legal/contracts/',
    ('legal', 'compliance'):         '/legal/compliance/',
    ('legal', 'litigation'):         '/legal/litigation/',
    ('legal', 'ip_mgmt'):            '/legal/ip/',
    ('legal', 'emp_law'):            '/legal/employment/',
    ('legal', 'contracts_mgmt'):     '/legal/contracts/',
    ('legal', 'litigation_mgmt'):    '/legal/litigation/',
    ('legal', 'compliance_mgmt'):    '/legal/compliance/',
    ('legal', 'corp_gov'):           '/legal/governance/',
    ('risk_management', 'risk_assess'):      '/risk/assessments/',
    ('risk_management', 'risk_register'):    '/risk/register/',
    ('risk_management', 'insurance'):        '/risk/insurance/',
    ('risk_management', 'biz_cont'):         '/risk/continuity/',
    ('risk_management', 'comp_audit'):       '/risk/audits/',
    ('risk_management', 'risk_register_mgr'): '/risk/register/',
    ('risk_management', 'kri'):              '/risk/kri/',
    ('risk_management', 'biz_continuity'):   '/risk/continuity/',
    ('risk_management', 'audit_compliance'): '/risk/audits/',
    # Information Technology dashboard
    ('information_tech', 'it_calls'):    '/it/tickets/',
    ('information_tech', 'it_tasks'):    '/it/tasks/',
    ('information_tech', 'new_ticket'):  '/it/tickets/',
    ('information_tech', 'open_tick'):   '/it/tickets/?status=open',
    ('information_tech', 'my_tickets'):  '/it/tickets/?status=in_progress',
    ('information_tech', 'tick_hist'):   '/it/tickets/?status=resolved',
    ('information_tech', 'asset_inv'):   '/it/assets/',
    ('information_tech', 'new_asset'):   '/it/assets/',
    ('information_tech', 'asset_hist'):  '/it/assets/?status=retired',
    ('information_tech', 'disposition'): '/it/assets/',
    ('information_tech', 'net_dash'):    '/it/network/',
    ('information_tech', 'bw_monitor'):  '/it/network/',
    ('information_tech', 'net_map'):     '/it/network/',
    ('information_tech', 'inc_log'):     '/it/incidents/',
    ('information_tech', 'pend_inst'):   '/it/software/?status=pending',
    ('information_tech', 'sw_inv'):      '/it/software/',
    ('information_tech', 'lic_mgmt'):    '/it/licenses/',
    ('information_tech', 'inst_hist'):   '/it/software/?status=installed',
    ('information_tech', 'new_repair'):  '/it/repairs/',
    ('information_tech', 'inprog'):      '/it/repairs/?status=in_progress',
    ('information_tech', 'comp_rep'):    '/it/repairs/?status=completed',
    ('information_tech', 'rep_hist'):    '/it/repairs/',
    ('information_tech', 'create_acct'): '/it/',
    ('information_tech', 'reset_pw'):    '/it/',
    ('information_tech', 'acct_stat'):   '/it/',
    ('information_tech', 'acct_audit'):  '/it/',
    ('information_tech', 'it_budg'):     '/it/',
    ('information_tech', 'hw_proc'):     '/it/',
    ('information_tech', 'sw_lic'):      '/it/',
    ('information_tech', 'proc_rpts'):   '/it/',
    ('information_tech', 'act_cont'):    '/it/',
    ('information_tech', 'cont_renew'):  '/it/',
    ('information_tech', 'vend_perf'):   '/it/',
    ('information_tech', 'cont_arch'):   '/it/',
    ('information_tech', 'act_proj'):    '/it/',
    ('information_tech', 'proj_pipe'):   '/it/',
    ('information_tech', 'proj_rpts'):   '/it/',
    ('information_tech', 'res_alloc'):   '/it/',
    ('information_tech', 'sec_dash'):    '/it/',
    ('information_tech', 'inc_rpts'):    '/it/',
    ('information_tech', 'vuln_mgmt'):   '/it/',
    ('information_tech', 'comp_rpts'):   '/it/',
    # Customer Service dashboard
    ('customer_service', 'cs_calls'): '/cs-dash/',
    ('customer_service', 'daily_tick'):  '/cs/reports/',
    ('customer_service', 'week_sum'):    '/cs/reports/',
    ('customer_service', 'res_analy'):   '/cs/reports/',
    ('customer_service', 'sla_rpts'):    '/cs/reports/',
    ('customer_service', 'staff_sched'): '/cs-dash/',
    ('customer_service', 'perf_met'):    '/cs-dash/',
    ('customer_service', 'staff_train'): '/cs-dash/',
    ('customer_service', 'staff_rpts'):  '/cs-dash/',
    ('customer_service', 'csat_res'):    '/cs/reports/',
    ('customer_service', 'nps_rpts'):    '/cs/reports/',
    ('customer_service', 'sat_trends'):  '/cs/reports/',
    ('customer_service', 'impr_plans'):  '/cs/plans/',
    ('customer_service', 'act_esc'):     '/cs/escalations/',
    ('customer_service', 'esc_hist'):    '/cs/escalations/',
    ('customer_service', 'esc_rpts'):    '/cs/escalations/',
    ('customer_service', 'res_track'):   '/cs/escalations/',
    # Returns & Refunds
    ('customer_service', 'pend_ret'):    '/cs/returns/',
    ('customer_service', 'refund_proc'): '/cs/returns/',
    ('customer_service', 'ret_rpts'):    '/cs/returns/',
    # Knowledge Base
    ('customer_service', 'browse'):      '/cs/kb/',
    ('customer_service', 'create_art'):  '/cs/kb/',
    ('customer_service', 'art_mgmt'):    '/cs/kb/',
    ('customer_service', 'kb_search'):   '/cs/kb/',
    # Service Reports
    ('customer_service', 'daily_rpt'):   '/cs/reports/',
    ('customer_service', 'res_rpts'):    '/cs/reports/',
    ('customer_service', 'csat_rpts'):   '/cs/reports/',
    # Surveys & Feedback
    ('customer_service', 'act_surv'):    '/cs/surveys/',
    ('customer_service', 'new_surv'):    '/cs/surveys/',
    ('customer_service', 'surv_res'):    '/cs/surveys/',
    ('customer_service', 'feed_rpts'):   '/cs/surveys/',
}


def _init_schema():
    """Create application tables if they don't exist.

    Thin wrapper around the canonical schema module, kept for the
    AppConfig.ready() hook in apps.py.
    """
    init_schema()


# ---------------------------------------------------------------------------
# Login / dashboard / logout
# ---------------------------------------------------------------------------


def home(request):
    # Schema and canonical roles are seeded once at startup by
    # AppConfig.ready() (-> _init_schema), so no per-request seeding here.
    from ..sso_core import is_configured as _sso_is_configured
    sso_enabled = _sso_is_configured()

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        if not email or not password:
            return render(request, 'home.html', {
                'error': 'Please enter both email and password.',
                'email_value': email,
                'sso_enabled': sso_enabled,
            })

        if _verify_login(email, password):
            request.session['user_email'] = email
            profile = _get_user_profile(email)
            request.session['user_role'] = profile.get('role_name', '')
            request.session['user_dept_key'] = profile.get('dept_key') or ''
            request.session['user_dept_name'] = profile.get('dept_name', '')
            request.session['user_full_access'] = _is_full_access(profile)
            request.session['user_is_manager'] = profile.get(
                'is_manager', False)
            if request.session['user_full_access']:
                return redirect('dashboard')
            dept_key = profile.get('dept_key')
            if dept_key:
                return redirect('dept_menu', dept=dept_key)
            return redirect('dashboard')

        return render(request, 'home.html', {
            'error': 'Invalid email or password.',
            'email_value': email,
            'sso_enabled': sso_enabled,
        })

    if request.session.get('user_email'):
        return redirect('dashboard')

    return render(request, 'home.html', {'sso_enabled': sso_enabled})


def dashboard(request):
    email = request.session.get('user_email')
    if not email:
        return redirect('home')
    if not request.session.get('user_full_access'):
        dept_key = request.session.get('user_dept_key')
        if dept_key:
            return redirect('dept_menu', dept=dept_key)
    _dept_dashboard_urls = {
        'accounting': '/acct/',
        'customer_service': '/cs-dash/',
        'engineering': '/eng/',
        'information_tech': '/it/',
        'maintenance': '/maint/',
        'marketing': '/mkt/',
        'personnel': '/pers/',
        'production': '/prod/',
        'inventory': '/inventory/dashboard/',
        'purchasing': '/purch/',
        'quality_assurance': '/qa/',
        'sales': '/sales/',
        'finance': '/fin/',
        'legal': '/legal/',
        'budget_management': '/budget/',
        'risk_management': '/risk/',
        'reports': '/reports/',
    }
    menu_items = [
        (_dept_dashboard_urls.get(key, '/dept/{}/'.format(key)), label)
        for key, label in DASHBOARD_DEPARTMENTS
    ]
    pending_approvals = 0
    kpis = {}
    rev_expense_json = '[]'
    open_items_json = '[]'
    stock_status_json = '{}'
    ar_ap_json = '{}'
    conn = get_db_connection()
    try:
        if request.session.get('user_role') in APPROVAL_ROLES:
            pending_approvals = count_pending(conn)
        kpi_row = conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM work_order
                 WHERE status NOT IN ('completed','cancelled')) AS open_wos,
                (SELECT COUNT(*) FROM purchase_order
                 WHERE status NOT IN ('received','cancelled')) AS open_pos,
                (SELECT COUNT(*) FROM qa_ncr WHERE status != 'Closed') AS open_ncrs,
                (SELECT COUNT(*) FROM maint_work_order
                 WHERE status NOT IN ('Completed','Cancelled')) AS open_maint_wos,
                (SELECT COUNT(*) FROM product
                 WHERE COALESCE(amount,0) > 0 AND reorder_point > 0
                   AND COALESCE(amount,0) <= reorder_point) AS low_stock,
                (SELECT COUNT(*) FROM product
                 WHERE COALESCE(amount,0) <= 0) AS zero_stock
        """).fetchone()
        kpis = dict(kpi_row) if kpi_row else {}
        cash_position = get_cash_position(conn)
        kpis['cash_position'] = cash_position
        rev_expense = get_revenue_expense_by_month(conn)
        rev_expense_json = json.dumps(rev_expense)
        open_items = [
            {'dept': 'Production', 'count': kpis.get('open_wos', 0)},
            {'dept': 'Purchasing', 'count': kpis.get('open_pos', 0)},
            {'dept': 'Quality', 'count': kpis.get('open_ncrs', 0)},
            {'dept': 'Maintenance', 'count': kpis.get('open_maint_wos', 0)},
        ]
        open_items_json = json.dumps(open_items)
        ss_row = conn.execute("""
            SELECT
                COUNT(*) FILTER (WHERE COALESCE(amount,0) <= 0) AS zero,
                COUNT(*) FILTER (
                    WHERE COALESCE(amount,0) > 0 AND reorder_point > 0
                      AND COALESCE(amount,0) <= reorder_point) AS low,
                COUNT(*) FILTER (
                    WHERE COALESCE(amount,0) > 0
                      AND (reorder_point = 0
                           OR COALESCE(amount,0) > reorder_point)) AS ok
            FROM product
        """).fetchone()
        stock_status_json = json.dumps(dict(ss_row) if ss_row else {})
        ar_row = conn.execute("""
            SELECT COALESCE(SUM(amount) FILTER (
                       WHERE status IN ('open','partial','overdue')), 0) AS ar_open
            FROM ar_invoice
        """).fetchone()
        ap_row = conn.execute("""
            SELECT COALESCE(SUM(amount) FILTER (
                       WHERE status IN ('open','partial','overdue')), 0) AS ap_open
            FROM ap_invoice
        """).fetchone()
        ar_ap_json = json.dumps({
            'ar': float(ar_row['ar_open']) if ar_row else 0,
            'ap': float(ap_row['ap_open']) if ap_row else 0,
        })
    finally:
        conn.close()
    return render(request, 'dashboard.html', {
        'email': email,
        'user_role': request.session.get('user_role', ''),
        'dept_name': request.session.get('user_dept_name', ''),
        'full_access': request.session.get('user_full_access', False),
        'menu_items': menu_items,
        'pending_approvals': pending_approvals,
        'kpis': kpis,
        'rev_expense_json': rev_expense_json,
        'open_items_json': open_items_json,
        'stock_status_json': stock_status_json,
        'ar_ap_json': ar_ap_json,
    })


def logout(request):
    email = request.session.get('user_email')
    request.session.flush()
    if email:
        log.info("User %s logged out", email)
    return redirect('home')


def generic_menu(request, dept, subpath=''):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        user_dept = request.session.get('user_dept_key', '')
        if not user_dept:
            return redirect('dashboard')
        if dept != user_dept:
            return redirect('dept_menu', dept=user_dept)
    parts = [p for p in subpath.split('/') if p]
    node = _walk_tree(dept, parts)
    if node is None:
        return redirect('dashboard')

    is_manager = request.session.get('user_is_manager', False)
    items = []
    for key, label, target in node['items']:
        if key in MANAGER_MENU_KEYS and not is_manager:
            continue
        new_parts = parts + [key]
        if isinstance(target, dict):
            url = '/dept/{}/{}/'.format(dept, '/'.join(new_parts))
        else:
            url = WEB_LEAF_URLS[(dept, key)]
        items.append((url, label))

    if parts:
        parent = parts[:-1]
        if parent:
            back_url = '/dept/{}/{}/'.format(dept, '/'.join(parent))
        else:
            back_url = '/dept/{}/'.format(dept)
    else:
        back_url = '/dashboard/'

    return render(request, 'dept_menu.html', {
        'email': request.session['user_email'],
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'title': node['title'],
        'menu_items': items,
        'back_url': back_url,
    })


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register(request):
    if request.method == 'POST':
        first = request.POST.get('first_name', '').strip()
        last = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')
        emp_id_text = request.POST.get('employee_id', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()

        error = None
        if not first or not last:
            error = 'First and last name are required.'
        elif not email or '@' not in email:
            error = 'Please enter a valid email address.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif emp_id_text and not emp_id_text.isdigit():
            error = 'Employee ID must be a number.'

        if error:
            return render(request, 'register.html', {
                          'error': error, 'form': request.POST})

        emp_id = int(emp_id_text) if emp_id_text else 0
        ok = _create_user(email, password, first, last,
                          address, city, state, zip_code, emp_id)

        if ok:
            return render(request, 'home.html', {
                'success': f'Account created for {first} {last}. '
                'You can now log in.',
            })
        return render(request, 'register.html', {
            'error': 'That email address is already registered.',
            'form': request.POST,
        })

    return render(request, 'register.html', {})


# ---------------------------------------------------------------------------
# Forgot password (two-step: verify email, then reset)
# ---------------------------------------------------------------------------

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        if not email or '@' not in email:
            return render(request, 'forgot_password.html', {
                'error': 'Please enter a valid email address.',
                'email_value': email,
            })

        if not _email_exists(email):
            return render(request, 'forgot_password.html', {
                'error': 'No account found for that email address.',
                'email_value': email,
            })

        request.session['reset_email'] = email
        return redirect('forgot_password_reset')

    return render(request, 'forgot_password.html', {})


def forgot_password_reset(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    if request.method == 'POST':
        new_pw = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')

        if len(new_pw) < 8:
            return render(request, 'forgot_password_reset.html', {
                'error': 'Password must be at least 8 characters.',
                'email': email,
            })
        if new_pw != confirm:
            return render(request, 'forgot_password_reset.html', {
                'error': 'Passwords do not match.',
                'email': email,
            })

        ok = _reset_password(email, new_pw)
        if ok:
            del request.session['reset_email']
            return render(request, 'home.html', {
                'success': 'Your password has been reset. You can now log in.',
            })
        return render(request, 'forgot_password_reset.html', {
            'error': 'Password reset failed. Please try again.',
            'email': email,
        })

    return render(request, 'forgot_password_reset.html', {'email': email})


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------

def change_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        current = request.POST.get('current_password', '')
        new_pw = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')

        error = None
        if not email or '@' not in email:
            error = 'Please enter a valid email address.'
        elif not current:
            error = 'Please enter your current password.'
        elif len(new_pw) < 8:
            error = 'New password must be at least 8 characters.'
        elif new_pw != confirm:
            error = 'New passwords do not match.'
        elif new_pw == current:
            error = 'New password must differ from your current password.'

        if error:
            return render(request, 'change_password.html', {
                'error': error,
                'email_value': email,
            })

        if not _verify_login(email, current):
            log.warning(
                "Password change denied for %s: current password incorrect",
                email)
            return render(request, 'change_password.html', {
                'error': 'Incorrect email or current password.',
                'email_value': email,
            })

        _reset_password(email, new_pw)
        return render(request, 'home.html', {
            'success': 'Your password has been changed. You can now log in.',
        })

    return render(request, 'change_password.html', {})


# ---------------------------------------------------------------------------
# User roles
# ---------------------------------------------------------------------------


def user_roles(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') not in _ROLE_ADMIN_ROLES:
        return redirect('dashboard')

    roles = _get_all_roles()

    if request.method == 'POST':
        users = _get_all_users_with_roles()
        for user in users:
            key = f"role_{user['id']}"
            value = request.POST.get(key, '').strip()
            if value:
                _set_user_role(user['id'], int(value))
            else:
                _remove_user_role(user['id'])
        return redirect('user_roles')

    users = _get_all_users_with_roles()
    return render(request, 'user_roles.html', {'users': users, 'roles': roles})


# ---------------------------------------------------------------------------
# Purchase orders (web)
# ---------------------------------------------------------------------------


def _po_context(request, **extra):
    """Toolbar context shared by the PO templates (matches base.html)."""
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


@dept_required('purchasing')
def po_list(request):

    status = request.GET.get('status') or None
    if status not in PO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        pos = list_pos(conn, status=status)
    finally:
        conn.close()

    for po in pos:
        po['status_color'] = PO_STATUS_COLORS.get(po['status'], '#ffffff')

    return render(request, 'po_list.html', _po_context(
        request,
        pos=pos,
        status=status,
        statuses=PO_STATUSES,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/dept/purchasing/purch/purch_orders/',
    ))


@dept_required('purchasing')
def po_export(request):
    status = request.GET.get('status') or None
    if status not in PO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        pos = list_pos(conn, status=status)
    finally:
        conn.close()

    return export_response(request, 'purchase_orders', [
        ('po_number', 'PO #'), ('company_name', 'Supplier'),
        ('order_date', 'Order Date'), ('expected_date', 'Expected Date'),
        ('item_count', 'Items'), ('total', 'Total'), ('status', 'Status'),
    ], pos)


@dept_required('purchasing')
def po_detail(request, po_id):

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        init_currency_schema(conn)
        po = get_po(conn, po_id)
        items = get_po_items(conn, po_id) if po else []
        products = load_products(conn) if (po and can_edit) else []
        approval = get_po_approval(conn, po_id) if po else None
        currencies = list_currencies(conn, active_only=True)
        base_currency = get_base_currency(conn).get("code", "USD")
        ensure_landed_cost_tables(conn)
        conn.commit()
        landed_costs = list_landed_costs(conn, po_id) if po else []
        if request.method == 'POST' and can_edit and po:
            cur_code = request.POST.get('currency', '').strip()
            cur_rate = request.POST.get('exchange_rate', '').strip()
            if cur_code:
                try:
                    conn.execute(
                        "UPDATE purchase_order SET currency=%s, exchange_rate=%s WHERE id=%s",
                        [cur_code, float(cur_rate or 1.0), po_id]
                    )
                    conn.commit()
                    po = get_po(conn, po_id)
                except Exception:
                    conn.rollback()
    finally:
        conn.close()

    if not po:
        return redirect('po_list')

    po['status_color'] = PO_STATUS_COLORS.get(po['status'], '#ffffff')
    if po.get('currency') and po.get('exchange_rate') and po.get('total'):
        po['total_base'] = round(float(po['total']) * float(po['exchange_rate']), 2)

    status_actions = [
        (target, PO_STATUS_ACTION_LABELS.get(target, target))
        for target in allowed_transitions(po['status'])
    ] if can_edit else []
    # Receiving is offered once the PO is out (sent/partial).
    can_receive = can_edit and po['status'] in ('sent', 'partial')

    return render(request, 'po_detail.html', _po_context(
        request,
        po=po,
        items=items,
        products=products,
        can_edit=can_edit,
        status_actions=status_actions,
        can_receive=can_receive,
        approval=approval,
        approval_threshold=APPROVAL_THRESHOLD,
        back_url='/po/',
        currencies=currencies,
        base_currency=base_currency,
        landed_costs=landed_costs,
    ))


# New POs may be created in either of these states; the rest of the workflow
# (sent -> partial -> received, cancelled) is driven by the status actions.
_PO_NEW_STATUSES = ('draft', 'sent')


def _int_or_none(value):
    """Coerce a form value to int, or None when blank/invalid (PO supplier and
    product columns are integer, so a text param would be rejected)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _po_header_form(request):
    """Pull + validate PO header fields from POST. Returns (data, error)."""
    po_number = (request.POST.get('po_number') or '').strip()
    status = request.POST.get('status') or 'draft'
    data = {
        'po_number': po_number,
        'supplier_id': _int_or_none(request.POST.get('supplier_id')),
        'order_date': (request.POST.get('order_date') or '').strip() or None,
        'expected_date':
            (request.POST.get('expected_date') or '').strip() or None,
        'status': status if status in _PO_NEW_STATUSES else 'draft',
        'notes': (request.POST.get('notes') or '').strip() or None,
    }
    if not po_number:
        return data, 'PO number is required.'
    return data, None


@dept_required('purchasing', write_redirect='po_list')
def po_new(request):

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _po_header_form(request)
            if not error and is_period_locked(conn, data.get('order_date')):
                error = ("Period %s is closed."
                         % period_label(*map(int,
                             data['order_date'][:7].split('-'))))
            if not error:
                try:
                    po_id = create_po(
                        conn, **data,
                        created_by=request.session.get('user_email'))
                    conn.commit()
                    return redirect('po_detail', po_id=po_id)
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = ("PO number '%s' already exists."
                             % data['po_number'])
            suppliers = load_suppliers(conn)
            return render(request, 'po_form.html', _po_context(
                request, mode='new', error=error, form=data,
                suppliers=suppliers, statuses=_PO_NEW_STATUSES,
                back_url='/po/'))

        form = {
            'po_number': next_po_number(conn),
            'supplier_id': None,
            'order_date': date.today().isoformat(),
            'expected_date': (date.today() + timedelta(days=14)).isoformat(),
            'status': 'draft',
            'notes': '',
        }
        suppliers = load_suppliers(conn)
    finally:
        conn.close()

    return render(request, 'po_form.html', _po_context(
        request, mode='new', form=form, suppliers=suppliers,
        statuses=_PO_NEW_STATUSES, back_url='/po/'))


@dept_required('purchasing', write_redirect='po_list')
def po_edit(request, po_id):

    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        if not po:
            return redirect('po_list')

        if request.method == 'POST':
            order_date = (request.POST.get('order_date') or '').strip() or None
            if is_period_locked(conn, order_date or po.get('order_date', '')):
                lbl = period_label(*map(int,
                    (order_date or po['order_date'])[:7].split('-')))
                suppliers = load_suppliers(conn)
                form = {
                    'po_number': po['po_number'],
                    'supplier_id': _int_or_none(
                        request.POST.get('supplier_id')),
                    'order_date': order_date or po['order_date'] or '',
                    'expected_date': (
                        request.POST.get('expected_date') or '').strip()
                        or po.get('expected_date') or '',
                    'status': po['status'],
                    'notes': (request.POST.get('notes') or '').strip()
                             or po.get('notes') or '',
                }
                return render(request, 'po_form.html', _po_context(
                    request, mode='edit', po=po, form=form,
                    suppliers=suppliers,
                    error="Period %s is closed." % lbl,
                    back_url='/po/%s/' % po_id))
            update_po(
                conn, po_id,
                supplier_id=_int_or_none(request.POST.get('supplier_id')),
                order_date=order_date,
                expected_date=(request.POST.get('expected_date') or '').strip()
                or None,
                notes=(request.POST.get('notes') or '').strip() or None,
            )
            conn.commit()
            return redirect('po_detail', po_id=po_id)

        suppliers = load_suppliers(conn)
    finally:
        conn.close()

    # po_number/status are not editable here, but shown read-only.
    form = {
        'po_number': po['po_number'],
        'supplier_id': po['supplier_id'],
        'order_date': po['order_date'] or '',
        'expected_date': po['expected_date'] or '',
        'status': po['status'],
        'notes': po['notes'] or '',
    }
    return render(request, 'po_form.html', _po_context(
        request, mode='edit', po=po, form=form, suppliers=suppliers,
        back_url='/po/%s/' % po_id))


@dept_required('purchasing', write_redirect='po_list')
def po_add_item(request, po_id):
    if request.method != 'POST':
        return redirect('po_detail', po_id=po_id)

    description = (request.POST.get('description') or '').strip()
    product_id = _int_or_none(request.POST.get('product_id'))
    try:
        qty = int(request.POST.get('qty_ordered') or 1)
    except ValueError:
        qty = 1
    try:
        unit_price = float(request.POST.get('unit_price') or 0)
    except ValueError:
        unit_price = 0.0

    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        if po and description and qty >= 1 and unit_price >= 0:
            add_po_item(conn, po_id, description, product_id=product_id,
                        qty_ordered=qty, unit_price=unit_price)
            conn.commit()
    finally:
        conn.close()
    return redirect('po_detail', po_id=po_id)


@dept_required('purchasing', write_redirect='po_list')
def po_remove_item(request, po_id):
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        if item_id:
            conn = get_db_connection()
            try:
                delete_po_item(conn, item_id, po_id=po_id)
                conn.commit()
            finally:
                conn.close()
    return redirect('po_detail', po_id=po_id)


@dept_required('purchasing', write_redirect='po_list')
def po_set_status(request, po_id):
    if request.method != 'POST':
        return redirect('po_detail', po_id=po_id)

    target = request.POST.get('status')
    conn = get_db_connection()
    _notify_approval_args = None
    try:
        po = get_po(conn, po_id)
        if po and can_transition(po['status'], target):
            if target == 'sent' and needs_approval(po.get('total', 0)):
                requester = request.session.get('user_email', '')
                request_approval(conn, po_id, requested_by=requester)
                _notify_approval_args = dict(
                    po_number=po['po_number'],
                    po_id=po_id,
                    total=po.get('total', 0),
                    requested_by=requester,
                    site_url=request.build_absolute_uri('/'),
                )
            else:
                set_po_status(conn, po_id, target)
        conn.commit()
        if _notify_approval_args:
            notify_approval_requested(conn, **_notify_approval_args)
    finally:
        conn.close()
    return redirect('po_detail', po_id=po_id)


@dept_required('purchasing', write_redirect='po_list')
def po_receive_item(request, po_id):
    if request.method != 'POST':
        return redirect('po_detail', po_id=po_id)

    item_id = _int_or_none(request.POST.get('item_id'))
    qty = _int_or_none(request.POST.get('qty_received'))
    if item_id is not None and qty is not None and qty >= 0:
        conn = get_db_connection()
        try:
            # Clamp to the ordered quantity so receipts can't exceed the order.
            item = next((i for i in get_po_items(conn, po_id)
                         if i['id'] == item_id), None)
            if item is not None:
                qty = min(qty, item['qty_ordered'])
                receive_po_item(conn, item_id, qty, po_id=po_id)
                # Also credit inventory (into the unassigned bin) so this
                # legacy screen doesn't leave product.amount un-adjusted for
                # anyone not using the newer /wms/receive/ put-away flow.
                ensure_wms_tables(conn)
                delta = qty - (item['qty_received'] or 0)
                credit_unassigned_receipt(
                    conn, item['product_id'], delta,
                    reference=f'PO item {item_id}',
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
        finally:
            conn.close()
    return redirect('po_detail', po_id=po_id)


# ---------------------------------------------------------------------------
# Reports dashboard (web)
# ---------------------------------------------------------------------------


@dept_required('reports')
def reports_dashboard(request):

    conn = get_db_connection()
    try:
        try:
            po = po_summary(conn)
        except Exception:
            po = None
        try:
            wo = wo_summary(conn)
        except Exception:
            wo = None
        try:
            inv = inventory_alerts(conn)
        except Exception:
            inv = None
        try:
            cs = cs_summary(conn)
        except Exception:
            cs = None
    finally:
        conn.close()

    def _status_pills(statuses_tuple, colors, by_status):
        return [
            (s.replace('_', ' ').title(), by_status.get(s, 0),
             colors.get(s, '#fff'))
            for s in statuses_tuple
        ]

    return render(request, 'reports_dashboard.html', {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'po': po,
        'wo': wo,
        'inv': inv,
        'cs': cs,
        'po_statuses': _status_pills(PO_STATUSES, PO_STATUS_COLORS,
                                     po['by_status'] if po else {}),
        'wo_statuses': _status_pills(WO_STATUSES, WO_STATUS_COLORS,
                                     wo['by_status'] if wo else {}),
    })


# ---------------------------------------------------------------------------
# Work orders (web)
# ---------------------------------------------------------------------------

_WO_DEPT_KEYS = {'maintenance', 'production'}
_WO_NEW_STATUSES = ('draft', 'open')


def _wo_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


@dept_required(_WO_DEPT_KEYS)
def wo_list(request):

    status = request.GET.get('status') or None
    if status not in WO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        wos = list_wos(conn, status=status)
    finally:
        conn.close()

    for wo in wos:
        wo['status_color'] = WO_STATUS_COLORS.get(wo['status'], '#ffffff')
        wo['status_label'] = wo['status'].replace('_', ' ').title()

    dept = request.session.get('user_dept_key', 'production')
    back_url = (
        f'/dept/{dept}/work_orders/'
        if dept in _WO_DEPT_KEYS else '/dashboard/'
    )

    return render(request, 'wo_list.html', _wo_context(
        request,
        wos=wos,
        status=status,
        statuses=[(s, s.replace('_', ' ').title()) for s in WO_STATUSES],
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url=back_url,
    ))


@dept_required(_WO_DEPT_KEYS)
def wo_export(request):
    status = request.GET.get('status') or None
    if status not in WO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        wos = list_wos(conn, status=status)
    finally:
        conn.close()

    return export_response(request, 'work_orders', [
        ('wo_number', 'WO #'), ('product_name', 'Product'),
        ('description', 'Description'), ('quantity', 'Qty'),
        ('start_date', 'Start Date'), ('due_date', 'Due Date'),
        ('status', 'Status'), ('mat_count', 'Materials'),
    ], wos)


@dept_required(_WO_DEPT_KEYS)
def wo_detail(request, wo_id):

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    schedule_error = schedule_success = None
    conn = get_db_connection()
    try:
        wo = get_wo(conn, wo_id)
        if not wo:
            return redirect('wo_list')

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                capacity_planning_core.ensure_capacity_tables(conn)
                if action == 'forward_schedule':
                    result = capacity_planning_core.forward_schedule_wo(conn, wo_id)
                    conn.commit()
                    schedule_success = (
                        f"Scheduled {len(result['operations'])} operation(s) forward — "
                        f"finishes {result['computed_end_date']}."
                    )
                elif action == 'backward_schedule':
                    result = capacity_planning_core.backward_schedule_wo(conn, wo_id)
                    conn.commit()
                    schedule_success = (
                        f"Scheduled {len(result['operations'])} operation(s) backward from "
                        f"the due date — must start {result['computed_start_date']}."
                    )
                    if result['at_risk']:
                        schedule_success += (
                            " This is before today — the due date is at risk."
                        )
            except ValueError as exc:
                conn.rollback()
                schedule_error = str(exc)

        materials = get_wo_materials(conn, wo_id)
        products = load_wo_products(conn) if can_edit else []
        operations, wo_labor_cost, wo_cost = [], None, None
        try:
            routing_core.ensure_routing_tables(conn)
            operations = routing_core.get_wo_operations(conn, wo_id)
            if operations:
                wo_labor_cost = routing_core.get_wo_labor_cost(conn, wo_id)
        except Exception:
            pass
        try:
            costing_core.ensure_costing_tables(conn)
            wo_cost = costing_core.get_wo_cost(conn, wo_id)
        except Exception:
            pass
    finally:
        conn.close()

    wo['status_color'] = WO_STATUS_COLORS.get(wo['status'], '#ffffff')
    wo['status_label'] = wo['status'].replace('_', ' ').title()
    status_actions = [
        (target, WO_STATUS_ACTION_LABELS.get(target, target))
        for target in wo_allowed_transitions(wo['status'])
    ] if can_edit else []

    return render(request, 'wo_detail.html', _wo_context(
        request,
        wo=wo,
        materials=materials,
        products=products,
        can_edit=can_edit,
        status_actions=status_actions,
        back_url='/wo/',
        operations=operations,
        wo_labor_cost=wo_labor_cost,
        wo_cost=wo_cost,
        schedule_error=schedule_error,
        schedule_success=schedule_success,
    ))


def _wo_header_form(request):
    """Pull + validate WO header fields from POST. Returns (data, error)."""
    wo_number = (request.POST.get('wo_number') or '').strip()
    status = request.POST.get('status') or 'draft'
    try:
        quantity = int(request.POST.get('quantity') or 1)
        quantity = max(1, quantity)
    except ValueError:
        quantity = 1
    data = {
        'wo_number': wo_number,
        'product_id': _int_or_none(request.POST.get('product_id')),
        'description': (request.POST.get('description') or '').strip() or None,
        'quantity': quantity,
        'start_date': (request.POST.get('start_date') or '').strip() or None,
        'due_date': (request.POST.get('due_date') or '').strip() or None,
        'status': status if status in _WO_NEW_STATUSES else 'draft',
        'notes': (request.POST.get('notes') or '').strip() or None,
    }
    if not wo_number:
        return data, 'WO number is required.'
    return data, None


@dept_required(_WO_DEPT_KEYS, write_redirect='wo_list')
def wo_new(request):

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _wo_header_form(request)
            if not error and is_period_locked(conn, data.get('start_date')):
                error = ("Period %s is closed."
                         % period_label(*map(int,
                             data['start_date'][:7].split('-'))))
            if not error:
                try:
                    wo_id = create_wo(
                        conn, **data,
                        created_by=request.session.get('user_email'))
                    conn.commit()
                    return redirect('wo_detail', wo_id=wo_id)
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = ("WO number '%s' already exists."
                             % data['wo_number'])
            products = load_wo_products(conn)
            return render(request, 'wo_form.html', _wo_context(
                request, mode='new', error=error, form=data,
                products=products, statuses=_WO_NEW_STATUSES,
                back_url='/wo/'))

        form = {
            'wo_number': next_wo_number(conn),
            'product_id': None,
            'description': '',
            'quantity': 1,
            'start_date': date.today().isoformat(),
            'due_date': '',
            'status': 'draft',
            'notes': '',
        }
        products = load_wo_products(conn)
    finally:
        conn.close()

    return render(request, 'wo_form.html', _wo_context(
        request, mode='new', form=form, products=products,
        statuses=_WO_NEW_STATUSES, back_url='/wo/'))


@dept_required(_WO_DEPT_KEYS, write_redirect='wo_list')
def wo_edit(request, wo_id):

    conn = get_db_connection()
    try:
        wo = get_wo(conn, wo_id)
        if not wo:
            return redirect('wo_list')

        if request.method == 'POST':
            try:
                quantity = int(request.POST.get('quantity') or 1)
                quantity = max(1, quantity)
            except ValueError:
                quantity = 1
            start_date = (request.POST.get('start_date') or '').strip() or None
            if is_period_locked(conn, start_date or wo.get('start_date', '')):
                lbl = period_label(*map(int,
                    (start_date or wo['start_date'])[:7].split('-')))
                products = load_wo_products(conn)
                form = {
                    'wo_number': wo['wo_number'],
                    'product_id': _int_or_none(
                        request.POST.get('product_id')),
                    'description': (
                        request.POST.get('description') or '').strip()
                        or wo.get('description') or '',
                    'quantity': quantity,
                    'start_date': start_date or wo.get('start_date') or '',
                    'due_date': (request.POST.get('due_date') or '').strip()
                                or wo.get('due_date') or '',
                    'status': wo['status'],
                    'notes': (request.POST.get('notes') or '').strip()
                             or wo.get('notes') or '',
                }
                return render(request, 'wo_form.html', _wo_context(
                    request, mode='edit', wo=wo, form=form,
                    products=products,
                    error="Period %s is closed." % lbl,
                    back_url='/wo/%s/' % wo_id))
            update_wo(
                conn, wo_id,
                product_id=_int_or_none(request.POST.get('product_id')),
                description=(request.POST.get('description') or '').strip()
                or None,
                quantity=quantity,
                start_date=start_date,
                due_date=(request.POST.get('due_date') or '').strip() or None,
                notes=(request.POST.get('notes') or '').strip() or None,
            )
            conn.commit()
            return redirect('wo_detail', wo_id=wo_id)

        products = load_wo_products(conn)
    finally:
        conn.close()

    form = {
        'wo_number': wo['wo_number'],
        'product_id': wo.get('product_id'),
        'description': wo.get('description') or '',
        'quantity': wo.get('quantity') or 1,
        'start_date': wo.get('start_date') or '',
        'due_date': wo.get('due_date') or '',
        'status': wo['status'],
        'notes': wo.get('notes') or '',
    }
    return render(request, 'wo_form.html', _wo_context(
        request, mode='edit', wo=wo, form=form, products=products,
        back_url='/wo/%s/' % wo_id))


@dept_required(_WO_DEPT_KEYS, write_redirect='wo_list')
def wo_add_material(request, wo_id):
    if request.method != 'POST':
        return redirect('wo_detail', wo_id=wo_id)

    product_id = _int_or_none(request.POST.get('product_id'))
    try:
        qty_required = int(request.POST.get('qty_required') or 1)
        qty_required = max(1, qty_required)
    except ValueError:
        qty_required = 1
    notes = (request.POST.get('notes') or '').strip() or None

    if product_id is not None:
        conn = get_db_connection()
        try:
            wo = get_wo(conn, wo_id)
            if wo:
                add_wo_material(conn, wo_id, product_id,
                                qty_required=qty_required, notes=notes)
                conn.commit()
        finally:
            conn.close()
    return redirect('wo_detail', wo_id=wo_id)


@dept_required(_WO_DEPT_KEYS, write_redirect='wo_list')
def wo_set_status(request, wo_id):
    if request.method != 'POST':
        return redirect('wo_detail', wo_id=wo_id)

    target = request.POST.get('status')
    conn = get_db_connection()
    try:
        wo = get_wo(conn, wo_id)
        if wo and wo_can_transition(wo['status'], target):
            set_wo_status(conn, wo_id, target)
            conn.commit()
    finally:
        conn.close()
    return redirect('wo_detail', wo_id=wo_id)


# ---------------------------------------------------------------------------
# Sales orders (web)
# ---------------------------------------------------------------------------

_SO_NEW_STATUSES = ('draft', 'confirmed')


def _so_context(request, **extra):
    """Toolbar context shared by the SO templates."""
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def _so_customer_name(so):
    return (
        so.get('company_name')
        or f"{so.get('first_name') or ''} {so.get('last_name') or ''}".strip()
        or '—'
    )


@dept_required('sales')
def so_list(request):

    status = request.GET.get('status') or None
    if status not in SO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        sos = list_sos(conn, status=status)
    finally:
        conn.close()

    for so in sos:
        so['status_color'] = SO_STATUS_COLORS.get(so['status'], '#ffffff')
        so['customer_name'] = _so_customer_name(so)

    return render(request, 'so_list.html', _so_context(
        request,
        sos=sos,
        status=status,
        statuses=SO_STATUSES,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/dept/sales/sales/sales_orders/',
    ))


@dept_required('sales')
def so_export(request):
    status = request.GET.get('status') or None
    if status not in SO_STATUSES:
        status = None

    conn = get_db_connection()
    try:
        sos = list_sos(conn, status=status)
    finally:
        conn.close()

    for so in sos:
        so['customer_name'] = _so_customer_name(so)

    return export_response(request, 'sales_orders', [
        ('so_number', 'SO #'), ('customer_name', 'Customer'),
        ('order_date', 'Order Date'), ('ship_date', 'Ship Date'),
        ('item_count', 'Items'), ('total', 'Total'), ('status', 'Status'),
    ], sos)


@dept_required('sales')
def so_detail(request, so_id):

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        init_currency_schema(conn)
        so = get_so(conn, so_id)
        items = get_so_items(conn, so_id) if so else []
        products = load_so_products(conn) if (so and can_edit) else []
        currencies = list_currencies(conn)
        base_currency = get_base_currency(conn).get("code", "USD")
        price_tiers = (
            get_customer_price_tiers(conn, so['customer_id'])
            if (so and can_edit and so.get('customer_id')) else {}
        )
        ensure_discount_tables(conn)
        promo_tiers = (
            get_promotion_tiers_for_customer(conn, so['customer_id'])
            if (so and can_edit and so.get('customer_id')) else {}
        )
        atp_by_product = (
            get_atp_qty_for_products(conn, so.get('ship_date') or date.today().isoformat())
            if (so and can_edit) else {}
        )
        atp_warning = None
        capacity_warning = None
        if so and can_edit and request.GET.get('atp_pending'):
            atp_warning = check_so_atp(conn, so_id) or None
            capacity_warning = check_so_capacity(conn, so_id) or None

        if request.method == 'POST' and request.POST.get('action') == 'currency' and can_edit and so:
            cur_code = request.POST.get('currency', 'USD')
            exc_rate = float(request.POST.get('exchange_rate', 1.0) or 1.0)
            conn.execute(
                "UPDATE sales_order SET currency=%s, exchange_rate=%s WHERE id=%s",
                [cur_code, exc_rate, so_id]
            )
            conn.commit()
            return redirect('so_detail', so_id=so_id)
    finally:
        conn.close()

    if not so:
        return redirect('so_list')

    so['status_color'] = SO_STATUS_COLORS.get(so['status'], '#ffffff')
    so['customer_name'] = _so_customer_name(so)
    if so.get('currency') and so.get('exchange_rate') and so.get('total'):
        so['total_base'] = round(float(so['total']) * float(so['exchange_rate']), 2)

    status_actions = [
        (target, SO_STATUS_ACTION_LABELS.get(target, target))
        for target in so_allowed_transitions(so['status'])
    ] if can_edit else []

    return render(request, 'so_detail.html', _so_context(
        request,
        so=so,
        items=items,
        products=products,
        can_edit=can_edit,
        status_actions=status_actions,
        currencies=currencies,
        base_currency=base_currency,
        price_tiers_json=json.dumps(price_tiers),
        promo_tiers_json=json.dumps(promo_tiers),
        atp_json=json.dumps(atp_by_product),
        atp_warning=atp_warning,
        capacity_warning=capacity_warning,
        pending_status=request.GET.get('atp_pending'),
        back_url='/so/',
    ))


def _so_header_form(request):
    """Pull + validate SO header fields from POST. Returns (data, error)."""
    so_number = (request.POST.get('so_number') or '').strip()
    status = request.POST.get('status') or 'draft'
    data = {
        'so_number': so_number,
        'customer_id': _int_or_none(request.POST.get('customer_id')),
        'order_date': (request.POST.get('order_date') or '').strip() or None,
        'ship_date': (request.POST.get('ship_date') or '').strip() or None,
        'status': status if status in _SO_NEW_STATUSES else 'draft',
        'notes': (request.POST.get('notes') or '').strip() or None,
    }
    if not so_number:
        return data, 'SO number is required.'
    return data, None


@dept_required('sales', write_redirect='so_list')
def so_new(request):

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _so_header_form(request)
            if not error and is_period_locked(conn, data.get('order_date')):
                error = ("Period %s is closed."
                         % period_label(*map(int,
                             data['order_date'][:7].split('-'))))
            if not error:
                try:
                    so_id = create_so(
                        conn, **data,
                        created_by=request.session.get('user_email'))
                    conn.commit()
                    return redirect('so_detail', so_id=so_id)
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = ("SO number '%s' already exists."
                             % data['so_number'])
            customers = load_customers(conn)
            return render(request, 'so_form.html', _so_context(
                request, mode='new', error=error, form=data,
                customers=customers, statuses=_SO_NEW_STATUSES,
                back_url='/so/'))

        form = {
            'so_number': next_so_number(conn),
            'customer_id': None,
            'order_date': date.today().isoformat(),
            'ship_date': '',
            'status': 'draft',
            'notes': '',
        }
        customers = load_customers(conn)
    finally:
        conn.close()

    return render(request, 'so_form.html', _so_context(
        request, mode='new', form=form, customers=customers,
        statuses=_SO_NEW_STATUSES, back_url='/so/'))


@dept_required('sales', write_redirect='so_list')
def so_edit(request, so_id):

    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        if not so:
            return redirect('so_list')

        if request.method == 'POST':
            order_date = (request.POST.get('order_date') or '').strip() or None
            if is_period_locked(conn, order_date or so.get('order_date', '')):
                lbl = period_label(*map(int,
                    (order_date or so['order_date'])[:7].split('-')))
                customers = load_customers(conn)
                form = {
                    'so_number': so['so_number'],
                    'customer_id': _int_or_none(
                        request.POST.get('customer_id')),
                    'order_date': order_date or so['order_date'] or '',
                    'ship_date': (
                        request.POST.get('ship_date') or '').strip()
                        or so.get('ship_date') or '',
                    'status': so['status'],
                    'notes': (request.POST.get('notes') or '').strip()
                             or so.get('notes') or '',
                }
                return render(request, 'so_form.html', _so_context(
                    request, mode='edit', so=so, form=form,
                    customers=customers,
                    error="Period %s is closed." % lbl,
                    back_url='/so/%s/' % so_id))
            update_so(
                conn, so_id,
                customer_id=_int_or_none(request.POST.get('customer_id')),
                order_date=order_date,
                ship_date=(request.POST.get('ship_date') or '').strip()
                or None,
                notes=(request.POST.get('notes') or '').strip() or None,
            )
            conn.commit()
            return redirect('so_detail', so_id=so_id)

        customers = load_customers(conn)
    finally:
        conn.close()

    form = {
        'so_number': so['so_number'],
        'customer_id': so['customer_id'],
        'order_date': so['order_date'] or '',
        'ship_date': so['ship_date'] or '',
        'status': so['status'],
        'notes': so['notes'] or '',
    }
    return render(request, 'so_form.html', _so_context(
        request, mode='edit', so=so, form=form, customers=customers,
        back_url='/so/%s/' % so_id))


@dept_required('sales', write_redirect='so_list')
def so_add_item(request, so_id):
    if request.method != 'POST':
        return redirect('so_detail', so_id=so_id)

    description = (request.POST.get('description') or '').strip()
    product_id = _int_or_none(request.POST.get('product_id'))
    try:
        qty = int(request.POST.get('qty') or 1)
        qty = max(1, qty)
    except ValueError:
        qty = 1
    try:
        unit_price = float(request.POST.get('unit_price') or 0)
    except ValueError:
        unit_price = 0.0

    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        if so and description and qty >= 1 and unit_price >= 0:
            add_so_item(conn, so_id, description, product_id=product_id,
                        qty=qty, unit_price=unit_price)
            conn.commit()
    finally:
        conn.close()
    return redirect('so_detail', so_id=so_id)


@dept_required('sales', write_redirect='so_list')
def so_remove_item(request, so_id):
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        if item_id:
            conn = get_db_connection()
            try:
                delete_so_item(conn, item_id, so_id=so_id)
                conn.commit()
            finally:
                conn.close()
    return redirect('so_detail', so_id=so_id)


@dept_required('sales', write_redirect='so_list')
def so_set_status(request, so_id):
    if request.method != 'POST':
        return redirect('so_detail', so_id=so_id)

    target = request.POST.get('status')
    override = request.POST.get('override') == '1'
    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        if so and so_can_transition(so['status'], target):
            if (target == 'confirmed' and not override
                    and (check_so_atp(conn, so_id) or check_so_capacity(conn, so_id))):
                return redirect(reverse('so_detail', args=[so_id]) + '?atp_pending=confirmed')
            set_so_status(conn, so_id, target)
            conn.commit()
    finally:
        conn.close()
    return redirect('so_detail', so_id=so_id)


# ---------------------------------------------------------------------------
# Personnel — employee directory + time-off requests (web)
# ---------------------------------------------------------------------------

_PERSONNEL_ROLES = {'HR / Personnel'}




def _people_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def _is_hr(request):
    """True if the user has personnel/HR access (can approve time-off etc.)."""
    return (
        request.session.get('user_full_access')
        or request.session.get('user_role') in _PERSONNEL_ROLES
        or request.session.get('user_dept_key') == 'personnel'
    )


@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def people_list(request):

    dept_id = _int_or_none(request.GET.get('dept_id'))
    search = (request.GET.get('search') or '').strip() or None

    conn = get_db_connection()
    try:
        people = list_people(conn, dept_id=dept_id, search=search)
        depts = load_depts(conn)
    finally:
        conn.close()

    if 'export' in request.GET:
        return export_response(request, 'employees', [
            ('id', 'ID'), ('first_name', 'First Name'), ('last_name', 'Last Name'),
            ('email', 'Email'), ('dept_name', 'Department'), ('job_title', 'Job Title'),
            ('employee_id', 'Employee ID'),
        ], people)

    return render(request, 'people_list.html', _people_context(
        request,
        people=people,
        depts=depts,
        dept_id=dept_id,
        search=search or '',
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/dept/personnel/pers_menu/emp_records/',
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def people_detail(request, person_id):

    conn = get_db_connection()
    try:
        person = get_person(conn, person_id)
    finally:
        conn.close()

    if not person:
        return redirect('people_list')

    return render(request, 'people_detail.html', _people_context(
        request,
        person=person,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/people/',
    ))


def _people_form(request):
    """Pull + validate person fields from POST. Returns (data, error)."""
    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    if not first_name or not last_name:
        data = {k: (request.POST.get(k) or '') for k in [
            'first_name', 'last_name', 'employee_id', 'email',
            'job_title', 'address', 'city', 'state', 'zip_code']}
        data['dept_id'] = _int_or_none(request.POST.get('dept_id'))
        data['dept_sub_id'] = _int_or_none(request.POST.get('dept_sub_id'))
        return data, 'First name and last name are required.'
    return {
        'first_name': first_name,
        'last_name': last_name,
        'employee_id': _int_or_none(request.POST.get('employee_id')) or 0,
        'email': (request.POST.get('email') or '').strip(),
        'job_title': (request.POST.get('job_title') or '').strip(),
        'address': (request.POST.get('address') or '').strip(),
        'city': (request.POST.get('city') or '').strip(),
        'state': (request.POST.get('state') or '').strip(),
        'zip_code': (request.POST.get('zip_code') or '').strip(),
        'dept_id': _int_or_none(request.POST.get('dept_id')),
        'dept_sub_id': _int_or_none(request.POST.get('dept_sub_id')),
    }, None


@dept_required('personnel', role_keys=_PERSONNEL_ROLES, write_redirect='people_list')
def people_new(request):

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _people_form(request)
            if not error:
                person_id = create_person(
                    conn,
                    first_name=data['first_name'], last_name=data['last_name'],
                    employee_id=int(data['employee_id'] or 0), email=data['email'],
                    address=data['address'], city=data['city'], state=data['state'],
                    zip_code=data['zip_code'], dept_id=data['dept_id'],
                    dept_sub_id=data['dept_sub_id'], job_title=data['job_title'],
                    created_by=request.session.get('user_email'))
                conn.commit()
                return redirect('people_detail', person_id=person_id)
            depts = load_depts(conn)
            dept_subs = load_dept_subs(conn)
            return render(request, 'people_form.html', _people_context(
                request, mode='new', error=error, form=data,
                depts=depts, dept_subs=dept_subs, back_url='/people/'))

        depts = load_depts(conn)
        dept_subs = load_dept_subs(conn)
    finally:
        conn.close()

    form = {
        'first_name': '', 'last_name': '', 'employee_id': '', 'email': '',
        'job_title': '', 'address': '', 'city': '', 'state': '',
        'zip_code': '', 'dept_id': None, 'dept_sub_id': None,
    }
    return render(request, 'people_form.html', _people_context(
        request, mode='new', form=form, depts=depts, dept_subs=dept_subs,
        back_url='/people/'))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES, write_redirect='people_list')
def people_edit(request, person_id):

    conn = get_db_connection()
    try:
        person = get_person(conn, person_id)
        if not person:
            return redirect('people_list')

        if request.method == 'POST':
            data, error = _people_form(request)
            if not error:
                update_person(
                    conn, person_id,
                    first_name=data['first_name'], last_name=data['last_name'],
                    employee_id=int(data['employee_id'] or 0), email=data['email'],
                    address=data['address'], city=data['city'], state=data['state'],
                    zip_code=data['zip_code'], dept_id=data['dept_id'],
                    dept_sub_id=data['dept_sub_id'], job_title=data['job_title'])
                conn.commit()
                return redirect('people_detail', person_id=person_id)
            depts = load_depts(conn)
            dept_subs = load_dept_subs(conn)
            return render(request, 'people_form.html', _people_context(
                request, mode='edit', person=person, error=error, form=data,
                depts=depts, dept_subs=dept_subs,
                back_url='/people/%s/' % person_id))

        depts = load_depts(conn)
        dept_subs = load_dept_subs(conn)
    finally:
        conn.close()

    form = {
        'first_name': person['first_name'],
        'last_name': person['last_name'],
        'employee_id': person['employee_id'] or '',
        'email': person['email'] or '',
        'job_title': person['job_title'] or '',
        'address': person['address'] or '',
        'city': person['city'] or '',
        'state': person['state'] or '',
        'zip_code': person['zip_code'] or '',
        'dept_id': person['dept_id'],
        'dept_sub_id': person['dept_sub_id'],
    }
    return render(request, 'people_form.html', _people_context(
        request, mode='edit', person=person, form=form,
        depts=depts, dept_subs=dept_subs,
        back_url='/people/%s/' % person_id))


# --- Time-off requests ---

def time_off_list(request):
    if not request.session.get('user_email'):
        return redirect('home')

    status = request.GET.get('status') or None
    if status not in TIME_OFF_STATUSES:
        status = None

    is_hr_user = _is_hr(request)
    email = request.session.get('user_email', '')

    conn = get_db_connection()
    try:
        people_id = None
        if not is_hr_user:
            p = get_person_by_email(conn, email)
            people_id = p['id'] if p else -1
        requests = list_time_off_requests(conn, people_id=people_id,
                                          status=status)
    finally:
        conn.close()

    back_url = (
        '/dept/personnel/pers_menu/time_clock/time_off/'
        if request.session.get('user_dept_key') == 'personnel'
        else '/dashboard/'
    )

    if 'export' in request.GET:
        return export_response(request, 'time_off_requests', [
            ('id', 'ID'), ('first_name', 'First Name'), ('last_name', 'Last Name'),
            ('start_date', 'Start Date'), ('end_date', 'End Date'),
            ('request_type', 'Type'), ('status', 'Status'), ('notes', 'Notes'),
        ], requests)

    return render(request, 'time_off_list.html', _people_context(
        request,
        requests=requests,
        status=status,
        statuses=TIME_OFF_STATUSES,
        is_hr=is_hr_user,
        back_url=back_url,
    ))


def time_off_new(request):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('time_off_list')

    email = request.session.get('user_email', '')

    if request.method == 'POST':
        start_date = (request.POST.get('start_date') or '').strip()
        end_date = (request.POST.get('end_date') or '').strip()
        request_type = request.POST.get('request_type') or 'Vacation'
        if request_type not in TIME_OFF_TYPES:
            request_type = 'Vacation'
        notes = (request.POST.get('notes') or '').strip() or None
        error = None
        if not start_date or not end_date:
            error = 'Start date and end date are required.'
        elif end_date < start_date:
            error = 'End date must be on or after start date.'
        if not error:
            conn = get_db_connection()
            try:
                p = get_person_by_email(conn, email)
                if not p:
                    error = 'Your employee record was not found.'
                else:
                    create_time_off_request(
                        conn, p['id'], start_date, end_date,
                        request_type=request_type, notes=notes,
                        created_by=email)
                    conn.commit()
                    return redirect('time_off_list')
            finally:
                conn.close()
        return render(request, 'time_off_form.html', _people_context(
            request, error=error,
            form={'start_date': start_date, 'end_date': end_date,
                  'request_type': request_type, 'notes': notes or ''},
            types=TIME_OFF_TYPES, back_url='/time-off/'))

    form = {
        'start_date': date.today().isoformat(),
        'end_date': '',
        'request_type': 'Vacation',
        'notes': '',
    }
    return render(request, 'time_off_form.html', _people_context(
        request, form=form, types=TIME_OFF_TYPES, back_url='/time-off/'))


def time_off_detail(request, req_id):
    if not request.session.get('user_email'):
        return redirect('home')

    is_hr_user = _is_hr(request)
    email = request.session.get('user_email', '')

    conn = get_db_connection()
    try:
        req = get_time_off_request(conn, req_id)
        if not req:
            return redirect('time_off_list')

        # Non-HR users may only view their own requests.
        if not is_hr_user:
            p = get_person_by_email(conn, email)
            if not p or p['id'] != req['people_id']:
                return redirect('time_off_list')

        if request.method == 'POST' and is_hr_user:
            new_status = request.POST.get('status')
            if new_status in TIME_OFF_STATUSES and new_status != 'pending':
                set_time_off_status(conn, req_id, new_status)
                conn.commit()
                return redirect('time_off_detail', req_id=req_id)
    finally:
        conn.close()

    return render(request, 'time_off_detail.html', _people_context(
        request,
        req=req,
        is_hr=is_hr_user,
        can_act=is_hr_user and req['status'] == 'pending',
        back_url='/time-off/',
    ))


# ---------------------------------------------------------------------------
# Time clock — punch in/out, hours, attendance (web)
# ---------------------------------------------------------------------------

_TC_BACK = '/dept/personnel/pers_menu/time_clock/'


def _tc_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def time_clock_status(request):
    """Punch in / punch out page and current status."""
    if not request.session.get('user_email'):
        return redirect('home')
    email = request.session.get('user_email', '')

    conn = get_db_connection()
    try:
        person = get_person_by_email(conn, email)
        if not person:
            return render(request, 'time_clock_status.html', _tc_context(
                request, error='Your employee record was not found.',
                current=None, today_entries=[], back_url=_TC_BACK))

        people_id = person['id']

        if request.method == 'POST':
            action = request.POST.get('action')
            current = get_current_entry(conn, people_id)
            if action == 'clock_in' and not current:
                tc_clock_in(conn, people_id, created_by=email)
                conn.commit()
            elif action == 'clock_out' and current:
                clock_out_entry(conn, current['id'])
                conn.commit()
            return redirect('time_clock_status')

        current = get_current_entry(conn, people_id)
        today = __import__('datetime').date.today().isoformat()
        today_entries = list_entries(conn, people_id,
                                     date_from=today, date_to=today)
        _, total_fmt = tc_total_hours(today_entries)
    finally:
        conn.close()

    return render(request, 'time_clock_status.html', _tc_context(
        request,
        current=current,
        today_entries=today_entries,
        total_fmt=total_fmt,
        back_url=_TC_BACK,
    ))


def time_clock_hours(request):
    """View personal hours for today / this week / this month."""
    if not request.session.get('user_email'):
        return redirect('home')
    email = request.session.get('user_email', '')

    period = request.GET.get('period', 'today')
    if period not in ('today', 'week', 'month'):
        period = 'today'
    date_from, date_to = get_period_dates(period)

    conn = get_db_connection()
    try:
        person = get_person_by_email(conn, email)
        if not person:
            return render(request, 'time_clock_hours.html', _tc_context(
                request, error='Your employee record was not found.',
                entries=[], period=period, total_fmt='0:00',
                back_url=_TC_BACK))
        entries = list_entries(conn, person['id'],
                               date_from=date_from, date_to=date_to)
        _, total_fmt = tc_total_hours(entries)
    finally:
        conn.close()

    return render(request, 'time_clock_hours.html', _tc_context(
        request,
        entries=entries,
        period=period,
        date_from=date_from,
        date_to=date_to,
        total_fmt=total_fmt,
        back_url=_TC_BACK,
    ))


def time_clock_attendance(request):
    """HR attendance view — all employees for a given date."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _is_hr(request):
        return redirect('time_clock_status')

    date_str = (request.GET.get('date') or '').strip()
    if not date_str:
        date_str = __import__('datetime').date.today().isoformat()

    conn = get_db_connection()
    try:
        attendance = get_attendance(conn, date_str)
    finally:
        conn.close()

    present = sum(1 for p in attendance if p['present'])
    absent = len(attendance) - present

    return render(request, 'time_clock_attendance.html', _tc_context(
        request,
        attendance=attendance,
        date_str=date_str,
        present=present,
        absent=absent,
        back_url=_TC_BACK,
    ))


# ── Time Clock Device Management ──────────────────────────────────────────

_DEV_BACK = '/time-clock/devices/'


@dept_required('personnel', role_keys=_PERSONNEL_ROLES, deny_redirect='time_clock_status')
def tc_device_list(request):
    """List all registered time clock terminals."""

    conn = get_db_connection()
    try:
        devices = list_devices(conn)
    finally:
        conn.close()

    return render(request, 'tc_device_list.html', _tc_context(
        request,
        devices=devices,
        device_type_labels=DEVICE_TYPE_LABELS,
        back_url='/time-clock/',
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES, deny_redirect='time_clock_status')
def tc_device_new(request):
    """Add a new time clock device — asks for type, then shows config fields."""

    error = ''
    form: dict = {
        'name': '', 'location': '', 'device_type': '',
        'ip_address': '', 'port': '', 'config_json': '{}',
    }

    if request.method == 'POST':
        form = {
            'name': request.POST.get('name', '').strip(),
            'location': request.POST.get('location', '').strip(),
            'device_type': request.POST.get('device_type', '').strip(),
            'ip_address': request.POST.get('ip_address', '').strip(),
            'port': request.POST.get('port', '').strip(),
            'config_json': request.POST.get('config_json', '{}').strip(),
        }
        if not form['name']:
            error = 'Name is required.'
        elif form['device_type'] not in DEVICE_TYPES:
            error = 'Please select a valid device type.'
        else:
            try:
                port = int(form['port']) if form['port'] else 0
            except ValueError:
                port = 0
            conn = get_db_connection()
            try:
                create_device(
                    conn,
                    name=form['name'],
                    location=form['location'],
                    device_type=form['device_type'],
                    ip_address=form['ip_address'],
                    port=port,
                    config_json=form['config_json'] or '{}',
                    created_by=request.session.get('user_email'),
                )
                conn.commit()
            finally:
                conn.close()
            return redirect('tc_device_list')

    return render(request, 'tc_device_form.html', _tc_context(
        request,
        form=form,
        error=error,
        device_types=DEVICE_TYPES,
        device_type_labels=DEVICE_TYPE_LABELS,
        is_new=True,
        back_url=_DEV_BACK,
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES, deny_redirect='time_clock_status')
def tc_device_detail(request, device_id: int):
    """Edit a device or view its sync log."""

    conn = get_db_connection()
    try:
        device = get_device(conn, device_id)
        if not device:
            return redirect('tc_device_list')

        error = ''
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            location = request.POST.get('location', '').strip()
            device_type = request.POST.get('device_type', '').strip()
            ip_address = request.POST.get('ip_address', '').strip()
            port_str = request.POST.get('port', '').strip()
            config_json = request.POST.get('config_json', '{}').strip()
            enabled = request.POST.get('enabled') == 'on'

            if not name:
                error = 'Name is required.'
            elif device_type not in DEVICE_TYPES:
                error = 'Please select a valid device type.'
            else:
                try:
                    port = int(port_str) if port_str else 0
                except ValueError:
                    port = 0
                update_device(conn, device_id,
                              name=name, location=location,
                              device_type=device_type,
                              ip_address=ip_address, port=port,
                              config_json=config_json or '{}',
                              enabled=enabled)
                conn.commit()
                return redirect('tc_device_detail', device_id=device_id)

            device = get_device(conn, device_id)

        sync_log = list_sync_log(conn, device_id=device_id, limit=20)
    finally:
        conn.close()

    return render(request, 'tc_device_form.html', _tc_context(
        request,
        form=device,
        error=error,
        device_types=DEVICE_TYPES,
        device_type_labels=DEVICE_TYPE_LABELS,
        is_new=False,
        device_id=device_id,
        sync_log=sync_log,
        back_url=_DEV_BACK,
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES, deny_redirect='time_clock_status')
def tc_device_poll(request, device_id: int):
    """Trigger an immediate poll of a device."""
    if request.method != 'POST':
        return redirect('tc_device_list')

    conn = get_db_connection()
    try:
        poll_device(conn, device_id)
        conn.commit()
    finally:
        conn.close()

    return redirect('tc_device_detail', device_id=device_id)


@dept_required('personnel', role_keys=_PERSONNEL_ROLES, deny_redirect='time_clock_status')
def tc_device_delete(request, device_id: int):
    """Delete a device and its sync log."""
    if request.method != 'POST':
        return redirect('tc_device_list')

    conn = get_db_connection()
    try:
        delete_device(conn, device_id)
        conn.commit()
    finally:
        conn.close()

    return redirect('tc_device_list')


# ---------------------------------------------------------------------------
# Time clock — Overtime Report
# ---------------------------------------------------------------------------

@login_required
def tc_ot_report(request):
    """Overtime report: 'mine' (default) or 'all' (managers/full-access only)."""

    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    mode = request.GET.get('mode', 'mine')

    # Only full-access / managers may see all-employee OT
    if mode == 'all' and not request.session.get('user_full_access'):
        mode = 'mine'

    my_ot = None
    all_ot = None

    conn = get_db_connection()
    try:
        if mode == 'mine':
            email = request.session.get('user_email', '')
            person = get_person_by_email(conn, email)
            if person:
                my_ot = get_ot_report(conn, person['id'],
                                      date_from=date_from or None,
                                      date_to=date_to or None)
                if not date_from:
                    date_from = my_ot['date_from']
                if not date_to:
                    date_to = my_ot['date_to']
            else:
                my_ot = {
                    'total_hours': 0.0, 'total_hours_fmt': '0:00',
                    'ot_hours': 0.0, 'ot_hours_fmt': '0:00',
                    'daily_ot': 0.0, 'weekly_ot': 0.0,
                    'by_day': [], 'entries': [],
                }
        else:
            all_ot = get_ot_report_all(conn,
                                       date_from=date_from or None,
                                       date_to=date_to or None)
            if not date_from or not date_to:
                from datetime import datetime
                today = datetime.now()
                date_from = date_from or today.replace(day=1).strftime('%Y-%m-%d')
                date_to = date_to or today.strftime('%Y-%m-%d')
    finally:
        conn.close()

    return render(request, 'tc_ot_report.html', {
        'user_email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'mode': mode,
        'date_from': date_from,
        'date_to': date_to,
        'my_ot': my_ot,
        'all_ot': all_ot or [],
    })


# ---------------------------------------------------------------------------
# Time clock — Schedule Summary
# ---------------------------------------------------------------------------

def tc_schedule(request):
    """Schedule / shift summary derived from clock-in records."""
    if not request.session.get('user_email'):
        return redirect('home')

    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    conn = get_db_connection()
    try:
        summary = get_schedule_summary(conn,
                                       date_from=date_from or None,
                                       date_to=date_to or None)
    finally:
        conn.close()

    return render(request, 'tc_schedule.html', {
        'user_email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'date_from': summary['date_from'],
        'date_to': summary['date_to'],
        'summary': summary,
    })


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

_AUDIT_ROLES = FULL_ACCESS_ROLES | {'Auditor'}


@role_required(_AUDIT_ROLES)
def audit_log(request):
    """Recent audit log entries, filterable by table and user."""

    table_filter = request.GET.get('table', '')
    user_filter = request.GET.get('user', '')
    entries = get_recent(
        limit=200,
        table_name=table_filter or None,
        changed_by=user_filter or None,
    )
    return render(request, 'audit_log.html', {
        'entries': entries,
        'audited_tables': sorted(AUDITED_TABLES),
        'table_filter': table_filter,
        'user_filter': user_filter,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


@role_required(_AUDIT_ROLES)
def audit_record(request, table_name: str, record_id: int):
    """Full history for a single record."""

    history = get_history(table_name, record_id)
    return render(request, 'audit_record.html', {
        'table_name': table_name,
        'record_id': record_id,
        'history': history,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


# ---------------------------------------------------------------------------
# Period locking management
# ---------------------------------------------------------------------------

@role_required(PERIOD_ADMIN_ROLES)
def periods(request):
    """List closed periods and show close/reopen controls."""

    error = None
    if request.method == 'POST':
        action = request.POST.get('action', '')
        conn = get_db_connection()
        try:
            if action == 'close':
                try:
                    year = int(request.POST.get('year', 0))
                    month = int(request.POST.get('month', 0))
                    notes = (request.POST.get('notes') or '').strip()
                    close_period(
                        conn, year, month,
                        closed_by=request.session.get('user_email', ''),
                        notes=notes,
                    )
                    conn.commit()
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
            elif action == 'reopen':
                try:
                    period_id = int(request.POST.get('period_id', 0))
                    reopen_period(
                        conn, period_id,
                        reopened_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                except (ValueError, TypeError) as exc:
                    conn.rollback()
                    error = str(exc)
        finally:
            conn.close()
        if not error:
            return redirect('periods')

    closed = list_periods(limit=36)
    closed_keys = {(p['period_year'], p['period_month']): p
                   for p in closed}
    months = recent_months(13)
    calendar = []
    for year, month in months:
        entry = closed_keys.get((year, month))
        calendar.append({
            'year': year,
            'month': month,
            'label': period_label(year, month),
            'closed': entry is not None,
            'period_id': entry['id'] if entry else None,
            'closed_by': entry['closed_by'] if entry else '',
            'closed_at': entry['closed_at'] if entry else None,
            'notes': entry['notes'] if entry else '',
        })

    return render(request, 'periods.html', {
        'calendar': calendar,
        'error': error,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_write': request.session.get('user_role', '') in PERIOD_ADMIN_ROLES,
    })


# ---------------------------------------------------------------------------
# PO approval workflow
# ---------------------------------------------------------------------------

@role_required(APPROVAL_ROLES)
def po_approvals(request):
    """Queue of POs waiting for approval (President / VP only)."""

    conn = get_db_connection()
    try:
        pending = get_pending_approvals(conn)
    finally:
        conn.close()

    return render(request, 'po_approvals.html', {
        'pending': pending,
        'threshold': APPROVAL_THRESHOLD,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


@role_required(APPROVAL_ROLES)
def po_approve(request, approval_id):
    """Approve a pending PO."""
    if request.method != 'POST':
        return redirect('po_approvals')

    notes = (request.POST.get('notes') or '').strip()
    decided_by = request.session.get('user_email', '')
    conn = get_db_connection()
    try:
        appr = get_approval_by_id(conn, approval_id)
        approve_po(conn, approval_id, decided_by=decided_by, notes=notes)
        conn.commit()
        if appr:
            notify_approval_decided(
                requester_email=appr['requested_by'],
                po_number=appr['po_number'],
                total=appr['total'],
                approved=True,
                notes=notes,
                decided_by=decided_by,
                site_url=request.build_absolute_uri('/'),
            )
    except ValueError:
        conn.rollback()
    finally:
        conn.close()
    return redirect('po_approvals')


@role_required(APPROVAL_ROLES)
def po_reject(request, approval_id):
    """Reject a pending PO, returning it to draft."""
    if request.method != 'POST':
        return redirect('po_approvals')

    notes = (request.POST.get('notes') or '').strip()
    decided_by = request.session.get('user_email', '')
    conn = get_db_connection()
    try:
        appr = get_approval_by_id(conn, approval_id)
        reject_po(conn, approval_id, decided_by=decided_by, notes=notes)
        conn.commit()
        if appr:
            notify_approval_decided(
                requester_email=appr['requested_by'],
                po_number=appr['po_number'],
                total=appr['total'],
                approved=False,
                notes=notes,
                decided_by=decided_by,
                site_url=request.build_absolute_uri('/'),
            )
    except ValueError:
        conn.rollback()
    finally:
        conn.close()
    return redirect('po_approvals')


# ---------------------------------------------------------------------------
# Bill of Materials (web)
# ---------------------------------------------------------------------------

_BOM_DEPT_KEYS = {'engineering', 'production'}


def _bom_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


@dept_required(_BOM_DEPT_KEYS)
def bom_list(request):

    item_type = request.GET.get('item_type') or None
    if item_type not in ITEM_TYPES:
        item_type = None

    conn = get_db_connection()
    try:
        products = list_products(conn, item_type=item_type)
    finally:
        conn.close()

    dept = request.session.get('user_dept_key', 'engineering')
    back_url = (
        f'/dept/{dept}/eng_menu/bom/'
        if dept in _BOM_DEPT_KEYS else '/dashboard/'
    )

    if 'export' in request.GET:
        return export_response(request, 'bom', [
            ('name', 'Product Name'), ('uom', 'Unit'), ('item_type', 'Type'),
            ('lead_time_days', 'Lead Time (Days)'), ('component_count', 'Component Count'),
        ], products)

    return render(request, 'bom_list.html', _bom_context(
        request,
        products=products,
        item_type=item_type,
        item_types=ITEM_TYPES,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url=back_url,
    ))


@dept_required(_BOM_DEPT_KEYS)
def bom_detail(request, product_id):

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        product = get_product(conn, product_id)
        if not product:
            return redirect('bom_list')

        error = None
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')

            if action == 'update_item_master':
                update_item_master(
                    conn, product_id,
                    item_type=request.POST.get('item_type', 'buy'),
                    lead_time_days=_int_or_none(
                        request.POST.get('lead_time_days')) or 0,
                    uom=(request.POST.get('uom') or 'ea').strip() or 'ea',
                )
                conn.commit()
                return redirect('bom_detail', product_id=product_id)

            elif action == 'add_line':
                component_id = _int_or_none(request.POST.get('component_id'))
                try:
                    qty = float(request.POST.get('qty_required') or 1.0)
                    qty = max(0.0, qty)
                except ValueError:
                    qty = 1.0
                try:
                    scrap_pct = float(request.POST.get('scrap_pct') or 0.0)
                    scrap_pct = max(0.0, scrap_pct)
                except ValueError:
                    scrap_pct = 0.0
                unit = (request.POST.get('unit') or 'ea').strip() or 'ea'
                notes = (request.POST.get('notes') or '').strip()
                if component_id is None:
                    error = 'Please select a component.'
                else:
                    ok, msg = add_bom_line(
                        conn, product_id, component_id,
                        qty_required=qty, unit=unit,
                        notes=notes, scrap_pct=scrap_pct,
                    )
                    if ok:
                        conn.commit()
                        return redirect('bom_detail', product_id=product_id)
                    error = msg

            elif action == 'update_line':
                line_id = _int_or_none(request.POST.get('line_id'))
                try:
                    qty = float(request.POST.get('qty_required') or 1.0)
                    qty = max(0.0, qty)
                except ValueError:
                    qty = 1.0
                try:
                    scrap_pct = float(request.POST.get('scrap_pct') or 0.0)
                    scrap_pct = max(0.0, scrap_pct)
                except ValueError:
                    scrap_pct = 0.0
                unit = (request.POST.get('unit') or 'ea').strip() or 'ea'
                notes = (request.POST.get('notes') or '').strip()
                if line_id is not None:
                    update_bom_line(conn, line_id, qty_required=qty,
                                    unit=unit, notes=notes, scrap_pct=scrap_pct)
                    conn.commit()
                return redirect('bom_detail', product_id=product_id)

            elif action == 'delete_line':
                line_id = _int_or_none(request.POST.get('line_id'))
                if line_id is not None:
                    delete_bom_line(conn, line_id)
                    conn.commit()
                return redirect('bom_detail', product_id=product_id)

        lines = get_bom(conn, product_id)
        all_products = list_products(conn)
        used_ids = {line['component_id'] for line in lines} | {product_id}
        available_components = [p for p in all_products if p['id'] not in used_ids]
    finally:
        conn.close()

    return render(request, 'bom_detail.html', _bom_context(
        request,
        product=product,
        lines=lines,
        available_components=available_components,
        item_types=ITEM_TYPES,
        can_edit=can_edit,
        error=error,
        back_url='/bom/',
    ))


@dept_required(_BOM_DEPT_KEYS)
def bom_explode(request, product_id):

    try:
        qty = float(request.GET.get('qty') or 1.0)
        qty = max(0.0, qty)
    except ValueError:
        qty = 1.0

    conn = get_db_connection()
    try:
        product = get_product(conn, product_id)
        if not product:
            return redirect('bom_list')
        explosion = explode_bom(conn, product_id, qty=qty)
    finally:
        conn.close()

    return render(request, 'bom_explode.html', _bom_context(
        request,
        product=product,
        explosion=explosion,
        qty=qty,
        back_url=f'/bom/{product_id}/',
    ))


# ---------------------------------------------------------------------------
# Material Requirements Planning (web)
# ---------------------------------------------------------------------------

_MRP_DEPT_KEYS = {'production', 'engineering'}


def _mrp_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_MRP_DEPT_KEYS)
def mrp_home(request):

    conn = get_db_connection()
    try:
        demand_rows = get_demand_details(conn)
        scheduled = get_scheduled_receipts_detail(conn)
    finally:
        conn.close()

    # Annotate each demand row with scheduled receipts and net requirement.
    for row in demand_rows:
        row['scheduled'] = scheduled.get(row['id'], 0.0)
        row['net'] = max(0.0,
            row['demand_qty'] + row['safety_stock']
            - row['on_hand'] - row['scheduled']
        )

    has_plan = 'mrp_plan' in request.session and bool(request.session['mrp_plan'])
    return render(request, 'mrp_home.html', _mrp_context(
        request,
        demand_rows=demand_rows,
        has_plan=has_plan,
    ))


@dept_required(_MRP_DEPT_KEYS, write_redirect='mrp_home')
def mrp_run(request):
    if request.method != 'POST':
        return redirect('mrp_home')

    include_forecast = request.POST.get('include_forecast') == 'on'
    conn = get_db_connection()
    try:
        plan = run_mrp_dated(conn, include_forecast=include_forecast)
    finally:
        conn.close()

    request.session['mrp_plan'] = plan
    return redirect('mrp_plan')


@dept_required(_MRP_DEPT_KEYS)
def mrp_plan(request):

    plan = request.session.get('mrp_plan') or []
    if not plan:
        return redirect('mrp_home')

    make_count = sum(1 for p in plan if p['order_type'] == 'make')
    buy_count = sum(1 for p in plan if p['order_type'] == 'buy')

    return render(request, 'mrp_plan.html', _mrp_context(
        request,
        plan=enumerate(plan),
        plan_list=plan,
        make_count=make_count,
        buy_count=buy_count,
    ))


@dept_required(_MRP_DEPT_KEYS, write_redirect='mrp_home')
def mrp_release(request):
    if request.method != 'POST':
        return redirect('mrp_plan')

    plan = request.session.get('mrp_plan') or []
    if not plan:
        return redirect('mrp_home')

    selected = request.POST.getlist('select')
    selected_indices = set()
    for v in selected:
        try:
            selected_indices.add(int(v))
        except ValueError:
            pass

    # Apply qty overrides from form
    items_to_release = []
    for i, item in enumerate(plan):
        if i not in selected_indices:
            continue
        override = request.POST.get(f'qty_{i}', '').strip()
        try:
            qty = float(override)
            if qty <= 0:
                qty = item['qty']
        except (ValueError, TypeError):
            qty = item['qty']
        items_to_release.append({**item, 'qty': qty})

    if not items_to_release:
        return redirect('mrp_plan')

    released_by = request.session.get('user_email', '')
    conn = get_db_connection()
    try:
        created_wos, created_pos = mrp_release_plan(conn, items_to_release, released_by)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Clear plan from session after release
    request.session.pop('mrp_plan', None)

    return render(request, 'mrp_release.html', _mrp_context(
        request,
        created_wos=created_wos,
        created_pos=created_pos,
        pos_missing_supplier=sum(1 for po in created_pos if not po.get('supplier_id')),
    ))


@dept_required(_MRP_DEPT_KEYS, write_redirect='mrp_safety_stock')
def mrp_safety_stock(request):
    """GET: show all products with their safety stock (reorder_point).
    POST: bulk-save the submitted values.
    """
    conn = get_db_connection()
    saved = False
    error = None

    try:
        if request.method == 'POST':
            rows = conn.execute(
                "SELECT id FROM product ORDER BY name"
            ).fetchall()
            for r in rows:
                pid = r['id']
                raw = request.POST.get(f'ss_{pid}', '').strip()
                try:
                    val = max(0.0, float(raw)) if raw else 0.0
                except ValueError:
                    continue
                conn.execute(
                    "UPDATE product SET reorder_point=%s WHERE id=%s",
                    (val, pid),
                )
            conn.commit()
            saved = True

        products = conn.execute(
            "SELECT id, name, "
            "COALESCE(item_type, 'buy') AS item_type, "
            "COALESCE(lead_time_days, 0) AS lead_time_days, "
            "COALESCE(amount, 0) AS on_hand, "
            "COALESCE(reorder_point, 0) AS safety_stock "
            "FROM product ORDER BY name"
        ).fetchall()
    except Exception as exc:
        conn.rollback()
        error = str(exc)
        products = []
    finally:
        conn.close()

    return render(request, 'mrp_safety_stock.html', _mrp_context(
        request,
        products=products,
        saved=saved,
        error=error,
    ))


# ---------------------------------------------------------------------------
# Inventory (web)
# ---------------------------------------------------------------------------

_INV_DEPT_KEYS = {'production', 'engineering', 'maintenance', 'purchasing'}


def _inv_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
        'trans_types': TRANS_TYPES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_INV_DEPT_KEYS)
def inventory_dashboard(request):
    conn = get_db_connection()
    try:
        alerts = get_alert_counts(conn)
        kpi = conn.execute("""
            SELECT
                COUNT(*)                                          AS total_products,
                COALESCE(SUM(amount * purchase_price), 0)        AS total_value,
                COUNT(*) FILTER (WHERE COALESCE(amount,0) <= 0)  AS zero_stock,
                COUNT(*) FILTER (
                    WHERE COALESCE(amount,0) > 0
                      AND reorder_point > 0
                      AND COALESCE(amount,0) <= reorder_point)   AS low_stock,
                COUNT(*) FILTER (
                    WHERE COALESCE(item_type,'buy') = 'make')     AS make_count,
                COUNT(*) FILTER (
                    WHERE COALESCE(item_type,'buy') = 'buy')      AS buy_count
            FROM product
        """).fetchone()
        top_value = conn.execute("""
            SELECT name, COALESCE(amount * purchase_price, 0) AS value
            FROM product
            WHERE COALESCE(amount, 0) > 0
            ORDER BY value DESC
            LIMIT 8
        """).fetchall()
        txn_trend = conn.execute("""
            SELECT trans_date AS day,
                COALESCE(SUM(quantity) FILTER (
                    WHERE trans_type = 'receive'), 0) AS received,
                COALESCE(SUM(quantity) FILTER (
                    WHERE trans_type = 'issue'), 0)   AS issued
            FROM inventory_transaction
            WHERE trans_date::date >= CURRENT_DATE - INTERVAL '14 days'
            GROUP BY trans_date
            ORDER BY trans_date
        """).fetchall()
        stock_status = conn.execute("""
            SELECT
                COUNT(*) FILTER (
                    WHERE COALESCE(amount,0) <= 0)                AS zero,
                COUNT(*) FILTER (
                    WHERE COALESCE(amount,0) > 0
                      AND reorder_point > 0
                      AND COALESCE(amount,0) <= reorder_point)    AS low,
                COUNT(*) FILTER (
                    WHERE COALESCE(amount,0) > 0
                      AND (reorder_point = 0
                           OR COALESCE(amount,0) > reorder_point)) AS ok
            FROM product
        """).fetchone()
        top_movers = conn.execute("""
            SELECT p.name AS product, COUNT(t.id) AS txn_count
            FROM inventory_transaction t
            JOIN product p ON p.id = t.product_id
            WHERE t.trans_date::date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY p.name
            ORDER BY txn_count DESC
            LIMIT 8
        """).fetchall()
        value_by_supplier = conn.execute("""
            SELECT COALESCE(s.company_name, 'No Supplier') AS supplier,
                   COALESCE(SUM(p.amount * p.purchase_price), 0) AS value
            FROM product p
            LEFT JOIN supplier s ON s.id = p.supplier_id
            WHERE COALESCE(p.amount, 0) > 0
            GROUP BY s.company_name
            ORDER BY value DESC
            LIMIT 8
        """).fetchall()
    finally:
        conn.close()

    ss = dict(stock_status) if stock_status else {}
    kpi_d = dict(kpi) if kpi else {}
    ctx = _inv_context(
        request,
        kpi=kpi_d,
        alerts=alerts,
        top_value_json=json.dumps([dict(r) for r in top_value]),
        txn_trend_json=json.dumps([dict(r) for r in txn_trend]),
        stock_status_json=json.dumps(ss),
        make_buy_json=json.dumps({
            'make': kpi_d.get('make_count', 0),
            'buy': kpi_d.get('buy_count', 0),
        }),
        top_movers_json=json.dumps([dict(r) for r in top_movers]),
        value_by_supplier_json=json.dumps([dict(r) for r in value_by_supplier]),
    )
    return render(request, 'inventory_dashboard.html', ctx)


@dept_required(_INV_DEPT_KEYS)
def inventory_list(request):

    search = request.GET.get('search', '').strip()
    filter_status = request.GET.get('filter') or None
    if filter_status not in ('low', 'zero'):
        filter_status = None
    item_type = request.GET.get('item_type') or None
    if item_type not in ('make', 'buy'):
        item_type = None

    conn = get_db_connection()
    try:
        products = inv_list_products(conn, search=search,
                                     filter_status=filter_status,
                                     item_type=item_type)
        alerts = get_alert_counts(conn)
    finally:
        conn.close()

    return render(request, 'inventory_list.html', _inv_context(
        request,
        products=products,
        search=search,
        filter_status=filter_status,
        item_type=item_type,
        alert_zero=alerts['zero_count'],
        alert_low=alerts['low_count'],
    ))


@dept_required(_INV_DEPT_KEYS)
def inventory_export(request):
    search = request.GET.get('search', '').strip()
    filter_status = request.GET.get('filter') or None
    if filter_status not in ('low', 'zero'):
        filter_status = None
    item_type = request.GET.get('item_type') or None
    if item_type not in ('make', 'buy'):
        item_type = None

    conn = get_db_connection()
    try:
        products = inv_list_products(conn, search=search,
                                     filter_status=filter_status,
                                     item_type=item_type)
    finally:
        conn.close()

    return export_response(request, 'inventory', [
        ('name', 'Product'), ('item_type', 'Type'), ('uom', 'UOM'),
        ('bin', 'Bin'), ('amount', 'On Hand'), ('reorder_point', 'Reorder Point'),
        ('purchase_price', 'Purchase Price'), ('lead_time_days', 'Lead Time (days)'),
        ('supplier_name', 'Supplier'),
    ], products)


@dept_required(_INV_DEPT_KEYS, write_redirect='inventory_list')
def inventory_new(request):

    conn = get_db_connection()
    error = None
    try:
        suppliers = inv_load_suppliers(conn)
        if request.method == 'POST':
            try:
                product_id = inv_create_product(
                    conn,
                    name=request.POST.get('name', ''),
                    supplier_id=_int_or_none(request.POST.get('supplier_id')),
                    bin_loc=request.POST.get('bin_loc', ''),
                    amount=float(request.POST.get('amount') or 0),
                    reorder_point=float(request.POST.get('reorder_point') or 0),
                    purchase_price=float(request.POST.get('purchase_price') or 0),
                    item_type=request.POST.get('item_type', 'buy'),
                    lead_time_days=int(request.POST.get('lead_time_days') or 0),
                    uom=request.POST.get('uom', 'ea'),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('inventory_detail', product_id=product_id)
            except (ValueError, Exception) as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    return render(request, 'inventory_new.html', _inv_context(
        request,
        suppliers=suppliers,
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


@dept_required(_INV_DEPT_KEYS)
def inventory_detail(request, product_id):

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    try:
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')

        suppliers = inv_load_suppliers(conn) if can_edit else []

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')

            if action == 'update':
                try:
                    inv_update_product(
                        conn, product_id,
                        name=request.POST.get('name', ''),
                        supplier_id=_int_or_none(request.POST.get('supplier_id')),
                        bin_loc=request.POST.get('bin_loc', ''),
                        reorder_point=float(request.POST.get('reorder_point') or 0),
                        purchase_price=float(request.POST.get('purchase_price') or 0),
                        item_type=request.POST.get('item_type', 'buy'),
                        lead_time_days=int(request.POST.get('lead_time_days') or 0),
                        uom=request.POST.get('uom', 'ea'),
                    )
                    conn.commit()
                    product = inv_get_product(conn, product_id) or product
                    success = 'Product updated.'
                except (ValueError, Exception) as e:
                    conn.rollback()
                    error = str(e)

        transactions = get_transactions(conn, product_id)
    finally:
        conn.close()

    amt = product['amount']
    rop = product['reorder_point']
    if amt <= 0:
        stock_status = 'zero'
    elif rop > 0 and amt <= rop:
        stock_status = 'low'
    else:
        stock_status = 'ok'

    return render(request, 'inventory_detail.html', _inv_context(
        request,
        product=product,
        suppliers=suppliers,
        transactions=transactions,
        stock_status=stock_status,
        error=error,
        success=success,
        can_edit=can_edit,
        back_url='/inventory/',
    ))


@dept_required(_INV_DEPT_KEYS, write_redirect='inventory_list')
def inventory_transaction(request, product_id):
    """POST only — record a stock movement for a product."""
    if request.method != 'POST':
        return redirect('inventory_detail', product_id=product_id)

    conn = get_db_connection()
    try:
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')

        trans_type = request.POST.get('trans_type', '')
        qty_raw = request.POST.get('quantity', '').strip()
        try:
            qty = float(qty_raw)
        except ValueError:
            qty = 0.0

        if trans_type in TRANS_TYPES and qty != 0:
            record_transaction(
                conn, product_id,
                trans_type=trans_type,
                quantity=qty,
                reference=request.POST.get('reference', '').strip(),
                notes=request.POST.get('notes', '').strip(),
                created_by=request.session.get('user_email', ''),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return redirect('inventory_detail', product_id=product_id)


# ---------------------------------------------------------------------------
# Customers (web)
# ---------------------------------------------------------------------------

_CUSTOMER_DEPT_KEYS = {'customers', 'customer_service', 'sales'}
_SUPPLIER_DEPT_KEYS = {'customers', 'purchasing', 'sales'}


def _contacts_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_CUSTOMER_DEPT_KEYS)
def customer_list(request):
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        customers = list_customers(conn, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'customers', [
            ('company_name', 'Company'), ('first_name', 'First Name'), ('last_name', 'Last Name'),
            ('email', 'Email'), ('phone_number', 'Phone'), ('city', 'City'), ('state', 'State'),
        ], customers)

    return render(request, 'contacts_list.html', _contacts_context(
        request,
        contacts=customers,
        search=search,
        contact_type='customer',
        contact_type_plural='customers',
        list_url='/customers/',
        new_url='/customers/new/',
        detail_base='/customers/',
    ))


@dept_required(_CUSTOMER_DEPT_KEYS, write_redirect='customer_list')
def customer_new(request):
    error = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            try:
                cid = create_customer(
                    conn,
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    company_name=request.POST.get('company_name', ''),
                    phone_number=request.POST.get('phone_number', ''),
                    address=request.POST.get('address', ''),
                    city=request.POST.get('city', ''),
                    state=request.POST.get('state', ''),
                    zip_code=request.POST.get('zip_code', ''),
                    email=request.POST.get('email', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('customer_detail', customer_id=cid)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'contacts_new.html', _contacts_context(
        request,
        contact_type='customer',
        contact_type_plural='customers',
        list_url='/customers/',
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


@dept_required(_CUSTOMER_DEPT_KEYS)
def customer_detail(request, customer_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    try:
        ensure_price_list_tables(conn)
        contact = get_customer(conn, customer_id)
        if not contact:
            return redirect('customer_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'assign_price_list':
                    pl_id = request.POST.get('price_list_id') or None
                    assign_customer_price_list(
                        conn, customer_id, int(pl_id) if pl_id else None)
                    conn.commit()
                    contact = get_customer(conn, customer_id)
                    success = 'Price list assigned.'
                else:
                    update_customer(
                        conn, customer_id,
                        first_name=request.POST.get('first_name', ''),
                        last_name=request.POST.get('last_name', ''),
                        company_name=request.POST.get('company_name', ''),
                        phone_number=request.POST.get('phone_number', ''),
                        address=request.POST.get('address', ''),
                        city=request.POST.get('city', ''),
                        state=request.POST.get('state', ''),
                        zip_code=request.POST.get('zip_code', ''),
                        email=request.POST.get('email', ''),
                    )
                    conn.commit()
                    contact = get_customer(conn, customer_id)
                    success = 'Customer updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        orders = get_customer_orders(conn, customer_id)
        price_lists = list_price_lists(conn, active_only=True)
    finally:
        conn.close()
    return render(request, 'contacts_detail.html', _contacts_context(
        request,
        contact=contact,
        orders=orders,
        contact_type='customer',
        contact_type_plural='customers',
        list_url='/customers/',
        new_url='/customers/new/',
        order_label='Sales Order',
        order_url_prefix='/so/',
        price_lists=price_lists,
        error=error,
        success=success,
        can_edit=can_edit,
    ))


# ---------------------------------------------------------------------------
# Suppliers (web)
# ---------------------------------------------------------------------------

@dept_required(_SUPPLIER_DEPT_KEYS)
def supplier_list(request):
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        suppliers = contacts_list_suppliers(conn, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'suppliers', [
            ('company_name', 'Company'), ('first_name', 'First Name'), ('last_name', 'Last Name'),
            ('email', 'Email'), ('phone_number', 'Phone'), ('city', 'City'), ('state', 'State'),
        ], suppliers)

    return render(request, 'contacts_list.html', _contacts_context(
        request,
        contacts=suppliers,
        search=search,
        contact_type='supplier',
        contact_type_plural='suppliers',
        list_url='/suppliers/',
        new_url='/suppliers/new/',
        detail_base='/suppliers/',
    ))


@dept_required(_SUPPLIER_DEPT_KEYS, write_redirect='supplier_list')
def supplier_new(request):
    error = None
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            try:
                sid = create_supplier(
                    conn,
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    company_name=request.POST.get('company_name', ''),
                    phone_number=request.POST.get('phone_number', ''),
                    address=request.POST.get('address', ''),
                    city=request.POST.get('city', ''),
                    state=request.POST.get('state', ''),
                    zip_code=request.POST.get('zip_code', ''),
                    email=request.POST.get('email', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('supplier_detail', supplier_id=sid)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'contacts_new.html', _contacts_context(
        request,
        contact_type='supplier',
        contact_type_plural='suppliers',
        list_url='/suppliers/',
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


@dept_required(_SUPPLIER_DEPT_KEYS)
def supplier_detail(request, supplier_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    try:
        contact = get_supplier(conn, supplier_id)
        if not contact:
            return redirect('supplier_list')
        if request.method == 'POST' and can_edit:
            try:
                update_supplier(
                    conn, supplier_id,
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    company_name=request.POST.get('company_name', ''),
                    phone_number=request.POST.get('phone_number', ''),
                    address=request.POST.get('address', ''),
                    city=request.POST.get('city', ''),
                    state=request.POST.get('state', ''),
                    zip_code=request.POST.get('zip_code', ''),
                    email=request.POST.get('email', ''),
                )
                conn.commit()
                contact = get_supplier(conn, supplier_id)
                success = 'Supplier updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        orders = get_supplier_orders(conn, supplier_id)
    finally:
        conn.close()
    return render(request, 'contacts_detail.html', _contacts_context(
        request,
        contact=contact,
        orders=orders,
        contact_type='supplier',
        contact_type_plural='suppliers',
        list_url='/suppliers/',
        new_url='/suppliers/new/',
        order_label='Purchase Order',
        order_url_prefix='/po/',
        error=error,
        success=success,
        can_edit=can_edit,
    ))


# ---------------------------------------------------------------------------
# Customer Service tickets (web)
# ---------------------------------------------------------------------------

_CS_DEPT_KEYS = {'customer_service', 'sales', 'customers'}


def _cs_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_CS_DEPT_KEYS)
def cs_ticket_list(request):
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    my_only = request.GET.get('my', '') == '1'
    created_by = request.session.get('user_email', '') if my_only else None
    conn = get_db_connection()
    try:
        tickets = list_tickets(
            conn,
            search=search or None,
            status=status_filter or None,
            created_by=created_by,
        )
        open_count = sum(1 for t in tickets if t['status'] == 'open')
        overdue_count = sum(1 for t in tickets
                           if t['priority'] in ('high', 'critical'))
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'cs_tickets', [
            ('id', 'ID'), ('customer_name', 'Customer'), ('call_date', 'Date'),
            ('priority', 'Priority'), ('status', 'Status'), ('created_by', 'Created By'),
        ], tickets)

    return render(request, 'cs_list.html', _cs_context(
        request,
        tickets=tickets,
        open_count=open_count,
        overdue_count=overdue_count,
        search=search,
        status_filter=status_filter,
        my_only=my_only,
    ))


@dept_required(_CS_DEPT_KEYS, write_redirect='cs_ticket_list')
def cs_ticket_new(request):
    conn = get_db_connection()
    error = None
    customers = []
    try:
        customers = load_customers_for_cs(conn)
        if request.method == 'POST':
            cid_raw = request.POST.get('customer_id', '')
            try:
                customer_id = int(cid_raw)
            except (TypeError, ValueError):
                customer_id = None
            call_text = request.POST.get('call', '')
            errors = validate_call(customer_id, call_text)
            if errors:
                error = '; '.join(errors)
            else:
                assert customer_id is not None
                import datetime as _dt
                today = _dt.date.today().isoformat()
                now_time = _dt.datetime.now().strftime('%H:%M')
                tid = create_ticket(
                    conn,
                    customer_id=customer_id,
                    call=call_text,
                    call_date=request.POST.get('call_date', '') or today,
                    call_time=request.POST.get('call_time', '') or now_time,
                    comments=request.POST.get('comments', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('cs_ticket_detail', ticket_id=tid)
    except Exception as e:
        conn.rollback()
        error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_new.html', _cs_context(
        request,
        customers=customers,
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_ticket_detail(request, ticket_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    ticket = None
    customers = []
    try:
        ticket = get_ticket(conn, ticket_id)
        if not ticket:
            return redirect('cs_ticket_list')
        customers = load_customers_for_cs(conn) if can_edit else []

        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action == 'close':
                    close_ticket(conn, ticket_id,
                                 comments=request.POST.get('comments', ''))
                    conn.commit()
                    success = 'Ticket closed.'
                elif action == 'update':
                    try:
                        cid = int(request.POST.get('customer_id', 0))
                    except ValueError:
                        cid = ticket['customer_id']
                    update_ticket(
                        conn, ticket_id,
                        customer_id=cid,
                        call=request.POST.get('call', ''),
                        call_date=request.POST.get('call_date', ''),
                        call_time=request.POST.get('call_time', ''),
                        completion_date=request.POST.get('completion_date', ''),
                        completion_time=request.POST.get('completion_time', ''),
                        comments=request.POST.get('comments', ''),
                        completed=request.POST.get('completed') == '1',
                    )
                    conn.commit()
                    success = 'Ticket updated.'
                ticket = get_ticket(conn, ticket_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_detail.html', _cs_context(
        request,
        ticket=ticket,
        customers=customers,
        error=error,
        success=success,
        can_edit=can_edit,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_escalations(request):
    conn = get_db_connection()
    try:
        tickets = get_escalations(conn)
        critical_count = sum(1 for t in tickets if t['priority'] == 'critical')
        high_count = sum(1 for t in tickets if t['priority'] == 'high')
    finally:
        conn.close()
    return render(request, 'cs_escalations.html', _cs_context(
        request,
        tickets=tickets,
        critical_count=critical_count,
        high_count=high_count,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_reports(request):
    try:
        days = int(request.GET.get('days', 365))
    except ValueError:
        days = 365
    conn = get_db_connection()
    try:
        stats = get_summary_stats(conn, days)
        monthly = get_monthly_volume(conn, days)
        open_tickets = list_tickets(conn, status='open')
        overdue_count = sum(1 for t in open_tickets
                           if t['priority'] in ('high', 'critical'))
    finally:
        conn.close()
    return render(request, 'cs_reports.html', _cs_context(
        request,
        stats=stats,
        monthly=monthly,
        open_count=len(open_tickets),
        overdue_count=overdue_count,
        days=days,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_plans(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_filter = request.GET.get('status', '').strip()
    conn = get_db_connection()
    error = None
    success = None
    plans = []
    try:
        plans = cs_list_plans(conn, status=status_filter or None)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action == 'create':
                    cs_create_plan(
                        conn,
                        title=request.POST.get('title', ''),
                        description=request.POST.get('description', ''),
                        owner=request.POST.get('owner', ''),
                        target_date=request.POST.get('target_date', ''),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Plan created.'
                elif action == 'update':
                    pid = int(request.POST.get('plan_id', 0))
                    cs_update_plan(
                        conn, pid,
                        title=request.POST.get('title', ''),
                        description=request.POST.get('description', ''),
                        owner=request.POST.get('owner', ''),
                        target_date=request.POST.get('target_date', ''),
                        status=request.POST.get('status', 'Open'),
                    )
                    conn.commit()
                    success = 'Plan updated.'
                plans = cs_list_plans(conn, status=status_filter or None)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_plans.html', _cs_context(
        request,
        plans=plans,
        plan_statuses=PLAN_STATUSES,
        status_filter=status_filter,
        error=error,
        success=success,
        can_edit=can_edit,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_returns_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_return_table(conn)
        returns = list_returns(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and can_edit:
            try:
                cid = request.POST.get('customer_id') or None
                create_return(
                    conn,
                    customer_id=int(cid) if cid else None,
                    return_date=request.POST.get('return_date', ''),
                    reason=request.POST.get('reason', ''),
                    items_returned=request.POST.get('items_returned', ''),
                    refund_amount=float(request.POST.get('refund_amount') or 0),
                    status=request.POST.get('status', 'Pending'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('cs_returns_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                returns = list_returns(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'cs_returns_list.html', _cs_context(
        request, returns=returns, status_filter=status_f, search=search,
        return_statuses=RETURN_STATUSES, return_reasons=RETURN_REASONS,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_returns_detail(request, return_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        ret = get_return(conn, return_id)
        if not ret:
            return redirect('cs_returns_list')
        customers = load_customers_for_cs(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            try:
                cid = request.POST.get('customer_id') or None
                update_return(
                    conn, return_id,
                    customer_id=int(cid) if cid else None,
                    return_date=request.POST.get('return_date', ''),
                    reason=request.POST.get('reason', ''),
                    items_returned=request.POST.get('items_returned', ''),
                    refund_amount=float(request.POST.get('refund_amount') or 0),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Return updated.'
                ret = get_return(conn, return_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_returns_detail.html', _cs_context(
        request, ret=ret, customers=customers, can_edit=can_edit,
        return_statuses=RETURN_STATUSES, return_reasons=RETURN_REASONS,
        error=error, success=success,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_kb_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    cat_f = request.GET.get('category', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_kb_table(conn)
        articles = list_kb_articles(
            conn, status=status_f or None,
            category=cat_f or None, search=search or None,
        )
        if request.method == 'POST' and can_edit:
            try:
                create_kb_article(
                    conn,
                    title=request.POST.get('title', ''),
                    category=request.POST.get('category', ''),
                    content=request.POST.get('content', ''),
                    author=request.POST.get('author', ''),
                    published_date=request.POST.get('published_date', ''),
                    status=request.POST.get('status', 'Draft'),
                    tags=request.POST.get('tags', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('cs_kb_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                articles = list_kb_articles(
                    conn, status=status_f or None,
                    category=cat_f or None, search=search or None,
                )
    finally:
        conn.close()
    return render(request, 'cs_kb_list.html', _cs_context(
        request, articles=articles, status_filter=status_f,
        category_filter=cat_f, search=search,
        kb_statuses=KB_STATUSES, kb_categories=KB_CATEGORIES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_kb_detail(request, article_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        article = get_kb_article(conn, article_id)
        if not article:
            return redirect('cs_kb_list')
        if request.method == 'POST' and can_edit:
            try:
                update_kb_article(
                    conn, article_id,
                    title=request.POST.get('title', ''),
                    category=request.POST.get('category', ''),
                    content=request.POST.get('content', ''),
                    author=request.POST.get('author', ''),
                    published_date=request.POST.get('published_date', ''),
                    status=request.POST.get('status', ''),
                    tags=request.POST.get('tags', ''),
                )
                conn.commit()
                success = 'Article updated.'
                article = get_kb_article(conn, article_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_kb_detail.html', _cs_context(
        request, article=article, can_edit=can_edit,
        kb_statuses=KB_STATUSES, kb_categories=KB_CATEGORIES,
        error=error, success=success,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_surveys_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('survey_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_survey_tables(conn)
        surveys = list_surveys(
            conn, status=status_f or None,
            survey_type=type_f or None, search=search or None,
        )
        if request.method == 'POST' and can_edit:
            try:
                create_survey(
                    conn,
                    title=request.POST.get('title', ''),
                    description=request.POST.get('description', ''),
                    survey_type=request.POST.get('survey_type', 'CSAT'),
                    status=request.POST.get('status', 'Draft'),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('cs_surveys_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                surveys = list_surveys(
                    conn, status=status_f or None,
                    survey_type=type_f or None, search=search or None,
                )
    finally:
        conn.close()
    return render(request, 'cs_surveys_list.html', _cs_context(
        request, surveys=surveys, status_filter=status_f, type_filter=type_f,
        search=search, survey_types=SURVEY_TYPES, survey_statuses=SURVEY_STATUSES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_CS_DEPT_KEYS)
def cs_surveys_detail(request, survey_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        survey = get_survey(conn, survey_id)
        if not survey:
            return redirect('cs_surveys_list')
        responses = get_survey_responses(conn, survey_id)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'respond':
                    cid = request.POST.get('customer_id') or None
                    add_survey_response(
                        conn, survey_id,
                        customer_id=int(cid) if cid else None,
                        score=int(request.POST.get('score') or 0),
                        comments=request.POST.get('comments', ''),
                        response_date=request.POST.get('response_date', ''),
                    )
                else:
                    update_survey(
                        conn, survey_id,
                        title=request.POST.get('title', ''),
                        description=request.POST.get('description', ''),
                        survey_type=request.POST.get('survey_type', ''),
                        status=request.POST.get('status', ''),
                        start_date=request.POST.get('start_date', ''),
                        end_date=request.POST.get('end_date', ''),
                    )
                    success = 'Survey updated.'
                conn.commit()
                survey = get_survey(conn, survey_id)
                responses = get_survey_responses(conn, survey_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'cs_surveys_detail.html', _cs_context(
        request, survey=survey, responses=responses, can_edit=can_edit,
        survey_types=SURVEY_TYPES, survey_statuses=SURVEY_STATUSES,
        error=error, success=success,
    ))


from ..accounting_core import (  # noqa: E402
    INVOICE_STATUSES, PAYMENT_METHODS, ACCOUNT_TYPES, load_vendors, load_customers,  # noqa: F811
    get_ap_dashboard, list_ap_invoices, get_ap_invoice,
    create_ap_invoice, update_ap_invoice, set_ap_status,
    list_ap_payments, record_ap_payment,
    get_ar_dashboard, list_ar_invoices, get_ar_invoice,
    create_ar_invoice, update_ar_invoice, set_ar_status,
    list_ar_payments, record_ar_payment,
    list_accounts, create_account, update_account, account_balance,
    list_journals, get_journal, get_journal_lines,
    create_journal, post_journal, void_journal,
    trial_balance, income_statement, balance_sheet, get_ar_aging,
)

_ACCOUNTING_DEPT_KEYS = {'accounting', 'finance'}


def _acct_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


# ── Accounts Payable ────────────────────────────────────────────────────────

@dept_required(_ACCOUNTING_DEPT_KEYS)
def ap_list(request):
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        if request.session.get('user_role') in READ_ONLY_ROLES:
            conn.close()
            return redirect('acct_dashboard')
        action = request.POST.get('action', '')
        try:
            if action == 'new':
                create_ap_invoice(
                    conn,
                    request.POST.get('vendor_id') or None,
                    request.POST.get('invoice_number', '').strip(),
                    request.POST.get('invoice_date', ''),
                    request.POST.get('due_date', ''),
                    request.POST.get('amount', 0),
                    request.POST.get('description', '').strip(),
                    request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Invoice created.'
        except Exception as exc:
            error = str(exc)
    status  = request.GET.get('status', '')
    vendor_id = request.GET.get('vendor_id', '')
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')
    invoices = list_ap_invoices(
        conn,
        status=status or None,
        vendor_id=int(vendor_id) if vendor_id else None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    dashboard = get_ap_dashboard(conn)
    vendors   = load_vendors(conn)
    conn.close()
    ctx = _acct_ctx(request,
        invoices=invoices, dashboard=dashboard, vendors=vendors,
        statuses=INVOICE_STATUSES, payment_methods=PAYMENT_METHODS,
        status=status, vendor_id=vendor_id,
        date_from=date_from, date_to=date_to,
        success=success, error=error,
    )
    return render(request, 'ap_list.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def ap_export(request):
    status = request.GET.get('status', '')
    vendor_id = request.GET.get('vendor_id', '')
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')
    conn = get_db_connection()
    try:
        invoices = list_ap_invoices(
            conn,
            status=status or None,
            vendor_id=int(vendor_id) if vendor_id else None,
            date_from=date_from or None,
            date_to=date_to or None,
        )
    finally:
        conn.close()

    return export_response(request, 'ap_invoices', [
        ('invoice_number', 'Invoice #'), ('vendor_label', 'Vendor'),
        ('invoice_date', 'Invoice Date'), ('due_date', 'Due Date'),
        ('amount', 'Amount'), ('paid', 'Paid'), ('balance', 'Balance'),
        ('status', 'Status'),
    ], invoices)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def ap_invoice_detail(request, inv_id=None):
    conn = get_db_connection()
    success = error = ''
    init_currency_schema(conn)
    if request.method == 'POST':
        if request.session.get('user_role') in READ_ONLY_ROLES:
            conn.close()
            return redirect('acct_dashboard')
        action = request.POST.get('action', '')
        try:
            if action == 'save' and inv_id:
                update_ap_invoice(
                    conn, inv_id,
                    request.POST.get('vendor_id') or None,
                    request.POST.get('invoice_number', '').strip(),
                    request.POST.get('invoice_date', ''),
                    request.POST.get('due_date', ''),
                    request.POST.get('amount', 0),
                    request.POST.get('description', '').strip(),
                    request.POST.get('status', 'open'),
                )
                conn.execute(
                    "UPDATE ap_invoice SET currency=%s, exchange_rate=%s WHERE id=%s",
                    [request.POST.get('currency', 'USD'),
                     float(request.POST.get('exchange_rate') or 1.0), inv_id]
                )
                conn.commit()
                success = 'Invoice updated.'
            elif action == 'payment' and inv_id:
                record_ap_payment(
                    conn, inv_id,
                    request.POST.get('payment_date', ''),
                    request.POST.get('amount', 0),
                    request.POST.get('method', 'Check'),
                    request.POST.get('reference', '').strip(),
                    request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Payment recorded.'
            elif action == 'status' and inv_id:
                set_ap_status(conn, inv_id, request.POST.get('new_status', 'open'))
                conn.commit()
                success = 'Status updated.'
        except Exception as exc:
            error = str(exc)
    invoice  = get_ap_invoice(conn, inv_id) if inv_id else None
    payments = list_ap_payments(conn, inv_id) if inv_id else []
    vendors  = load_vendors(conn)
    currencies = list_currencies(conn, active_only=True)
    base_currency = get_base_currency(conn).get("code", "USD")
    conn.close()
    if inv_id and not invoice:
        return redirect('/ap/')
    if invoice and invoice.get('exchange_rate') and invoice.get('amount'):
        invoice['amount_base'] = round(float(invoice['amount']) * float(invoice['exchange_rate']), 2)
    ctx = _acct_ctx(request,
        invoice=invoice, payments=payments, vendors=vendors,
        currencies=currencies, base_currency=base_currency,
        statuses=INVOICE_STATUSES, payment_methods=PAYMENT_METHODS,
        inv_id=inv_id, success=success, error=error,
    )
    return render(request, 'ap_invoice_detail.html', ctx)


# ── Accounts Receivable ─────────────────────────────────────────────────────

@dept_required(_ACCOUNTING_DEPT_KEYS)
def ar_list(request):
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        if request.session.get('user_role') in READ_ONLY_ROLES:
            conn.close()
            return redirect('acct_dashboard')
        action = request.POST.get('action', '')
        try:
            if action == 'new':
                create_ar_invoice(
                    conn,
                    request.POST.get('customer_id') or None,
                    request.POST.get('invoice_number', '').strip(),
                    request.POST.get('invoice_date', ''),
                    request.POST.get('due_date', ''),
                    request.POST.get('amount', 0),
                    request.POST.get('description', '').strip(),
                    request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Invoice created.'
        except Exception as exc:
            error = str(exc)
    status      = request.GET.get('status', '')
    customer_id = request.GET.get('customer_id', '')
    date_from   = request.GET.get('date_from', '')
    date_to     = request.GET.get('date_to', '')
    invoices  = list_ar_invoices(
        conn,
        status=status or None,
        customer_id=int(customer_id) if customer_id else None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    dashboard = get_ar_dashboard(conn)
    customers = load_customers(conn)
    conn.close()
    ctx = _acct_ctx(request,
        invoices=invoices, dashboard=dashboard, customers=customers,
        statuses=INVOICE_STATUSES, payment_methods=PAYMENT_METHODS,
        status=status, customer_id=customer_id,
        date_from=date_from, date_to=date_to,
        success=success, error=error,
    )
    return render(request, 'ar_list.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def ar_export(request):
    status = request.GET.get('status', '')
    customer_id = request.GET.get('customer_id', '')
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')
    conn = get_db_connection()
    try:
        invoices = list_ar_invoices(
            conn,
            status=status or None,
            customer_id=int(customer_id) if customer_id else None,
            date_from=date_from or None,
            date_to=date_to or None,
        )
    finally:
        conn.close()

    return export_response(request, 'ar_invoices', [
        ('invoice_number', 'Invoice #'), ('customer_label', 'Customer'),
        ('invoice_date', 'Invoice Date'), ('due_date', 'Due Date'),
        ('amount', 'Amount'), ('received', 'Received'), ('balance', 'Balance'),
        ('status', 'Status'),
    ], invoices)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def ar_invoice_detail(request, inv_id=None):
    conn = get_db_connection()
    success = error = ''
    init_currency_schema(conn)
    if request.method == 'POST':
        if request.session.get('user_role') in READ_ONLY_ROLES:
            conn.close()
            return redirect('acct_dashboard')
        action = request.POST.get('action', '')
        try:
            if action == 'save' and inv_id:
                update_ar_invoice(
                    conn, inv_id,
                    request.POST.get('customer_id') or None,
                    request.POST.get('invoice_number', '').strip(),
                    request.POST.get('invoice_date', ''),
                    request.POST.get('due_date', ''),
                    request.POST.get('amount', 0),
                    request.POST.get('description', '').strip(),
                    request.POST.get('status', 'open'),
                )
                conn.execute(
                    "UPDATE ar_invoice SET currency=%s, exchange_rate=%s WHERE id=%s",
                    [request.POST.get('currency', 'USD'),
                     float(request.POST.get('exchange_rate') or 1.0), inv_id]
                )
                conn.commit()
                success = 'Invoice updated.'
            elif action == 'payment' and inv_id:
                record_ar_payment(
                    conn, inv_id,
                    request.POST.get('payment_date', ''),
                    request.POST.get('amount', 0),
                    request.POST.get('method', 'Check'),
                    request.POST.get('reference', '').strip(),
                    request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Payment recorded.'
            elif action == 'status' and inv_id:
                set_ar_status(conn, inv_id, request.POST.get('new_status', 'open'))
                conn.commit()
                success = 'Status updated.'
        except Exception as exc:
            error = str(exc)
    invoice   = get_ar_invoice(conn, inv_id) if inv_id else None
    payments  = list_ar_payments(conn, inv_id) if inv_id else []
    customers = load_customers(conn)
    currencies = list_currencies(conn, active_only=True)
    base_currency = get_base_currency(conn).get("code", "USD")
    conn.close()
    if inv_id and not invoice:
        return redirect('/ar/')
    if invoice and invoice.get('exchange_rate') and invoice.get('amount'):
        invoice['amount_base'] = round(float(invoice['amount']) * float(invoice['exchange_rate']), 2)
    ctx = _acct_ctx(request,
        invoice=invoice, payments=payments, customers=customers,
        currencies=currencies, base_currency=base_currency,
        statuses=INVOICE_STATUSES, payment_methods=PAYMENT_METHODS,
        inv_id=inv_id, success=success, error=error,
    )
    return render(request, 'ar_invoice_detail.html', ctx)


# ── General Ledger ───────────────────────────────────────────────────────────

@dept_required(_ACCOUNTING_DEPT_KEYS)
def gl_dashboard(request):
    conn = get_db_connection()
    ap_dash = get_ap_dashboard(conn)
    ar_dash = get_ar_dashboard(conn)
    acct_count = len(list_accounts(conn, active_only=True))
    recent_journals = list_journals(conn)[:8]
    conn.close()
    ctx = _acct_ctx(request,
        ap=ap_dash, ar=ar_dash,
        acct_count=acct_count,
        recent_journals=recent_journals,
    )
    return render(request, 'gl_dashboard.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def gl_accounts(request):
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        if request.session.get('user_role') in READ_ONLY_ROLES:
            conn.close()
            return redirect('acct_dashboard')
        action = request.POST.get('action', '')
        try:
            if action == 'create':
                create_account(
                    conn,
                    request.POST.get('account_number', '').strip(),
                    request.POST.get('account_name', '').strip(),
                    request.POST.get('account_type', 'Expense'),
                    request.POST.get('account_sub', '').strip(),
                    request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Account created.'
            elif action == 'update':
                update_account(
                    conn,
                    int(request.POST.get('acct_id')),
                    request.POST.get('account_number', '').strip(),
                    request.POST.get('account_name', '').strip(),
                    request.POST.get('account_type', 'Expense'),
                    request.POST.get('account_sub', '').strip(),
                    bool(request.POST.get('is_active')),
                    request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Account updated.'
        except Exception as exc:
            error = str(exc)
    acct_type  = request.GET.get('type', '')
    active_only = request.GET.get('active', '1') != '0'
    accounts = list_accounts(conn, acct_type=acct_type or None, active_only=active_only)
    accts_with_bal = []
    for a in accounts:
        d = dict(a)
        d['balance'] = account_balance(conn, a['id'], a['account_type'])
        accts_with_bal.append(d)
    conn.close()
    ctx = _acct_ctx(request,
        accounts=accts_with_bal, account_types=ACCOUNT_TYPES,
        acct_type=acct_type, active_only=active_only,
        success=success, error=error,
    )
    return render(request, 'gl_accounts.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def gl_journals(request):
    conn = get_db_connection()
    posted_param = request.GET.get('posted', '')
    date_from    = request.GET.get('date_from', '')
    date_to      = request.GET.get('date_to', '')
    posted = None
    if posted_param == '1':
        posted = True
    elif posted_param == '0':
        posted = False
    journals = list_journals(conn,
        posted=posted,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    conn.close()
    ctx = _acct_ctx(request,
        journals=journals,
        posted_param=posted_param,
        date_from=date_from, date_to=date_to,
    )
    return render(request, 'gl_journals.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def gl_journal_detail(request, journal_id=None):
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        action = request.POST.get('action', '')
        try:
            if action == 'create':
                if request.session.get('user_role') in READ_ONLY_ROLES:
                    conn.close()
                    return redirect('acct_dashboard')
                # Parse lines from POST: account_id[], debit[], credit[], memo[]
                acct_ids = request.POST.getlist('account_id')
                debits   = request.POST.getlist('debit')
                credits  = request.POST.getlist('credit')
                memos    = request.POST.getlist('memo')
                lines = [
                    (int(acct_ids[i]), float(debits[i] or 0),
                     float(credits[i] or 0), memos[i] if i < len(memos) else '')
                    for i in range(len(acct_ids))
                    if acct_ids[i]
                ]
                new_id = create_journal(
                    conn,
                    request.POST.get('journal_date', ''),
                    request.POST.get('reference', '').strip(),
                    request.POST.get('description', '').strip(),
                    lines,
                    request.session.get('user_email', ''),
                )
                conn.commit()
                conn.close()
                return redirect(f'/gl/journals/{new_id}/')
            elif action == 'post' and journal_id:
                if request.session.get('user_role') in READ_ONLY_ROLES:
                    conn.close()
                    return redirect('acct_dashboard')
                post_journal(conn, journal_id)
                conn.commit()
                success = 'Journal entry posted.'
            elif action == 'void' and journal_id:
                if request.session.get('user_role') in READ_ONLY_ROLES:
                    conn.close()
                    return redirect('acct_dashboard')
                void_journal(conn, journal_id)
                conn.commit()
                conn.close()
                return redirect('/gl/journals/')
        except Exception as exc:
            error = str(exc)
    journal  = get_journal(conn, journal_id) if journal_id else None
    lines    = get_journal_lines(conn, journal_id) if journal_id else []
    accounts = list_accounts(conn, active_only=True)
    conn.close()
    if journal_id and not journal:
        return redirect('/gl/journals/')
    ctx = _acct_ctx(request,
        journal=journal, lines=lines, accounts=accounts,
        journal_id=journal_id, success=success, error=error,
    )
    return render(request, 'gl_journal_detail.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def gl_trial_balance(request):
    conn = get_db_connection()
    as_of = request.GET.get('as_of', '')
    result = trial_balance(conn, as_of=as_of or None)
    conn.close()
    ctx = _acct_ctx(request, as_of=as_of, **result)
    return render(request, 'gl_trial_balance.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def gl_income_statement(request):
    import datetime as _dt
    today = _dt.date.today()
    date_from = request.GET.get('date_from', f'{today.year}-01-01')
    date_to   = request.GET.get('date_to', today.isoformat())
    conn = get_db_connection()
    result = income_statement(conn, date_from, date_to)
    conn.close()
    ctx = _acct_ctx(request, date_from=date_from, date_to=date_to, **result)
    return render(request, 'gl_income_statement.html', ctx)


@dept_required(_ACCOUNTING_DEPT_KEYS)
def gl_balance_sheet(request):
    as_of = request.GET.get('as_of', '')
    conn = get_db_connection()
    result = balance_sheet(conn, as_of=as_of or None)
    conn.close()
    ctx = _acct_ctx(request, as_of=as_of, **result)
    return render(request, 'gl_balance_sheet.html', ctx)


from ..engineering_core import (  # noqa: E402
    PROJECT_STATUSES, TASK_STATUSES, ECR_STATUSES, PRIORITIES,  # noqa: F811
    load_products, load_people,  # noqa: F811
    get_eng_dashboard, next_project_number, next_ecr_number,
    list_projects, get_project, create_project, update_project,
    list_project_tasks, list_tasks, get_task, create_task, update_task,
    list_ecrs, get_ecr, create_ecr, update_ecr, set_ecr_status,
    ENG_STANDARD_STATUSES, ENG_STANDARD_CATEGORIES,
    list_eng_standards, get_eng_standard,
    create_eng_standard, update_eng_standard, init_eng_standard_table,
    eng_reports as _eng_reports_data,
)

_ENGINEERING_DEPT_KEYS = {'engineering'}


def _eng_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
        'PROJECT_STATUSES': PROJECT_STATUSES,
        'TASK_STATUSES': TASK_STATUSES,
        'ECR_STATUSES': ECR_STATUSES,
        'PRIORITIES': PRIORITIES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_dashboard(request):
    with get_db_connection() as conn:
        dash = get_eng_dashboard(conn)
        recent_projects = list_projects(conn)[:8]
        recent_ecrs = list_ecrs(conn)[:8]
        init_eng_standard_table(conn)

        project_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM eng_project GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        project_status_json = json.dumps([dict(r) for r in project_status_rows])

        task_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM eng_task GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        task_status_json = json.dumps([dict(r) for r in task_status_rows])

        task_priority_rows = conn.execute("""
            SELECT priority, COUNT(*) AS cnt FROM eng_task
            WHERE status NOT IN ('completed', 'cancelled')
            GROUP BY priority ORDER BY cnt DESC
        """).fetchall()
        task_priority_json = json.dumps([dict(r) for r in task_priority_rows])

        ecr_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM eng_design_review GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        ecr_status_json = json.dumps([dict(r) for r in ecr_status_rows])

        project_engineer_rows = conn.execute("""
            SELECT engineer, COUNT(*) AS cnt FROM eng_project
            WHERE engineer IS NOT NULL AND engineer != ''
            GROUP BY engineer ORDER BY cnt DESC LIMIT 8
        """).fetchall()
        project_engineer_json = json.dumps([dict(r) for r in project_engineer_rows])

        standard_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM eng_standard GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        standard_status_json = json.dumps([dict(r) for r in standard_status_rows])

    ctx = _eng_ctx(request, dash=dash,
                   recent_projects=recent_projects, recent_ecrs=recent_ecrs,
                   project_status_json=project_status_json,
                   task_status_json=task_status_json,
                   task_priority_json=task_priority_json,
                   ecr_status_json=ecr_status_json,
                   project_engineer_json=project_engineer_json,
                   standard_status_json=standard_status_json)
    return render(request, 'eng_dashboard.html', ctx)


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_projects(request):
    status = request.GET.get('status', '')
    engineer = request.GET.get('engineer', '')
    search = request.GET.get('search', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST' and request.POST.get('action') == 'new':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('eng_dashboard')
            try:
                pid = create_project(
                    conn,
                    project_number='',
                    title=request.POST.get('title', '').strip(),
                    product_id=request.POST.get('product_id') or None,
                    engineer=request.POST.get('engineer', '').strip(),
                    start_date=request.POST.get('start_date', ''),
                    due_date=request.POST.get('due_date', '') or None,
                    status=request.POST.get('status', 'planning'),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect(f'/eng/projects/{pid}/')
            except Exception as e:
                error = str(e)
        projects = list_projects(conn, status=status or None,
                                 engineer=engineer or None,
                                 search=search or None)
        products = load_products(conn)
        people = load_people(conn)
    ctx = _eng_ctx(request, projects=projects, products=products, people=people,
                   filter_status=status, filter_engineer=engineer,
                   filter_search=search, error=error, success=success)
    return render(request, 'eng_projects.html', ctx)


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_project_detail(request, project_id=None):
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('eng_dashboard')
            action = request.POST.get('action', '')
            try:
                if action == 'save':
                    if project_id:
                        update_project(
                            conn, project_id,
                            title=request.POST.get('title', '').strip(),
                            product_id=request.POST.get('product_id') or None,
                            engineer=request.POST.get('engineer', '').strip(),
                            start_date=request.POST.get('start_date', ''),
                            due_date=request.POST.get('due_date', '') or None,
                            status=request.POST.get('status', 'planning'),
                            notes=request.POST.get('notes', '').strip(),
                        )
                        conn.commit()
                        success = 'Project updated.'
                elif action == 'add_task':
                    create_task(
                        conn,
                        project_id=project_id,
                        task_name=request.POST.get('task_name', '').strip(),
                        assigned_to=request.POST.get('assigned_to', '').strip(),
                        due_date=request.POST.get('due_date', '') or None,
                        priority=request.POST.get('priority', 'medium'),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Task added.'
                elif action == 'update_task':
                    update_task(
                        conn,
                        task_id=int(request.POST.get('task_id', 0)),
                        task_name=request.POST.get('task_name', '').strip(),
                        assigned_to=request.POST.get('assigned_to', '').strip(),
                        due_date=request.POST.get('due_date', '') or None,
                        priority=request.POST.get('priority', 'medium'),
                        status=request.POST.get('status', 'open'),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Task updated.'
            except Exception as e:
                error = str(e)
        project = get_project(conn, project_id) if project_id else None
        tasks = list_project_tasks(conn, project_id) if project_id else []
        products = load_products(conn)
        people = load_people(conn)
        new_proj_num = next_project_number(conn) if not project_id else ''
    ctx = _eng_ctx(request, project=project, tasks=tasks,
                   products=products, people=people,
                   new_proj_num=new_proj_num,
                   error=error, success=success)
    return render(request, 'eng_project_detail.html', ctx)


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_ecrs(request):
    status = request.GET.get('status', '')
    proj_filter = request.GET.get('project_id', '')
    search = request.GET.get('search', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST' and request.POST.get('action') == 'new':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('eng_dashboard')
            try:
                eid = create_ecr(
                    conn,
                    ecr_number='',
                    title=request.POST.get('title', '').strip(),
                    product_id=request.POST.get('product_id') or None,
                    project_id=request.POST.get('project_id') or None,
                    requested_by=request.POST.get('requested_by', '').strip(),
                    review_date=request.POST.get('review_date', '') or None,
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect(f'/eng/ecrs/{eid}/')
            except Exception as e:
                error = str(e)
        ecrs = list_ecrs(conn,
                         status=status or None,
                         project_id=int(proj_filter) if proj_filter.isdigit() else None,
                         search=search or None)
        projects = list_projects(conn)
        products = load_products(conn)
        people = load_people(conn)
    ctx = _eng_ctx(request, ecrs=ecrs, projects=projects, products=products,
                   people=people, filter_status=status,
                   filter_project=proj_filter, filter_search=search,
                   error=error, success=success)
    return render(request, 'eng_ecrs.html', ctx)


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_ecr_detail(request, ecr_id=None):
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('eng_dashboard')
            action = request.POST.get('action', '')
            try:
                if action == 'save' and ecr_id:
                    update_ecr(
                        conn, ecr_id,
                        title=request.POST.get('title', '').strip(),
                        product_id=request.POST.get('product_id') or None,
                        project_id=request.POST.get('project_id') or None,
                        requested_by=request.POST.get('requested_by', '').strip(),
                        review_date=request.POST.get('review_date', '') or None,
                        status=request.POST.get('status', 'draft'),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'ECR updated.'
                elif action == 'status' and ecr_id:
                    set_ecr_status(conn, ecr_id,
                                   request.POST.get('new_status', 'draft'))
                    conn.commit()
                    success = 'Status updated.'
                elif action == 'create':
                    eid = create_ecr(
                        conn,
                        ecr_number=request.POST.get('ecr_number', '').strip(),
                        title=request.POST.get('title', '').strip(),
                        product_id=request.POST.get('product_id') or None,
                        project_id=request.POST.get('project_id') or None,
                        requested_by=request.POST.get('requested_by', '').strip(),
                        review_date=request.POST.get('review_date', '') or None,
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect(f'/eng/ecrs/{eid}/')
            except Exception as e:
                error = str(e)
        ecr = get_ecr(conn, ecr_id) if ecr_id else None
        projects = list_projects(conn)
        products = load_products(conn)
        people = load_people(conn)
        new_ecr_num = next_ecr_number(conn) if not ecr_id else ''
    ctx = _eng_ctx(request, ecr=ecr, projects=projects, products=products,
                   people=people, new_ecr_num=new_ecr_num,
                   error=error, success=success)
    return render(request, 'eng_ecr_detail.html', ctx)


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_reports_view(request):
    with get_db_connection() as conn:
        data = _eng_reports_data(conn)
    ctx = _eng_ctx(request, **data)
    return render(request, 'eng_reports.html', ctx)


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_tasks_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    priority_f = request.GET.get('priority', '').strip()
    error = success = None
    with get_db_connection() as conn:
        if request.method == 'POST' and can_edit:
            try:
                create_task(
                    conn,
                    project_id=request.POST.get('project_id') or None,
                    task_name=request.POST.get('task_name', '').strip(),
                    assigned_to=request.POST.get('assigned_to', '').strip(),
                    due_date=request.POST.get('due_date', '') or None,
                    priority=request.POST.get('priority', 'medium'),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('eng_tasks_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
        tasks = list_tasks(
            conn,
            status=status_f or None,
            priority=priority_f or None,
        )
        projects = list_projects(conn)
        people = load_people(conn)
    if 'export' in request.GET:
        return export_response(request, 'eng_tasks', [
            ('task_name', 'Task'), ('project_title', 'Project'), ('assigned_to', 'Assigned To'),
            ('due_date', 'Due Date'), ('priority', 'Priority'), ('status', 'Status'),
        ], tasks)

    return render(request, 'eng_tasks_list.html', _eng_ctx(
        request, tasks=tasks, projects=projects, people=people,
        status_filter=status_f, priority_filter=priority_f,
        TASK_STATUSES=TASK_STATUSES, PRIORITIES=PRIORITIES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_task_detail(request, task_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    with get_db_connection() as conn:
        task = get_task(conn, task_id)
        if not task:
            return redirect('eng_tasks_list')
        task = dict(task)
        projects = list_projects(conn) if can_edit else []
        people = load_people(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            try:
                update_task(
                    conn, task_id,
                    task_name=request.POST.get('task_name', '').strip(),
                    assigned_to=request.POST.get('assigned_to', '').strip(),
                    due_date=request.POST.get('due_date', '') or None,
                    priority=request.POST.get('priority', 'medium'),
                    status=request.POST.get('status', 'open'),
                    notes=request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Task updated.'
                task = dict(get_task(conn, task_id))
            except Exception as e:
                conn.rollback()
                error = str(e)
    return render(request, 'eng_task_detail.html', _eng_ctx(
        request, task=task, projects=projects, people=people, can_edit=can_edit,
        TASK_STATUSES=TASK_STATUSES, PRIORITIES=PRIORITIES,
        error=error, success=success,
    ))


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_specs_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    cat_f = request.GET.get('category', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_eng_standard_table(conn)
        specs = list_eng_standards(
            conn, status=status_f or None,
            category=cat_f or None, search=search or None,
        )
        if request.method == 'POST' and can_edit:
            try:
                create_eng_standard(
                    conn,
                    standard_number=request.POST.get('standard_number', ''),
                    title=request.POST.get('title', ''),
                    category=request.POST.get('category', ''),
                    version=request.POST.get('version', ''),
                    status=request.POST.get('status', 'Active'),
                    review_date=request.POST.get('review_date', ''),
                    description=request.POST.get('description', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('eng_specs_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                specs = list_eng_standards(
                    conn, status=status_f or None,
                    category=cat_f or None, search=search or None,
                )
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'eng_specs', [
            ('standard_number', 'Spec Number'), ('title', 'Title'),
            ('category', 'Category'), ('version', 'Version'), ('status', 'Status'),
        ], specs)

    return render(request, 'eng_specs_list.html', _eng_ctx(
        request, specs=specs, status_filter=status_f, category_filter=cat_f,
        search=search, spec_statuses=ENG_STANDARD_STATUSES,
        spec_categories=ENG_STANDARD_CATEGORIES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_ENGINEERING_DEPT_KEYS)
def eng_spec_detail(request, spec_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        spec = get_eng_standard(conn, spec_id)
        if not spec:
            return redirect('eng_specs_list')
        if request.method == 'POST' and can_edit:
            try:
                update_eng_standard(
                    conn, spec_id,
                    standard_number=request.POST.get('standard_number', ''),
                    title=request.POST.get('title', ''),
                    category=request.POST.get('category', ''),
                    version=request.POST.get('version', ''),
                    status=request.POST.get('status', ''),
                    review_date=request.POST.get('review_date', ''),
                    description=request.POST.get('description', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Standard updated.'
                spec = get_eng_standard(conn, spec_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'eng_spec_detail.html', _eng_ctx(
        request, spec=spec, can_edit=can_edit,
        spec_statuses=ENG_STANDARD_STATUSES, spec_categories=ENG_STANDARD_CATEGORIES,
        error=error, success=success,
    ))


from ..sales_core import (  # noqa: E402
    SO_STATUSES, SO_STATUS_ACTION_LABELS,  # noqa: F811
    allowed_transitions, can_transition, next_so_number, list_sos, get_so, get_so_items,  # noqa: F811
    load_customers, load_products,  # noqa: F811
    create_so, update_so, add_so_item, delete_so_item, set_so_status,  # noqa: F811
    QUOTE_STATUSES, TARGET_STATUSES,
    get_sales_dashboard, get_revenue_by_month, get_sales_reports,
    list_quotes, create_quote, update_quote, set_quote_status,
    list_targets, create_target, update_target,
    SALES_LEAD_STATUSES, SALES_LEAD_SOURCES, SALES_LEAD_PRIORITIES,
    list_sales_leads, get_sales_lead, create_sales_lead, update_sales_lead,
    init_sales_lead_table,
    SALES_CONTRACT_STATUSES,
    list_sales_contracts, get_sales_contract,
    create_sales_contract, update_sales_contract, init_sales_contract_table,
    FORECAST_PERIODS, FORECAST_STATUSES,
    list_forecasts, get_forecast, create_forecast, update_forecast,
    init_sales_forecast_table, get_forecast_kpis, get_period_actuals,
    get_demand_by_product, update_forecast_actual,
    # Territories
    TERRITORY_STATUSES,
    init_sales_territory_table, list_territories, create_territory, update_territory, get_territory_performance,
    # Commissions
    COMMISSION_PLAN_TYPES, COMMISSION_STATUSES,
    init_commission_tables,
    list_commission_plans, create_commission_plan, update_commission_plan,
    list_commissions, create_commission, update_commission,
    get_commission_summary,
    # Performance
    get_sales_performance,
    COACHING_NOTE_STATUSES, PERF_REVIEW_STATUSES,
    init_sales_performance_tables,
    list_coaching_notes, create_coaching_note,
    list_perf_reviews, create_perf_review,
)

_SALES_DEPT_KEYS = {'sales'}


def _sales_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
        'SO_STATUSES': SO_STATUSES,
        'SO_STATUS_ACTION_LABELS': SO_STATUS_ACTION_LABELS,
        'QUOTE_STATUSES': QUOTE_STATUSES,
        'TARGET_STATUSES': TARGET_STATUSES,
    }
    ctx.update(extra)
    return ctx


@dept_required(_SALES_DEPT_KEYS)
def sales_dashboard(request):
    with get_db_connection() as conn:
        dash = get_sales_dashboard(conn)
        recent_orders = list_sos(conn)[:8]
        recent_quotes = list_quotes(conn)[:8]
        revenue_by_month = get_revenue_by_month(conn)
        top_customers = conn.execute("""
            SELECT c.company_name AS customer,
                   COALESCE(SUM(si.qty * si.unit_price), 0) AS revenue
            FROM sales_order so
            JOIN customer c ON c.id = so.customer_id
            JOIN so_item si ON si.so_id = so.id
            WHERE so.status IN ('confirmed','shipped','invoiced')
            GROUP BY c.company_name
            ORDER BY revenue DESC
            LIMIT 8
        """).fetchall()
        leads_by_status = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM sales_lead
            GROUP BY status
            ORDER BY cnt DESC
        """).fetchall()
        top_products = conn.execute("""
            SELECT COALESCE(p.name, si.description, 'Unknown') AS product,
                   COALESCE(SUM(si.qty * si.unit_price), 0) AS revenue
            FROM so_item si
            LEFT JOIN product p ON p.id = si.product_id
            JOIN sales_order so ON so.id = si.so_id
            WHERE so.status IN ('confirmed','shipped','invoiced')
            GROUP BY COALESCE(p.name, si.description, 'Unknown')
            ORDER BY revenue DESC LIMIT 8
        """).fetchall()
        order_status = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM sales_order GROUP BY status ORDER BY cnt DESC
        """).fetchall()
    ctx = _sales_ctx(
        request, dash=dash,
        recent_orders=recent_orders, recent_quotes=recent_quotes,
        quote_funnel_json=json.dumps(dash.get('quotes', {})),
        revenue_by_month_json=json.dumps(revenue_by_month),
        top_customers_json=json.dumps([dict(r) for r in top_customers]),
        leads_by_status_json=json.dumps([dict(r) for r in leads_by_status]),
        orders_by_status_json=json.dumps(dash.get('orders', {})),
        top_products_json=json.dumps([dict(r) for r in top_products]),
        order_status_json=json.dumps([dict(r) for r in order_status]),
    )
    return render(request, 'sales_dashboard.html', ctx)


@dept_required(_SALES_DEPT_KEYS)
def sales_reports_view(request):
    period = request.GET.get('period', 'month')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    today = date.today()

    if date_from and date_to:
        try:
            start = date.fromisoformat(date_from)
            end = date.fromisoformat(date_to)
            if end < start:
                start, end = end, start
        except ValueError:
            start, end = today.replace(day=1), today
        period = 'custom'
    elif period == 'day':
        start = end = today
    elif period == 'quarter':
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=q_start_month, day=1)
        end = today
    elif period == 'year':
        start = today.replace(month=1, day=1)
        end = today
    else:
        period = 'month'
        start = today.replace(day=1)
        end = today

    with get_db_connection() as conn:
        data = get_sales_reports(conn, start.isoformat(), end.isoformat())

    return render(request, 'sales_reports.html', _sales_ctx(
        request, **data, period=period,
        start=start.isoformat(), end=end.isoformat(),
        date_from=date_from, date_to=date_to,
        trend_json=json.dumps(data['trend'], default=str),
        top_customers_json=json.dumps(data['top_customers']),
        top_products_json=json.dumps(data['top_products']),
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_orders_list(request):
    status = request.GET.get('status', '')
    customer_id = request.GET.get('customer_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST' and request.POST.get('action') == 'new':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('sales_dashboard')
            try:
                so_num = next_so_number(conn)
                so_id = create_so(
                    conn,
                    so_number=so_num,
                    customer_id=request.POST.get('customer_id') or None,
                    order_date=request.POST.get('order_date') or None,
                    ship_date=request.POST.get('ship_date') or None,
                    status='draft',
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect(f'/sales/orders/{so_id}/')
            except Exception as e:
                error = str(e)
        orders = list_sos(conn,
                          status=status or None,
                          customer_id=int(customer_id) if customer_id.isdigit() else None,
                          date_from=date_from or None,
                          date_to=date_to or None)
        customers = load_customers(conn)
    ctx = _sales_ctx(request, orders=orders, customers=customers,
                     filter_status=status, filter_customer=customer_id,
                     filter_date_from=date_from, filter_date_to=date_to,
                     error=error, success=success)
    return render(request, 'sales_orders.html', ctx)


@dept_required(_SALES_DEPT_KEYS)
def sales_order_detail(request, so_id=None):
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('sales_dashboard')
            action = request.POST.get('action', '')
            try:
                if action == 'save' and so_id:
                    update_so(conn, so_id,
                              customer_id=request.POST.get('customer_id') or None,
                              order_date=request.POST.get('order_date') or None,
                              ship_date=request.POST.get('ship_date') or None,
                              notes=request.POST.get('notes', '').strip())
                    conn.commit()
                    success = 'Order updated.'
                elif action == 'status' and so_id:
                    new_status = request.POST.get('new_status', '')
                    so = get_so(conn, so_id)
                    if so and can_transition(so['status'], new_status):
                        set_so_status(conn, so_id, new_status)
                        conn.commit()
                        success = f'Status changed to {new_status}.'
                    else:
                        error = 'Invalid status transition.'
                elif action == 'add_item' and so_id:
                    add_so_item(conn, so_id,
                                description=request.POST.get('description', '').strip(),
                                product_id=request.POST.get('product_id') or None,
                                qty=int(request.POST.get('qty', 1) or 1),
                                unit_price=float(request.POST.get('unit_price', 0) or 0))
                    conn.commit()
                    success = 'Line item added.'
                elif action == 'delete_item':
                    item_id = int(request.POST.get('item_id', 0))
                    delete_so_item(conn, item_id, so_id=so_id)
                    conn.commit()
                    success = 'Line item removed.'
            except Exception as e:
                error = str(e)
        so = get_so(conn, so_id) if so_id else None
        items = get_so_items(conn, so_id) if so_id else []
        customers = load_customers(conn)
        products = load_products(conn)
        transitions = allowed_transitions(so['status']) if so else ()
    ctx = _sales_ctx(request, so=so, items=items,
                     customers=customers, products=products,
                     transitions=transitions,
                     error=error, success=success)
    return render(request, 'sales_order_detail.html', ctx)


@dept_required(_SALES_DEPT_KEYS)
def sales_quotes(request):
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('sales_dashboard')
            action = request.POST.get('action', '')
            try:
                if action == 'new':
                    qid = create_quote(
                        conn,
                        customer=request.POST.get('customer', '').strip(),
                        description=request.POST.get('description', '').strip(),
                        amount=request.POST.get('amount', 0),
                        owner=request.POST.get('owner', '').strip(),
                        quote_date=request.POST.get('quote_date') or None,
                        valid_until=request.POST.get('valid_until') or None,
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = f'Quote #{qid} created.'
                elif action == 'update':
                    update_quote(
                        conn,
                        quote_id=int(request.POST.get('quote_id', 0)),
                        customer=request.POST.get('customer', '').strip(),
                        description=request.POST.get('description', '').strip(),
                        amount=request.POST.get('amount', 0),
                        owner=request.POST.get('owner', '').strip(),
                        quote_date=request.POST.get('quote_date') or None,
                        valid_until=request.POST.get('valid_until') or None,
                        status=request.POST.get('status', 'Draft'),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Quote updated.'
                elif action == 'set_status':
                    set_quote_status(conn,
                                     int(request.POST.get('quote_id', 0)),
                                     request.POST.get('new_status', 'Draft'))
                    conn.commit()
                    success = 'Quote status updated.'
            except Exception as e:
                error = str(e)
        quotes = list_quotes(conn, status=status or None,
                             search=search or None)
    ctx = _sales_ctx(request, quotes=quotes,
                     filter_status=status, filter_search=search,
                     error=error, success=success)
    return render(request, 'sales_quotes.html', ctx)


@dept_required(_SALES_DEPT_KEYS)
def sales_targets(request):
    rep_filter = request.GET.get('rep', '')
    period_filter = request.GET.get('period', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            if request.session.get('user_role') in READ_ONLY_ROLES:
                return redirect('sales_dashboard')
            action = request.POST.get('action', '')
            try:
                if action == 'new':
                    create_target(
                        conn,
                        rep=request.POST.get('rep', '').strip(),
                        period=request.POST.get('period', '').strip(),
                        target=request.POST.get('target', 0),
                        actual=request.POST.get('actual', 0),
                        region=request.POST.get('region', '').strip(),
                        status=request.POST.get('status', 'On Track'),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Target added.'
                elif action == 'update':
                    update_target(
                        conn,
                        target_id=int(request.POST.get('target_id', 0)),
                        rep=request.POST.get('rep', '').strip(),
                        period=request.POST.get('period', '').strip(),
                        target=request.POST.get('target', 0),
                        actual=request.POST.get('actual', 0),
                        region=request.POST.get('region', '').strip(),
                        status=request.POST.get('status', 'On Track'),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Target updated.'
            except Exception as e:
                error = str(e)
        targets = list_targets(conn,
                               rep=rep_filter or None,
                               period=period_filter or None)
        periods = conn.execute(
            "SELECT DISTINCT period FROM sales_target ORDER BY period DESC"
        ).fetchall()
        reps = conn.execute(
            "SELECT DISTINCT rep FROM sales_target ORDER BY rep"
        ).fetchall()
    ctx = _sales_ctx(request, targets=targets,
                     periods=[r['period'] for r in periods],
                     reps=[r['rep'] for r in reps],
                     filter_rep=rep_filter, filter_period=period_filter,
                     error=error, success=success)
    return render(request, 'sales_targets.html', ctx)


@dept_required(_SALES_DEPT_KEYS)
def sales_leads_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_sales_lead_table(conn)
        leads = list_sales_leads(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and can_edit:
            try:
                create_sales_lead(
                    conn,
                    company=request.POST.get('company', ''),
                    contact=request.POST.get('contact', ''),
                    source=request.POST.get('source', ''),
                    status=request.POST.get('status', 'New'),
                    priority=request.POST.get('priority', 'Medium'),
                    estimated_value=float(request.POST.get('estimated_value') or 0),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('sales_leads_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                leads = list_sales_leads(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'sales_leads', [
            ('company', 'Company'), ('contact', 'Contact'), ('source', 'Source'),
            ('owner', 'Owner'), ('priority', 'Priority'), ('status', 'Status'),
        ], leads)

    return render(request, 'sales_leads_list.html', _sales_ctx(
        request, leads=leads, status_filter=status_f, search=search,
        lead_statuses=SALES_LEAD_STATUSES, lead_sources=SALES_LEAD_SOURCES,
        lead_priorities=SALES_LEAD_PRIORITIES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_leads_detail(request, lead_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        lead = get_sales_lead(conn, lead_id)
        if not lead:
            return redirect('sales_leads_list')
        if request.method == 'POST' and can_edit:
            try:
                update_sales_lead(
                    conn, lead_id,
                    company=request.POST.get('company', ''),
                    contact=request.POST.get('contact', ''),
                    source=request.POST.get('source', ''),
                    status=request.POST.get('status', ''),
                    priority=request.POST.get('priority', ''),
                    estimated_value=float(request.POST.get('estimated_value') or 0),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Lead updated.'
                lead = get_sales_lead(conn, lead_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'sales_leads_detail.html', _sales_ctx(
        request, lead=lead, can_edit=can_edit,
        lead_statuses=SALES_LEAD_STATUSES, lead_sources=SALES_LEAD_SOURCES,
        lead_priorities=SALES_LEAD_PRIORITIES,
        error=error, success=success,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_contracts_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_sales_contract_table(conn)
        contracts = list_sales_contracts(conn, status=status_f or None, search=search or None)
        if request.method == 'POST' and can_edit:
            try:
                create_sales_contract(
                    conn,
                    customer=request.POST.get('customer', ''),
                    title=request.POST.get('title', ''),
                    value=float(request.POST.get('value') or 0),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    renewal_date=request.POST.get('renewal_date', ''),
                    status=request.POST.get('status', 'Draft'),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('sales_contracts_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                contracts = list_sales_contracts(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'sales_contracts', [
            ('customer', 'Customer'), ('title', 'Title'), ('value', 'Value'),
            ('start_date', 'Start Date'), ('end_date', 'End Date'), ('status', 'Status'),
        ], contracts)

    return render(request, 'sales_contracts_list.html', _sales_ctx(
        request, contracts=contracts, status_filter=status_f, search=search,
        contract_statuses=SALES_CONTRACT_STATUSES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_contracts_detail(request, contract_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        contract = get_sales_contract(conn, contract_id)
        if not contract:
            return redirect('sales_contracts_list')
        if request.method == 'POST' and can_edit:
            try:
                update_sales_contract(
                    conn, contract_id,
                    customer=request.POST.get('customer', ''),
                    title=request.POST.get('title', ''),
                    value=float(request.POST.get('value') or 0),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    renewal_date=request.POST.get('renewal_date', ''),
                    status=request.POST.get('status', ''),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Contract updated.'
                contract = get_sales_contract(conn, contract_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'sales_contracts_detail.html', _sales_ctx(
        request, contract=contract, can_edit=can_edit,
        contract_statuses=SALES_CONTRACT_STATUSES,
        error=error, success=success,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_forecast_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    period_f = request.GET.get('period', '').strip()
    search = request.GET.get('search', '').strip()
    fiscal_year = int(request.GET.get('fiscal_year') or 0) or date.today().year
    error = success = None
    conn = get_db_connection()
    try:
        init_sales_forecast_table(conn)
        forecasts = list_forecasts(conn, period=period_f or None, search=search or None)
        kpis = get_forecast_kpis(conn, period=period_f or None, search=search or None)
        period_actuals = get_period_actuals(conn, fiscal_year)
        if request.method == 'POST' and can_edit:
            try:
                create_forecast(
                    conn,
                    rep=request.POST.get('rep', ''),
                    period=request.POST.get('period', ''),
                    fiscal_year=int(request.POST.get('fiscal_year') or 0),
                    product_line=request.POST.get('product_line', ''),
                    expected_value=float(request.POST.get('expected_value') or 0),
                    probability=int(request.POST.get('probability') or 0),
                    status=request.POST.get('status', 'Draft'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('sales_forecast_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                forecasts = list_forecasts(conn, period=period_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'sales_forecast_list.html', _sales_ctx(
        request, forecasts=forecasts, period_filter=period_f, search=search,
        fiscal_year=fiscal_year, kpis=kpis, period_actuals=period_actuals,
        forecast_periods=FORECAST_PERIODS, forecast_statuses=FORECAST_STATUSES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_forecast_detail(request, forecast_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        init_sales_forecast_table(conn)
        forecast = get_forecast(conn, forecast_id)
        if not forecast:
            return redirect('sales_forecast_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'actual':
                    update_forecast_actual(
                        conn, forecast_id,
                        actual_value=float(request.POST.get('actual_value') or 0),
                    )
                else:
                    update_forecast(
                        conn, forecast_id,
                        rep=request.POST.get('rep', ''),
                        period=request.POST.get('period', ''),
                        fiscal_year=int(request.POST.get('fiscal_year') or 0),
                        product_line=request.POST.get('product_line', ''),
                        expected_value=float(request.POST.get('expected_value') or 0),
                        probability=int(request.POST.get('probability') or 0),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                conn.commit()
                success = 'Forecast updated.'
                forecast = get_forecast(conn, forecast_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        actual = float(forecast.get('actual_value') or 0)
        weighted = float(forecast.get('weighted_value') or 0)
        variance = actual - weighted
        attainment = round(actual / weighted * 100, 1) if weighted else None
    finally:
        conn.close()
    return render(request, 'sales_forecast_detail.html', _sales_ctx(
        request, forecast=forecast, can_edit=can_edit,
        forecast_periods=FORECAST_PERIODS, forecast_statuses=FORECAST_STATUSES,
        error=error, success=success,
        actual=actual, variance=variance, attainment=attainment,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_demand(request):
    fiscal_year = int(request.GET.get('fiscal_year') or 0) or date.today().year
    conn = get_db_connection()
    try:
        init_sales_forecast_table(conn)
        demand_rows = get_demand_by_product(conn, fiscal_year)
        forecasts = list_forecasts(conn)
    finally:
        conn.close()

    # Pivot: product → {Q1, Q2, Q3, Q4, total_revenue, total_units}
    products: dict = {}
    for r in demand_rows:
        prod = r['product']
        if prod not in products:
            products[prod] = {'product': prod, 'Q1': 0, 'Q2': 0, 'Q3': 0, 'Q4': 0,
                              'total_revenue': 0, 'total_units': 0}
        qkey = f"Q{int(r['qtr'])}"
        products[prod][qkey] = float(r['revenue'])
        products[prod]['total_revenue'] += float(r['revenue'])
        products[prod]['total_units'] += int(r['units'])

    product_rows = sorted(products.values(), key=lambda x: -x['total_revenue'])

    # Quarter totals
    quarter_totals = {
        'Q1': sum(p['Q1'] for p in product_rows),
        'Q2': sum(p['Q2'] for p in product_rows),
        'Q3': sum(p['Q3'] for p in product_rows),
        'Q4': sum(p['Q4'] for p in product_rows),
    }
    quarter_totals['total'] = sum(quarter_totals.values())

    # Forecast summary by period for comparison
    forecast_by_period: dict = {}
    for f in forecasts:
        if f.get('fiscal_year') == fiscal_year:
            p = f.get('period', '')
            forecast_by_period[p] = forecast_by_period.get(p, 0) + float(f.get('weighted_value') or 0)

    years = list(range(date.today().year - 3, date.today().year + 2))

    return render(request, 'sales_demand.html', _sales_ctx(
        request, fiscal_year=fiscal_year, years=years,
        product_rows=product_rows, quarter_totals=quarter_totals,
        forecast_by_period=forecast_by_period,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
    ))


def _prod_ctx(request, **extra):
    role = request.session.get('user_role', '')
    return {
        'email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
        **extra,
    }


@dept_required('production')
def prod_dashboard(request):
    with get_db_connection() as conn:
        data = get_production_dashboard(conn)
        daily_output = get_daily_output_trend(conn)
        wo_status_breakdown = get_wo_status_breakdown(conn)
        top_products = conn.execute("""
            SELECT p.name AS product, COALESCE(SUM(wo.quantity), 0) AS qty
            FROM work_order wo
            JOIN product p ON p.id = wo.product_id
            WHERE wo.status = 'completed'
              AND wo.due_date::date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY p.name
            ORDER BY qty DESC
            LIMIT 8
        """).fetchall()
        on_time_row = conn.execute("""
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'completed'
                      AND due_date::date >= CURRENT_DATE - INTERVAL '30 days'
                ) AS total_completed,
                COUNT(*) FILTER (
                    WHERE status = 'completed'
                      AND due_date::date >= CURRENT_DATE - INTERVAL '30 days'
                      AND due_date::date >= CURRENT_DATE
                ) AS on_time
            FROM work_order
        """).fetchone()
        scrap_rework = conn.execute("""
            SELECT operation_name,
                   COALESCE(SUM(scrap_qty), 0)  AS scrap,
                   COALESCE(SUM(rework_qty), 0) AS rework
            FROM wo_operation
            WHERE operation_name IS NOT NULL
            GROUP BY operation_name
            ORDER BY (SUM(scrap_qty) + SUM(rework_qty)) DESC
            LIMIT 8
        """).fetchall()
        wo_by_month = conn.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', due_date::date), 'Mon YYYY') AS month,
                   COUNT(*) AS cnt
            FROM work_order
            WHERE status = 'completed'
              AND due_date >= (CURRENT_DATE - INTERVAL '6 months')::text
            GROUP BY DATE_TRUNC('month', due_date::date)
            ORDER BY DATE_TRUNC('month', due_date::date)
        """).fetchall()
    on_time = dict(on_time_row) if on_time_row else {}
    ctx = _prod_ctx(
        request, **data,
        daily_output_json=json.dumps(daily_output),
        wo_status_json=json.dumps(wo_status_breakdown),
        top_products_json=json.dumps([dict(r) for r in top_products]),
        on_time_json=json.dumps(on_time),
        scrap_rework_json=json.dumps([dict(r) for r in scrap_rework]),
        wo_by_month_json=json.dumps([dict(r) for r in wo_by_month]),
    )
    return render(request, 'prod_dashboard.html', ctx)


@dept_required('production')
def prod_schedule(request):
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    status_f = request.GET.get('status', '').strip()
    with get_db_connection() as conn:
        wos = list_scheduled_wos(
            conn,
            date_from=date_from or None,
            date_to=date_to or None,
            status=status_f or None,
        )
    return render(request, 'prod_schedule.html', _prod_ctx(
        request, wos=wos,
        date_from=date_from, date_to=date_to, status_filter=status_f,
        WO_STATUSES=WO_STATUSES,
    ))


@dept_required('production')
def prod_reports_view(request):
    with get_db_connection() as conn:
        data = get_prod_reports(conn)
    return render(request, 'prod_reports.html', _prod_ctx(request, **data))


@dept_required('production')
def prod_shipping_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        conn.commit()
        shipments = list_shipments(conn, status=status_f or None, search=search or None)
        sales_orders = list_sos(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            try:
                sid = create_shipment(
                    conn,
                    so_id=_int_or_none(request.POST.get('so_id')),
                    ship_date=request.POST.get('ship_date', ''),
                    carrier=request.POST.get('carrier', '').strip(),
                    tracking_number=request.POST.get('tracking_number', '').strip(),
                    status=request.POST.get('status', 'pending'),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('prod_shipping_detail', shipment_id=sid)
            except Exception as e:
                conn.rollback()
                error = str(e)
                shipments = list_shipments(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'shipments', [
            ('id', 'ID'), ('ship_number', 'Ship #'), ('ship_date', 'Ship Date'),
            ('carrier', 'Carrier'), ('tracking_number', 'Tracking #'), ('status', 'Status'),
        ], shipments)

    return render(request, 'prod_shipping_list.html', _prod_ctx(
        request, shipments=shipments, sales_orders=sales_orders,
        status_filter=status_f, search=search,
        SHIPMENT_STATUSES=SHIPMENT_STATUSES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required('production')
def prod_shipping_detail(request, shipment_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = None
    success = request.session.pop('_ec_flash', None)
    conn = get_db_connection()
    try:
        shipment = get_shipment(conn, shipment_id)
        if not shipment:
            return redirect('prod_shipping_list')
        items = get_shipment_items(conn, shipment_id)
        products = load_wo_products(conn) if can_edit else []
        sales_orders = list_sos(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'edit')
            try:
                if action == 'add_item':
                    add_shipment_item(
                        conn, shipment_id,
                        description=request.POST.get('description', '').strip(),
                        product_id=_int_or_none(request.POST.get('product_id')),
                        qty=int(request.POST.get('qty') or 1),
                    )
                    conn.commit()
                    return redirect('prod_shipping_detail', shipment_id=shipment_id)
                else:
                    update_shipment(
                        conn, shipment_id,
                        so_id=_int_or_none(request.POST.get('so_id')),
                        ship_date=request.POST.get('ship_date', ''),
                        carrier=request.POST.get('carrier', '').strip(),
                        tracking_number=request.POST.get('tracking_number', '').strip(),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Shipment updated.'
                    shipment = get_shipment(conn, shipment_id)
                    items = get_shipment_items(conn, shipment_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'prod_shipping_detail.html', _prod_ctx(
        request, shipment=shipment, items=items,
        products=products, sales_orders=sales_orders,
        SHIPMENT_STATUSES=SHIPMENT_STATUSES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required('production')
def prod_tracking_dashboard(request):
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        conn.commit()
        data = get_tracking_dashboard(conn)
    finally:
        conn.close()
    return render(request, 'prod_tracking_dashboard.html', _prod_ctx(
        request, SHIPMENT_STATUSES=SHIPMENT_STATUSES, **data,
    ))


@dept_required('production')
def prod_delivery_status(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        conn.commit()
        shipments = get_delivery_status(
            conn, status_filter=status_f or None, search=search or None
        )
    finally:
        conn.close()
    return render(request, 'prod_delivery_status.html', _prod_ctx(
        request, shipments=shipments,
        status_filter=status_f, search=search,
        SHIPMENT_STATUSES=SHIPMENT_STATUSES,
    ))


@dept_required('production')
def prod_daily_report(request):
    report_date = request.GET.get('date', '').strip() or None
    with get_db_connection() as conn:
        data = get_daily_report(conn, report_date=report_date)
    return render(request, 'prod_daily_report.html', _prod_ctx(
        request, WO_STATUSES=WO_STATUSES, **data,
    ))


@dept_required('production')
def prod_performance_report(request):
    try:
        days = int(request.GET.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        conn.commit()
        data = get_performance_report(conn, days=days)
    finally:
        conn.close()
    return render(request, 'prod_performance_report.html', _prod_ctx(
        request, **data,
    ))


@dept_required('production')
def prod_returns_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_shipment_tables(conn)
        init_rma_table(conn)
        conn.commit()
        rmas = list_rmas(conn, status=status_f or None, search=search or None)
        sales_orders = list_sos(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            try:
                rma_id = create_rma(
                    conn,
                    so_id=_int_or_none(request.POST.get('so_id')),
                    customer=request.POST.get('customer', '').strip(),
                    reason=request.POST.get('reason', 'other'),
                    description=request.POST.get('description', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('prod_returns_detail', rma_id=rma_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
                rmas = list_rmas(
                    conn, status=status_f or None, search=search or None
                )
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'returns_rma', [
            ('rma_number', 'RMA #'), ('customer', 'Customer'), ('reason', 'Reason'),
            ('status', 'Status'), ('created_by', 'Created By'),
        ], rmas)

    return render(request, 'prod_returns_list.html', _prod_ctx(
        request, rmas=rmas, sales_orders=sales_orders,
        status_filter=status_f, search=search,
        RMA_STATUSES=RMA_STATUSES, RMA_REASONS=RMA_REASONS,
        error=error, success=success, can_edit=can_edit,
    ))


def prod_returns_new(request):
    """Shortcut that redirects to the list page (which includes the create form)."""
    return redirect('/prod/returns/')


@dept_required('production')
def prod_returns_detail(request, rma_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        init_rma_table(conn)
        conn.commit()
        rma = get_rma(conn, rma_id)
        if not rma:
            return redirect('prod_returns_list')
        sales_orders = list_sos(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            try:
                update_rma(
                    conn, rma_id,
                    so_id=_int_or_none(request.POST.get('so_id')),
                    customer=request.POST.get('customer', '').strip(),
                    reason=request.POST.get('reason', 'other'),
                    status=request.POST.get('status', ''),
                    description=request.POST.get('description', '').strip(),
                    resolution=request.POST.get('resolution', '').strip(),
                )
                conn.commit()
                success = 'Return updated.'
                rma = get_rma(conn, rma_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'prod_returns_detail.html', _prod_ctx(
        request, rma=rma, sales_orders=sales_orders,
        RMA_STATUSES=RMA_STATUSES, RMA_REASONS=RMA_REASONS,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required('production')
def prod_returns_reports(request):
    conn = get_db_connection()
    try:
        init_rma_table(conn)
        conn.commit()
        data = get_rma_reports(conn)
    finally:
        conn.close()
    return render(request, 'prod_returns_reports.html', _prod_ctx(
        request, RMA_STATUSES=RMA_STATUSES, RMA_REASONS=RMA_REASONS, **data,
    ))


# ---------------------------------------------------------------------------
# Purchasing dashboard
# ---------------------------------------------------------------------------

def _purch_ctx(request, **extra):
    role = request.session.get('user_role', '')
    return {
        'email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': request.session.get('user_full_access', False),
        'can_edit': role not in READ_ONLY_ROLES,
        **extra,
    }


@dept_required('purchasing')
def purch_dashboard(request):
    with get_db_connection() as conn:
        data = get_purchasing_dashboard(conn)
    ctx = _purch_ctx(
        request, **data,
        po_status_json=json.dumps(data.get('po_status_chart', [])),
        spend_by_month_json=json.dumps(data.get('spend_by_month', [])),
        top_suppliers_json=json.dumps(data.get('top_suppliers', [])),
        po_trend_json=json.dumps(data.get('po_trend', [])),
        top_items_json=json.dumps(data.get('top_items', [])),
        req_status_json=json.dumps(data.get('req_status', [])),
    )
    return render(request, 'purchasing_dashboard.html', ctx)


@dept_required('purchasing')
def purch_contracts_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    try:
        init_purch_contract_table(conn)
        if request.method == 'POST' and can_edit:
            title = request.POST.get('title', '').strip()
            if not title:
                error = 'Title is required.'
            else:
                try:
                    sup_id = request.POST.get('supplier_id') or None
                    val_str = request.POST.get('value', '').strip()
                    val = float(val_str) if val_str else None
                    create_purch_contract(
                        conn,
                        title=title,
                        category=request.POST.get('category', ''),
                        supplier_id=int(sup_id) if sup_id else None,
                        start_date=request.POST.get('start_date', '').strip() or None,
                        end_date=request.POST.get('end_date', '').strip() or None,
                        value=val,
                        status=request.POST.get('status', 'Active'),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    success = 'Contract created.'
                except Exception as exc:
                    error = str(exc)

        status_filter = request.GET.get('status', '')
        search = request.GET.get('search', '')
        contracts = list_purch_contracts(conn, status=status_filter or None, search=search or None)
        suppliers = conn.execute(
            "SELECT id, company_name FROM supplier ORDER BY company_name"
        ).fetchall()
    finally:
        conn.close()

    if 'export' in request.GET:
        return export_response(request, 'purch_contracts', [
            ('contract_number', 'Contract #'), ('title', 'Title'), ('supplier_name', 'Supplier'),
            ('category', 'Category'), ('start_date', 'Start Date'), ('end_date', 'End Date'),
            ('value', 'Value'), ('status', 'Status'),
        ], contracts)

    ctx = _purch_ctx(
        request,
        contracts=contracts,
        suppliers=[dict(s) for s in suppliers],
        CONTRACT_STATUSES=PURCH_CONTRACT_STATUSES,
        CONTRACT_CATEGORIES=PURCH_CONTRACT_CATEGORIES,
        status_filter=status_filter,
        search=search,
        can_edit=can_edit,
        error=error,
        success=success,
    )
    return render(request, 'purch_contracts_list.html', ctx)


@dept_required('purchasing')
def purch_contract_detail(request, contract_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    try:
        init_purch_contract_table(conn)
        contract = get_purch_contract(conn, contract_id)
        if contract is None:
            conn.close()
            return redirect('purch_contracts_list')
        if request.method == 'POST' and can_edit:
            title = request.POST.get('title', '').strip()
            if not title:
                error = 'Title is required.'
            else:
                try:
                    sup_id = request.POST.get('supplier_id') or None
                    val_str = request.POST.get('value', '').strip()
                    val = float(val_str) if val_str else None
                    update_purch_contract(
                        conn,
                        contract_id,
                        title=title,
                        category=request.POST.get('category', ''),
                        supplier_id=int(sup_id) if sup_id else None,
                        start_date=request.POST.get('start_date', '').strip() or None,
                        end_date=request.POST.get('end_date', '').strip() or None,
                        value=val,
                        status=request.POST.get('status', 'Active'),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    success = 'Contract updated.'
                    contract = get_purch_contract(conn, contract_id)
                except Exception as exc:
                    error = str(exc)

        suppliers = conn.execute(
            "SELECT id, company_name FROM supplier ORDER BY company_name"
        ).fetchall()
    finally:
        conn.close()

    ctx = _purch_ctx(
        request,
        contract=contract,
        suppliers=[dict(s) for s in suppliers],
        CONTRACT_STATUSES=PURCH_CONTRACT_STATUSES,
        CONTRACT_CATEGORIES=PURCH_CONTRACT_CATEGORIES,
        can_edit=can_edit,
        error=error,
        success=success,
    )
    return render(request, 'purch_contract_detail.html', ctx)


@dept_required('purchasing')
def purch_reports_view(request):
    conn = get_db_connection()
    try:
        init_purch_contract_table(conn)
        data = get_purch_reports(conn)
    finally:
        conn.close()
    ctx = _purch_ctx(request, **data)
    return render(request, 'purch_reports.html', ctx)


# ---------------------------------------------------------------------------
# Purchase Requisitions — open to every department (any employee can
# request goods/services), so gated by login_required only, not
# dept_required('purchasing'). Visibility within the list/detail views is
# still scoped by role, mirroring the Mobile API (api_views.py's api_req*).
# ---------------------------------------------------------------------------

def _req_actor(request, conn):
    """Resolve the caller's people_id/dept_id/role/full_access/is_manager
    for requisition visibility + authorization checks.

    is_manager here means "may authorize requisitions" — role in
    AUTHORIZER_ROLES (Dept Manager/Supervisor/President/VP), matching the
    Mobile API's api_auth._MANAGERS and purchase_requisitions_core.is_manager.
    That's a different, broader concept than the web session's
    user_is_manager flag (dept_sub_id-based menu visibility), so it's
    deliberately not reused here.
    """
    role = request.session.get('user_role', '')
    person = get_person_by_email(conn, request.session.get('user_email', ''))
    people_id = person['id'] if person else None
    full = person and get_person(conn, people_id)
    return {
        'people_id': people_id,
        'dept_id': full['dept_id'] if full else None,
        'role': role,
        'full_access': request.session.get('user_full_access', False),
        'is_manager': req_is_manager(role),
    }


@login_required
def req_list(request):
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = None
    conn = get_db_connection()
    try:
        actor = _req_actor(request, conn)
        if not actor['people_id']:
            return redirect('dashboard')
        rows = list_purchase_reqs(
            conn, full_access=actor['full_access'],
            is_manager_role=actor['is_manager'], dept_id=actor['dept_id'],
            requester_id=actor['people_id'], status=status_f or None,
            search=search or None,
        )
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                req_id = create_purchase_req(
                    conn,
                    requester_id=actor['people_id'], dept_id=actor['dept_id'],
                    dept_sub_id=None,
                    needed_date=request.POST.get('needed_date', ''),
                    justification=request.POST.get('justification', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('req_detail', req_id=req_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
                rows = list_purchase_reqs(
                    conn, full_access=actor['full_access'],
                    is_manager_role=actor['is_manager'], dept_id=actor['dept_id'],
                    requester_id=actor['people_id'], status=status_f or None,
                    search=search or None,
                )
    finally:
        conn.close()
    return render(request, 'req_list.html', _purch_ctx(
        request, rows=rows, status_filter=status_f, search=search,
        statuses=REQ_STATUSES, error=error,
    ))


@login_required
def req_detail(request, req_id):
    conn = get_db_connection()
    error = None
    req = None
    try:
        actor = _req_actor(request, conn)
        req = get_purchase_req(conn, req_id)
        if not req:
            return redirect('req_list')
        is_own = req['requester_id'] == actor['people_id']
        can_view = actor['full_access'] or is_own or (
            actor['is_manager'] and req['dept_id'] == actor['dept_id'])
        if not can_view:
            return redirect('req_list')

        can_edit = is_own and req['status'] == 'draft' \
            and request.session.get('user_role') not in READ_ONLY_ROLES
        can_decide = req_can_authorize(
            actor['role'], req['status'], req['dept_id'], actor['dept_id'], is_own)

        if request.method == 'POST':
            action = request.POST.get('action')
            try:
                if action == 'add_item' and can_edit:
                    add_requisition_item(
                        conn, req_id,
                        description=request.POST.get('description', ''),
                        qty=int(request.POST.get('qty', 1) or 1),
                        est_unit_price=float(request.POST.get('est_unit_price', 0) or 0),
                    )
                    conn.commit()
                    return redirect('req_detail', req_id=req_id)
                elif action == 'submit' and can_edit:
                    submit_requisition(conn, req_id)
                    conn.commit()
                    return redirect('req_detail', req_id=req_id)
                elif action == 'decide' and can_decide:
                    decision = request.POST.get('decision')
                    if decision in ('approve', 'deny'):
                        decide_requisition(
                            conn, req_id, decision, actor['people_id'],
                            request.POST.get('comment', ''),
                        )
                        conn.commit()
                        return redirect('req_detail', req_id=req_id)
            except Exception as e:
                conn.rollback()
                error = str(e)

        req = get_purchase_req(conn, req_id)
        items = list_requisition_items(conn, req_id)
        approvals = list_requisition_approvals(conn, req_id)
    finally:
        conn.close()
    return render(request, 'req_detail.html', _purch_ctx(
        request, req=req, items=items, approvals=approvals,
        can_edit=can_edit, can_decide=can_decide, error=error,
    ))


# ---------------------------------------------------------------------------
# Personnel dashboard
# ---------------------------------------------------------------------------

@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def pers_dashboard(request):
    with get_db_connection() as conn:
        ensure_workforce_columns(conn)
        data = get_personnel_dashboard(conn)
        hire_trend = conn.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', hire_date::date), 'YYYY-MM')
                       AS month,
                   COUNT(*) AS count
            FROM people
            WHERE hire_date IS NOT NULL
              AND hire_date >= (CURRENT_DATE - INTERVAL '12 months')::text
            GROUP BY DATE_TRUNC('month', hire_date::date)
            ORDER BY DATE_TRUNC('month', hire_date::date)
        """).fetchall()
        time_off_status = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM time_off_request
            GROUP BY status
        """).fetchall()
        training_status = conn.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM pers_training
            GROUP BY status
        """).fetchall()
        review_ratings = conn.execute("""
            SELECT rating::text AS rating, COUNT(*) AS cnt
            FROM pers_review
            WHERE rating IS NOT NULL
            GROUP BY rating ORDER BY rating
        """).fetchall()
        payroll_by_month = conn.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', pr.run_date::date), 'Mon YYYY') AS month,
                   COALESCE(SUM(pe.gross_pay), 0)::float AS gross
            FROM payroll_run pr
            JOIN payroll_entry pe ON pe.run_id = pr.id
            WHERE pr.run_date >= (CURRENT_DATE - INTERVAL '6 months')::text
            GROUP BY DATE_TRUNC('month', pr.run_date::date)
            ORDER BY DATE_TRUNC('month', pr.run_date::date)
        """).fetchall()
    ctx = _people_context(
        request, **data,
        dept_chart_json=json.dumps(data.get('by_dept', [])),
        hire_trend_json=json.dumps([dict(r) for r in hire_trend]),
        time_off_status_json=json.dumps([dict(r) for r in time_off_status]),
        training_status_json=json.dumps([dict(r) for r in training_status]),
        review_ratings_json=json.dumps([dict(r) for r in review_ratings]),
        payroll_by_month_json=json.dumps([dict(r) for r in payroll_by_month]),
    )
    return render(request, 'personnel_dashboard.html', ctx)


@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def pers_depts(request):
    can_edit = _is_hr(request)
    error = success = None
    conn = get_db_connection()
    try:
        depts = load_depts(conn)
        dept_subs = list_dept_subs_with_dept(conn)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action == 'new_dept':
                    create_dept(conn, request.POST.get('dept_name', ''))
                    conn.commit()
                    return redirect('pers_depts')
                elif action == 'edit_dept':
                    dept_id = int(request.POST.get('dept_id', 0))
                    update_dept(conn, dept_id, request.POST.get('dept_name', ''))
                    conn.commit()
                    return redirect('pers_depts')
                elif action == 'new_sub':
                    dept_id = int(request.POST.get('dept_id', 0))
                    create_dept_sub(conn, dept_id, request.POST.get('dept_sub_name', ''))
                    conn.commit()
                    return redirect('pers_depts')
                elif action == 'edit_sub':
                    sub_id = int(request.POST.get('dept_sub_id', 0))
                    dept_id = int(request.POST.get('dept_id', 0))
                    update_dept_sub(conn, sub_id, dept_id, request.POST.get('dept_sub_name', ''))
                    conn.commit()
                    return redirect('pers_depts')
            except Exception as e:
                conn.rollback()
                error = str(e)
                depts = load_depts(conn)
                dept_subs = list_dept_subs_with_dept(conn)
    finally:
        conn.close()
    return render(request, 'pers_depts.html', _people_context(
        request, depts=depts, dept_subs=dept_subs,
        can_edit=can_edit, error=error, success=success,
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def pers_reviews_list(request):
    can_edit = _is_hr(request)
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_review_table(conn)
        conn.commit()
        reviews = list_reviews(conn, status=status_f or None, search=search or None)
        people = list_people(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            try:
                rid = create_review(
                    conn,
                    people_id=int(request.POST.get('people_id', 0)),
                    review_type=request.POST.get('review_type', 'Annual'),
                    review_date=request.POST.get('review_date', ''),
                    reviewer=request.POST.get('reviewer', '').strip(),
                    rating=request.POST.get('rating', ''),
                    status=request.POST.get('status', 'Scheduled'),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('pers_review_detail', review_id=rid)
            except Exception as e:
                conn.rollback()
                error = str(e)
                reviews = list_reviews(conn, status=status_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'performance_reviews', [
            ('first_name', 'First Name'), ('last_name', 'Last Name'),
            ('reviewer', 'Reviewer'), ('review_type', 'Type'),
            ('review_date', 'Review Date'), ('rating', 'Rating'), ('status', 'Status'),
        ], reviews)

    return render(request, 'pers_reviews_list.html', _people_context(
        request, reviews=reviews, people=people,
        status_filter=status_f, search=search,
        REVIEW_STATUSES=REVIEW_STATUSES, REVIEW_TYPES=REVIEW_TYPES, REVIEW_RATINGS=REVIEW_RATINGS,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def pers_review_detail(request, review_id):
    can_edit = _is_hr(request)
    error = success = None
    conn = get_db_connection()
    try:
        review = get_review(conn, review_id)
        if not review:
            return redirect('pers_reviews_list')
        if request.method == 'POST' and can_edit:
            try:
                update_review(
                    conn, review_id,
                    review_type=request.POST.get('review_type', ''),
                    review_date=request.POST.get('review_date', ''),
                    reviewer=request.POST.get('reviewer', '').strip(),
                    rating=request.POST.get('rating', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Review updated.'
                review = get_review(conn, review_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'pers_review_detail.html', _people_context(
        request, review=review, can_edit=can_edit,
        REVIEW_STATUSES=REVIEW_STATUSES, REVIEW_TYPES=REVIEW_TYPES, REVIEW_RATINGS=REVIEW_RATINGS,
        error=error, success=success,
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def pers_training_list(request):
    can_edit = _is_hr(request)
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_training_table(conn)
        conn.commit()
        trainings = list_trainings(
            conn, status=status_f or None,
            training_type=type_f or None, search=search or None,
        )
        people = list_people(conn) if can_edit else []
        if request.method == 'POST' and can_edit:
            try:
                tid = create_training(
                    conn,
                    people_id=int(request.POST.get('people_id', 0)),
                    course_name=request.POST.get('course_name', ''),
                    training_type=request.POST.get('training_type', 'Other'),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    status=request.POST.get('status', 'Scheduled'),
                    notes=request.POST.get('notes', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('pers_training_detail', training_id=tid)
            except Exception as e:
                conn.rollback()
                error = str(e)
                trainings = list_trainings(
                    conn, status=status_f or None,
                    training_type=type_f or None, search=search or None,
                )
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'training_records', [
            ('course_name', 'Course'), ('first_name', 'First Name'), ('last_name', 'Last Name'),
            ('training_type', 'Type'), ('start_date', 'Start Date'),
            ('end_date', 'End Date'), ('status', 'Status'),
        ], trainings)

    return render(request, 'pers_training_list.html', _people_context(
        request, trainings=trainings, people=people,
        status_filter=status_f, type_filter=type_f, search=search,
        TRAINING_STATUSES=TRAINING_STATUSES, TRAINING_TYPES=TRAINING_TYPES,
        error=error, success=success, can_edit=can_edit,
    ))


@dept_required('personnel', role_keys=_PERSONNEL_ROLES)
def pers_training_detail(request, training_id):
    can_edit = _is_hr(request)
    error = success = None
    conn = get_db_connection()
    try:
        training = get_training(conn, training_id)
        if not training:
            return redirect('pers_training_list')
        if request.method == 'POST' and can_edit:
            try:
                update_training(
                    conn, training_id,
                    course_name=request.POST.get('course_name', ''),
                    training_type=request.POST.get('training_type', ''),
                    start_date=request.POST.get('start_date', ''),
                    end_date=request.POST.get('end_date', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', '').strip(),
                )
                conn.commit()
                success = 'Training record updated.'
                training = get_training(conn, training_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'pers_training_detail.html', _people_context(
        request, training=training, can_edit=can_edit,
        TRAINING_STATUSES=TRAINING_STATUSES, TRAINING_TYPES=TRAINING_TYPES,
        error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Customer Service dashboard
# ---------------------------------------------------------------------------

@dept_required(_CS_DEPT_KEYS)
def cs_dashboard_view(request):
    with get_db_connection() as conn:
        stats = get_summary_stats(conn)
        recent_tickets = list_tickets(conn)[:8]

        ticket_trend_rows = conn.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', call_date::date), 'Mon YYYY') AS month,
                   COUNT(*) AS total,
                   SUM(CASE WHEN completion_box = 0 THEN 1 ELSE 0 END) AS open_cnt,
                   SUM(CASE WHEN completion_box = 1 THEN 1 ELSE 0 END) AS closed_cnt
            FROM calls2
            WHERE call_date::date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', call_date::date)
            ORDER BY DATE_TRUNC('month', call_date::date)
        """).fetchall()
        ticket_trend_json = json.dumps([dict(r) for r in ticket_trend_rows])

        return_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM cs_return GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        return_status_json = json.dumps([dict(r) for r in return_status_rows])

        return_reason_rows = conn.execute("""
            SELECT reason, COUNT(*) AS cnt
            FROM cs_return
            WHERE reason IS NOT NULL AND reason != ''
            GROUP BY reason ORDER BY cnt DESC LIMIT 8
        """).fetchall()
        return_reason_json = json.dumps([dict(r) for r in return_reason_rows])

        survey_score_rows = conn.execute("""
            SELECT score, COUNT(*) AS cnt
            FROM cs_survey_response
            WHERE score IS NOT NULL
            GROUP BY score ORDER BY score
        """).fetchall()
        survey_score_json = json.dumps([dict(r) for r in survey_score_rows])

        kb_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM cs_kb_article GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        kb_status_json = json.dumps([dict(r) for r in kb_status_rows])

        open_closed_json = json.dumps([
            {'label': 'Open', 'cnt': stats.get('open_count', 0)},
            {'label': 'Closed', 'cnt': stats.get('completed_count', 0)},
        ])

    ctx = _cs_context(request, stats=stats, recent_tickets=recent_tickets,
                      ticket_trend_json=ticket_trend_json,
                      return_status_json=return_status_json,
                      return_reason_json=return_reason_json,
                      survey_score_json=survey_score_json,
                      kb_status_json=kb_status_json,
                      open_closed_json=open_closed_json)
    return render(request, 'cs_dashboard.html', ctx)


# ---------------------------------------------------------------------------
# Finance dashboard
# ---------------------------------------------------------------------------

@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_dashboard(request):
    with get_db_connection() as conn:
        data = get_finance_dashboard(conn)
        ar_aging = get_ar_aging(conn)
        rev_expense = get_revenue_expense_by_month(conn)
        cash_position = get_cash_position(conn)
        cash_forecast = get_cash_forecast_13wk(conn, starting_balance=cash_position)
        top_ar_customers = get_top_ar_customers(conn)
        invoice_status_mix = get_invoice_status_mix(conn)
        ap_aging_row = conn.execute("""
            SELECT
                COALESCE(SUM(amount) FILTER (
                    WHERE due_date::date >= CURRENT_DATE), 0) AS current,
                COALESCE(SUM(amount) FILTER (
                    WHERE due_date::date < CURRENT_DATE
                      AND due_date::date >= CURRENT_DATE - INTERVAL '30 days'), 0) AS d1_30,
                COALESCE(SUM(amount) FILTER (
                    WHERE due_date::date < CURRENT_DATE - INTERVAL '30 days'
                      AND due_date::date >= CURRENT_DATE - INTERVAL '60 days'), 0) AS d31_60,
                COALESCE(SUM(amount) FILTER (
                    WHERE due_date::date < CURRENT_DATE - INTERVAL '60 days'
                      AND due_date::date >= CURRENT_DATE - INTERVAL '90 days'), 0) AS d61_90,
                COALESCE(SUM(amount) FILTER (
                    WHERE due_date::date < CURRENT_DATE - INTERVAL '90 days'), 0) AS over_90
            FROM ap_invoice WHERE status IN ('open','partial','overdue')
        """).fetchone()
        ap_aging = dict(ap_aging_row) if ap_aging_row else {}
    ctx = _acct_ctx(
        request, **data,
        ar_aging_json=json.dumps(ar_aging['totals']),
        ap_aging_json=json.dumps(ap_aging),
        rev_expense_json=json.dumps(rev_expense),
        cash_forecast_json=json.dumps(cash_forecast),
        top_ar_customers_json=json.dumps(top_ar_customers),
        invoice_status_mix_json=json.dumps(invoice_status_mix),
        cash_position=cash_position,
        cash_forecast_end=cash_forecast[-1]['projected_balance'],
        cash_forecast_net_change=cash_forecast[-1]['projected_balance'] - cash_position,
    )
    return render(request, 'finance_dashboard.html', ctx)


# ---------------------------------------------------------------------------
# Finance sub-pages — budgets, audits, bank rec, tax
# ---------------------------------------------------------------------------

def _fin_ctx(request, **extra):
    role = request.session.get('user_role', '')
    ctx = {
        'user_email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


# ── Budgets ──────────────────────────────────────────────────────────────────

# Maintenance's own budget leaves (Budget Requests, Budget vs. Actual,
# Maintenance Budget) route here too, since there's no maintenance-specific
# budget table — only this one view (not the other Finance sub-pages that
# share _ACCOUNTING_DEPT_KEYS) grants that extra department access.
@dept_required(_ACCOUNTING_DEPT_KEYS | {'maintenance'})
def fin_budget_list(request):
    status_f = request.GET.get('status', '').strip()
    year_f = request.GET.get('fiscal_year', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        budgets = list_budgets(
            conn,
            status=status_f or None,
            fiscal_year=int(year_f) if year_f.isdigit() else None,
            search=search or None,
        )
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_budget(
                    conn,
                    budget_name=request.POST.get('budget_name', ''),
                    fiscal_year=int(request.POST.get('fiscal_year') or 0),
                    status=request.POST.get('status', 'draft'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('fin_budget_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                budgets = list_budgets(conn, status=status_f or None,
                                       fiscal_year=int(year_f) if year_f.isdigit() else None,
                                       search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'budgets', [
            ('budget_name', 'Budget Name'), ('fiscal_year', 'Fiscal Year'),
            ('status', 'Status'), ('notes', 'Notes'),
        ], budgets)

    return render(request, 'finance_budget_list.html', _fin_ctx(
        request, budgets=budgets, status_filter=status_f, year_filter=year_f,
        search=search, budget_statuses=BUDGET_STATUSES, error=error, success=success,
    ))


@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_budget_detail(request, budget_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        budget = get_budget(conn, budget_id)
        if not budget:
            return redirect('fin_budget_list')
        action = request.POST.get('action', 'update') if request.method == 'POST' else None
        if action == 'update' and can_edit:
            try:
                update_budget(
                    conn, budget_id,
                    budget_name=request.POST.get('budget_name', ''),
                    fiscal_year=int(request.POST.get('fiscal_year') or budget['fiscal_year']),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Budget updated.'
                budget = get_budget(conn, budget_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        elif action == 'add_line' and can_edit:
            try:
                create_budget_line(
                    conn, budget_id,
                    category=request.POST.get('category', ''),
                    description=request.POST.get('description', ''),
                    budgeted_amount=float(request.POST.get('budgeted_amount') or 0),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('fin_budget_detail', budget_id=budget_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        elif action == 'del_line' and can_edit:
            try:
                delete_budget_line(conn, int(request.POST.get('line_id', 0)))
                conn.commit()
                return redirect('fin_budget_detail', budget_id=budget_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        lines = get_budget_lines(conn, budget_id)
        total_budgeted = sum(ln['budgeted_amount'] or 0 for ln in lines)
    finally:
        conn.close()
    return render(request, 'finance_budget_detail.html', _fin_ctx(
        request, budget=budget, lines=lines, total_budgeted=total_budgeted,
        can_edit=can_edit, budget_statuses=BUDGET_STATUSES,
        error=error, success=success,
    ))


# ── Audits ───────────────────────────────────────────────────────────────────

@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_audit_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('audit_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        audits = list_fin_audits(conn, status=status_f or None,
                                 audit_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_fin_audit(
                    conn,
                    audit_name=request.POST.get('audit_name', ''),
                    audit_type=request.POST.get('audit_type', ''),
                    department=request.POST.get('department', ''),
                    auditor=request.POST.get('auditor', ''),
                    scheduled=request.POST.get('scheduled', ''),
                    status=request.POST.get('status', 'Scheduled'),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('fin_audit_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                audits = list_fin_audits(conn, status=status_f or None,
                                         audit_type=type_f or None, search=search or None)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'fin_audits', [
            ('audit_name', 'Audit Name'), ('audit_type', 'Type'), ('department', 'Department'),
            ('auditor', 'Auditor'), ('scheduled', 'Scheduled Date'), ('status', 'Status'),
        ], audits)

    return render(request, 'finance_audit_list.html', _fin_ctx(
        request, audits=audits, status_filter=status_f, type_filter=type_f,
        search=search, audit_statuses=FIN_AUDIT_STATUSES, audit_types=FIN_AUDIT_TYPES,
        error=error, success=success,
    ))


@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_audit_detail(request, audit_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        audit = get_audit_record(conn, audit_id)
        if not audit:
            return redirect('fin_audit_list')
        action = request.POST.get('action', 'update') if request.method == 'POST' else None
        if action == 'update' and can_edit:
            try:
                update_audit_record(
                    conn, audit_id,
                    audit_name=request.POST.get('audit_name', ''),
                    audit_type=request.POST.get('audit_type', ''),
                    department=request.POST.get('department', ''),
                    auditor=request.POST.get('auditor', ''),
                    scheduled=request.POST.get('scheduled', '') or None,
                    completed=request.POST.get('completed', '') or None,
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Audit updated.'
                audit = get_audit_record(conn, audit_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        elif action == 'add_finding' and can_edit:
            try:
                create_audit_finding(
                    conn, audit_id,
                    finding_ref=request.POST.get('finding_ref', ''),
                    description=request.POST.get('description', ''),
                    severity=request.POST.get('severity', 'Minor'),
                    department=request.POST.get('department', ''),
                    found_date=request.POST.get('found_date', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('fin_audit_detail', audit_id=audit_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        findings = get_audit_findings(conn, audit_id)
    finally:
        conn.close()
    return render(request, 'finance_audit_detail.html', _fin_ctx(
        request, audit=audit, findings=findings, can_edit=can_edit,
        audit_statuses=FIN_AUDIT_STATUSES, audit_types=FIN_AUDIT_TYPES,
        finding_severities=FINDING_SEVERITIES,
        error=error, success=success,
    ))


# ── Bank Reconciliation ──────────────────────────────────────────────────────

@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_bank_rec_list(request):
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        accounts = list_bank_accounts(conn, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_bank_account(
                    conn,
                    account_name=request.POST.get('account_name', ''),
                    bank_name=request.POST.get('bank_name', ''),
                    account_number=request.POST.get('account_number', ''),
                    routing_number=request.POST.get('routing_number', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('fin_bank_rec_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                accounts = list_bank_accounts(conn, search=search or None)
    finally:
        conn.close()
    return render(request, 'finance_bank_rec_list.html', _fin_ctx(
        request, accounts=accounts, search=search, error=error, success=success,
    ))


@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_bank_rec_detail(request, account_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        account = get_bank_account(conn, account_id)
        if not account:
            return redirect('fin_bank_rec_list')
        action = request.POST.get('action', 'update') if request.method == 'POST' else None
        if action == 'update' and can_edit:
            try:
                update_bank_account(
                    conn, account_id,
                    account_name=request.POST.get('account_name', ''),
                    bank_name=request.POST.get('bank_name', ''),
                    account_number=request.POST.get('account_number', ''),
                    routing_number=request.POST.get('routing_number', ''),
                    is_active=int(request.POST.get('is_active', 1)),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Account updated.'
                account = get_bank_account(conn, account_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        elif action == 'add_statement' and can_edit:
            try:
                conn.execute(
                    "INSERT INTO bank_statement "
                    "(bank_account_id, statement_date, beginning_balance, ending_balance, status, notes) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (account_id,
                     request.POST.get('statement_date', ''),
                     float(request.POST.get('beginning_balance') or 0),
                     float(request.POST.get('ending_balance') or 0),
                     request.POST.get('status', 'Open'),
                     request.POST.get('notes', '')),
                )
                conn.commit()
                return redirect('fin_bank_rec_detail', account_id=account_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
        statements = list_bank_statements(conn, account_id)
    finally:
        conn.close()
    return render(request, 'finance_bank_rec_detail.html', _fin_ctx(
        request, account=account, statements=statements, can_edit=can_edit,
        statement_statuses=BANK_STATEMENT_STATUSES,
        error=error, success=success,
    ))


# ── Tax Filings ──────────────────────────────────────────────────────────────

@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_tax_list(request):
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('tax_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        filings = list_tax_filings(conn, status=status_f or None,
                                   tax_type=type_f or None, search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_tax_filing(
                    conn,
                    tax_type=request.POST.get('tax_type', ''),
                    jurisdiction=request.POST.get('jurisdiction', ''),
                    period=request.POST.get('period', ''),
                    amount_due=float(request.POST.get('amount_due') or 0),
                    due_date=request.POST.get('due_date', ''),
                    status=request.POST.get('status', 'Pending'),
                    reference=request.POST.get('reference', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                return redirect('fin_tax_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                filings = list_tax_filings(conn, status=status_f or None,
                                           tax_type=type_f or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'finance_tax_list.html', _fin_ctx(
        request, filings=filings, status_filter=status_f, type_filter=type_f,
        search=search, tax_types=TAX_TYPES, tax_statuses=TAX_FILING_STATUSES,
        error=error, success=success,
    ))


@dept_required(_ACCOUNTING_DEPT_KEYS)
def fin_tax_detail(request, filing_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        filing = get_tax_filing(conn, filing_id)
        if not filing:
            return redirect('fin_tax_list')
        if request.method == 'POST' and can_edit:
            try:
                update_tax_filing(
                    conn, filing_id,
                    tax_type=request.POST.get('tax_type', ''),
                    jurisdiction=request.POST.get('jurisdiction', ''),
                    period=request.POST.get('period', ''),
                    amount_due=float(request.POST.get('amount_due') or 0),
                    amount_paid=float(request.POST.get('amount_paid') or 0),
                    filed_date=request.POST.get('filed_date', '') or None,
                    due_date=request.POST.get('due_date', '') or None,
                    status=request.POST.get('status', ''),
                    reference=request.POST.get('reference', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                success = 'Filing updated.'
                filing = get_tax_filing(conn, filing_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'finance_tax_detail.html', _fin_ctx(
        request, filing=filing, can_edit=can_edit,
        tax_types=TAX_TYPES, tax_statuses=TAX_FILING_STATUSES,
        error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Accounting dashboard
# ---------------------------------------------------------------------------

@dept_required(_ACCOUNTING_DEPT_KEYS)
def acct_dashboard(request):
    """Accounting department landing page — AP, AR, and GL summary."""
    conn = get_db_connection()
    try:
        ap = get_ap_dashboard(conn)
        ar = get_ar_dashboard(conn)
        recent_journals = conn.execute(
            "SELECT j.id, j.journal_date, j.reference, j.description, j.posted, "
            "COUNT(jl.id) AS line_count, "
            "COALESCE(SUM(jl.debit), 0) AS total_debit "
            "FROM gl_journal j "
            "LEFT JOIN gl_journal_line jl ON jl.journal_id = j.id "
            "GROUP BY j.id "
            "ORDER BY j.journal_date DESC, j.id DESC LIMIT 8"
        ).fetchall()
        recent_journals = [dict(r) for r in recent_journals]

        ap_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM ap_invoice GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        ap_status_json = json.dumps([dict(r) for r in ap_status_rows])

        ar_status_rows = conn.execute("""
            SELECT status, COUNT(*) AS cnt FROM ar_invoice GROUP BY status ORDER BY cnt DESC
        """).fetchall()
        ar_status_json = json.dumps([dict(r) for r in ar_status_rows])

        top_vendors_rows = conn.execute("""
            SELECT COALESCE(NULLIF(s.company_name, ''), s.first_name || ' ' || s.last_name) AS name,
                   SUM(i.amount) AS total_outstanding
            FROM ap_invoice i
            JOIN supplier s ON s.id = i.vendor_id
            WHERE i.status IN ('open', 'partial', 'overdue')
            GROUP BY s.id, name ORDER BY total_outstanding DESC LIMIT 8
        """).fetchall()
        top_vendors_json = json.dumps([dict(r) for r in top_vendors_rows])

        top_customers_rows = conn.execute("""
            SELECT COALESCE(NULLIF(c.company_name, ''), c.first_name || ' ' || c.last_name) AS name,
                   SUM(i.amount) AS total_outstanding
            FROM ar_invoice i
            JOIN customer c ON c.id = i.customer_id
            WHERE i.status IN ('open', 'partial', 'overdue')
            GROUP BY c.id, name ORDER BY total_outstanding DESC LIMIT 8
        """).fetchall()
        top_customers_json = json.dumps([dict(r) for r in top_customers_rows])

        journal_trend_rows = conn.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', j.journal_date::date), 'Mon YYYY') AS month,
                   COUNT(*) AS cnt
            FROM gl_journal j
            WHERE j.journal_date::date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', j.journal_date::date)
            ORDER BY DATE_TRUNC('month', j.journal_date::date)
        """).fetchall()
        journal_trend_json = json.dumps([dict(r) for r in journal_trend_rows])

        journal_posted_rows = conn.execute("""
            SELECT CASE WHEN posted = 1 THEN 'Posted' ELSE 'Draft' END AS label, COUNT(*) AS cnt
            FROM gl_journal GROUP BY label ORDER BY cnt DESC
        """).fetchall()
        journal_posted_json = json.dumps([dict(r) for r in journal_posted_rows])
    finally:
        conn.close()
    return render(request, 'acct_dashboard.html', _acct_ctx(
        request, ap=ap, ar=ar, recent_journals=recent_journals,
        ap_status_json=ap_status_json,
        ar_status_json=ar_status_json,
        top_vendors_json=top_vendors_json,
        top_customers_json=top_customers_json,
        journal_trend_json=journal_trend_json,
        journal_posted_json=journal_posted_json,
    ))


# ---------------------------------------------------------------------------
# Sales — Territory Management
# ---------------------------------------------------------------------------

@dept_required(_SALES_DEPT_KEYS)
def sales_territories(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_sales_territory_table(conn)
        conn.commit()
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'new')
            try:
                if action == 'update':
                    update_territory(
                        conn,
                        territory_id=int(request.POST.get('territory_id', 0)),
                        name=request.POST.get('name', '').strip(),
                        region=request.POST.get('region', '').strip(),
                        assigned_rep=request.POST.get('assigned_rep', '').strip(),
                        status=request.POST.get('status', 'Active'),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Territory updated.'
                else:
                    create_territory(
                        conn,
                        name=request.POST.get('name', '').strip(),
                        region=request.POST.get('region', '').strip(),
                        assigned_rep=request.POST.get('assigned_rep', '').strip(),
                        status=request.POST.get('status', 'Active'),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Territory created.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        territories = list_territories(conn, status=status_f or None,
                                       search=search or None)
    finally:
        conn.close()
    return render(request, 'sales_territories.html', _sales_ctx(
        request,
        territories=territories,
        status_filter=status_f,
        search=search,
        TERRITORY_STATUSES=TERRITORY_STATUSES,
        can_edit=can_edit,
        error=error,
        success=success,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_territory_performance(request):
    conn = get_db_connection()
    try:
        init_sales_territory_table(conn)
        conn.commit()
        territories = get_territory_performance(conn)
    finally:
        conn.close()
    return render(request, 'sales_territory_performance.html', _sales_ctx(
        request, territories=territories,
    ))


# ---------------------------------------------------------------------------
# Sales — Commission Tracking
# ---------------------------------------------------------------------------

@dept_required(_SALES_DEPT_KEYS)
def sales_commissions(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    rep_f = request.GET.get('rep', '').strip()
    period_f = request.GET.get('period', '').strip()
    status_f = request.GET.get('status', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_commission_tables(conn)
        conn.commit()
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'new')
            try:
                plan_id_raw = request.POST.get('plan_id', '') or None
                plan_id = int(plan_id_raw) if plan_id_raw else None
                if action == 'update':
                    update_commission(
                        conn,
                        commission_id=int(request.POST.get('commission_id', 0)),
                        rep=request.POST.get('rep', '').strip(),
                        period=request.POST.get('period', '').strip(),
                        plan_id=plan_id,
                        sale_amount=float(request.POST.get('sale_amount') or 0),
                        commission=float(request.POST.get('commission') or 0),
                        status=request.POST.get('status', 'Pending'),
                        notes=request.POST.get('notes', '').strip(),
                    )
                    conn.commit()
                    success = 'Commission record updated.'
                else:
                    create_commission(
                        conn,
                        rep=request.POST.get('rep', '').strip(),
                        period=request.POST.get('period', '').strip(),
                        plan_id=plan_id,
                        sale_amount=float(request.POST.get('sale_amount') or 0),
                        commission=float(request.POST.get('commission') or 0),
                        status=request.POST.get('status', 'Pending'),
                        notes=request.POST.get('notes', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Commission record added.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        commissions = list_commissions(
            conn,
            rep=rep_f or None,
            period=period_f or None,
            status=status_f or None,
        )
        summary = get_commission_summary(conn)
        plans = list_commission_plans(conn, active_only=True)
        periods = conn.execute(
            "SELECT DISTINCT period FROM sales_commission"
            " ORDER BY period DESC"
        ).fetchall()
    finally:
        conn.close()
    return render(request, 'sales_commissions.html', _sales_ctx(
        request,
        commissions=commissions,
        summary=summary,
        plans=plans,
        periods=[r['period'] for r in periods],
        rep_filter=rep_f,
        period_filter=period_f,
        status_filter=status_f,
        COMMISSION_STATUSES=COMMISSION_STATUSES,
        can_edit=can_edit,
        error=error,
        success=success,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_commission_history(request):
    """Payment history view — shows only Paid commissions."""
    rep_f = request.GET.get('rep', '').strip()
    period_f = request.GET.get('period', '').strip()
    conn = get_db_connection()
    try:
        init_commission_tables(conn)
        conn.commit()
        paid = list_commissions(conn, rep=rep_f or None,
                                period=period_f or None, status='Paid')
        periods = conn.execute(
            "SELECT DISTINCT period FROM sales_commission"
            " WHERE status='Paid' ORDER BY period DESC"
        ).fetchall()
    finally:
        conn.close()
    return render(request, 'sales_commission_history.html', _sales_ctx(
        request,
        paid=paid,
        periods=[r['period'] for r in periods],
        rep_filter=rep_f,
        period_filter=period_f,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_commission_plans(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        init_commission_tables(conn)
        conn.commit()
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'new')
            try:
                if action == 'update':
                    update_commission_plan(
                        conn,
                        plan_id=int(request.POST.get('plan_id', 0)),
                        name=request.POST.get('name', '').strip(),
                        plan_type=request.POST.get('plan_type', 'Flat Rate'),
                        rate=float(request.POST.get('rate') or 0),
                        description=request.POST.get('description', '').strip(),
                        active=request.POST.get('active') == 'on',
                    )
                    conn.commit()
                    success = 'Plan updated.'
                else:
                    create_commission_plan(
                        conn,
                        name=request.POST.get('name', '').strip(),
                        plan_type=request.POST.get('plan_type', 'Flat Rate'),
                        rate=float(request.POST.get('rate') or 0),
                        description=request.POST.get('description', '').strip(),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    success = 'Plan created.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        plans = list_commission_plans(conn)
    finally:
        conn.close()
    return render(request, 'sales_commission_plans.html', _sales_ctx(
        request,
        plans=plans,
        COMMISSION_PLAN_TYPES=COMMISSION_PLAN_TYPES,
        can_edit=can_edit,
        error=error,
        success=success,
    ))


# ---------------------------------------------------------------------------
# Sales — Staff Performance
# ---------------------------------------------------------------------------

@dept_required(_SALES_DEPT_KEYS)
def sales_performance(request):
    conn = get_db_connection()
    try:
        data = get_sales_performance(conn)
    finally:
        conn.close()
    return render(request, 'sales_performance.html', _sales_ctx(
        request, **data,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_performance_reviews(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    rep_f = request.GET.get('rep', '').strip()
    status_f = request.GET.get('status', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_sales_performance_tables(conn)
        conn.commit()
        if request.method == 'POST' and can_edit:
            try:
                create_perf_review(
                    conn,
                    rep=request.POST.get('rep', '').strip(),
                    review_date=request.POST.get('review_date', '').strip(),
                    period=request.POST.get('period', '').strip(),
                    rating=request.POST.get('rating', '').strip(),
                    strengths=request.POST.get('strengths', '').strip(),
                    improvements=request.POST.get('improvements', '').strip(),
                    goals=request.POST.get('goals', '').strip(),
                    status=request.POST.get('status', 'Scheduled'),
                    reviewer=request.POST.get('reviewer', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Review scheduled.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        reviews = list_perf_reviews(conn, rep=rep_f or None,
                                    status=status_f or None)
    finally:
        conn.close()
    return render(request, 'sales_performance_reviews.html', _sales_ctx(
        request,
        reviews=reviews,
        rep_filter=rep_f,
        status_filter=status_f,
        PERF_REVIEW_STATUSES=PERF_REVIEW_STATUSES,
        can_edit=can_edit,
        error=error,
        success=success,
    ))


@dept_required(_SALES_DEPT_KEYS)
def sales_coaching(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    rep_f = request.GET.get('rep', '').strip()
    status_f = request.GET.get('status', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_sales_performance_tables(conn)
        conn.commit()
        if request.method == 'POST' and can_edit:
            try:
                create_coaching_note(
                    conn,
                    rep=request.POST.get('rep', '').strip(),
                    subject=request.POST.get('subject', '').strip(),
                    note=request.POST.get('note', '').strip(),
                    status=request.POST.get('status', 'Open'),
                    coach=request.POST.get('coach', '').strip(),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'Coaching note added.'
            except Exception as e:
                conn.rollback()
                error = str(e)
        notes = list_coaching_notes(conn, rep=rep_f or None,
                                    status=status_f or None)
    finally:
        conn.close()
    return render(request, 'sales_coaching.html', _sales_ctx(
        request,
        notes=notes,
        rep_filter=rep_f,
        status_filter=status_f,
        COACHING_NOTE_STATUSES=COACHING_NOTE_STATUSES,
        can_edit=can_edit,
        error=error,
        success=success,
    ))


# =============================================================================
# Lot tracking  (7A)
# =============================================================================

_LOT_DEPT_KEYS = {'production', 'quality', 'inventory', 'warehouse'}


def _lot_ctx(request, **kw):
    return dict(
        user_role=request.session.get('user_role', ''),
        user_dept_name=request.session.get('user_dept_name', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        **kw,
    )


@login_required
def lot_list(request):
    status_filter = request.GET.get('status') or None
    product_id = _int_or_none(request.GET.get('product_id'))
    conn = get_db_connection()
    try:
        lot_core.ensure_lot_tables(conn)
        lots = lot_core.list_lots(conn, product_id=product_id, status=status_filter)
        expiry_alerts = lot_core.get_expiry_alerts(conn, days_ahead=30)
        products = inv_list_products(conn)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'lots', [
            ('lot_number', 'Lot Number'), ('product_name', 'Product'),
            ('qty', 'Quantity'), ('status', 'Status'),
            ('received_date', 'Received Date'), ('expiry_date', 'Expiry Date'),
        ], lots)

    return render(request, 'lot_list.html', _lot_ctx(
        request,
        lots=lots,
        expiry_alerts=expiry_alerts,
        products=products,
        status_filter=status_filter,
        product_id=product_id,
        LOT_STATUSES=lot_core.LOT_STATUSES,
    ))


@login_required
def lot_detail(request, lot_id):
    conn = get_db_connection()
    error = success = None
    try:
        lot_core.ensure_lot_tables(conn)
        lot = lot_core.get_lot(conn, lot_id)
        if not lot:
            return redirect('lot_list')
        genealogy = lot_core.get_lot_genealogy(conn, lot_id)
        serials = lot_core.list_serials(conn, lot_id=lot_id)
        if request.method == 'POST':
            action = request.POST.get('action', '')
            if action == 'status':
                new_status = request.POST.get('status', '')
                try:
                    lot_core.update_lot_status(conn, lot_id, new_status,
                                               notes=request.POST.get('notes', ''))
                    conn.commit()
                    lot = lot_core.get_lot(conn, lot_id)
                    success = f'Status updated to {new_status}.'
                except ValueError as exc:
                    conn.rollback()
                    error = str(exc)
            elif action == 'add_serial':
                sn = request.POST.get('serial_number', '').strip()
                if sn:
                    try:
                        lot_core.create_serial(conn, sn, lot['product_id'],
                                               lot_id=lot_id,
                                               created_by=request.session.get('user_email', ''))
                        conn.commit()
                        serials = lot_core.list_serials(conn, lot_id=lot_id)
                        success = f'Serial {sn} added.'
                    except Exception as exc:
                        conn.rollback()
                        error = str(exc)
    finally:
        conn.close()
    return render(request, 'lot_detail.html', _lot_ctx(
        request,
        lot=lot,
        genealogy=genealogy,
        serials=serials,
        error=error,
        success=success,
        LOT_STATUSES=lot_core.LOT_STATUSES,
        SERIAL_STATUSES=lot_core.SERIAL_STATUSES,
    ))


@login_required
def lot_new(request):
    conn = get_db_connection()
    error = None
    try:
        lot_core.ensure_lot_tables(conn)
        products = inv_list_products(conn)
        if request.method == 'POST':
            product_id = _int_or_none(request.POST.get('product_id'))
            qty = request.POST.get('qty', '').strip()
            if not product_id or not qty:
                error = 'Product and quantity are required.'
            else:
                try:
                    lot_id = lot_core.create_lot(
                        conn,
                        product_id=product_id,
                        qty=float(qty),
                        received_date=request.POST.get('received_date') or None,
                        expiry_date=request.POST.get('expiry_date') or None,
                        lot_number=request.POST.get('lot_number') or None,
                        notes=request.POST.get('notes', ''),
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    return redirect('lot_detail', lot_id=lot_id)
                except Exception as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'lot_new.html', _lot_ctx(
        request,
        products=products,
        error=error,
        form=request.POST if request.method == 'POST' else {},
    ))


# =============================================================================
# Routing — workcenters & product routing  (7A)
# =============================================================================

_ROUTING_DEPT_KEYS = {'production', 'engineering'}


def _routing_ctx(request, **kw):
    return dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        **kw,
    )


def _workcenter_day_flags(post):
    return {
        col: post.get(col) == '1'
        for col in ('works_mon', 'works_tue', 'works_wed', 'works_thu',
                    'works_fri', 'works_sat', 'works_sun')
    }


@login_required
def workcenter_list(request):
    conn = get_db_connection()
    error = success = None
    try:
        capacity_planning_core.ensure_capacity_tables(conn)
        workcenters = capacity_planning_core.list_workcenters_with_calendar(conn)
        if request.method == 'POST':
            action = request.POST.get('action', '')
            if action == 'create':
                name = request.POST.get('name', '').strip()
                if not name:
                    error = 'Name is required.'
                else:
                    try:
                        wc_id = routing_core.create_workcenter(
                            conn,
                            name=name,
                            dept=request.POST.get('dept', ''),
                            capacity_hours_per_day=float(request.POST.get('capacity', 8) or 8),
                            labor_rate=float(request.POST.get('labor_rate', 0) or 0),
                            notes=request.POST.get('notes', ''),
                        )
                        capacity_planning_core.set_workcenter_calendar(
                            conn, wc_id, **_workcenter_day_flags(request.POST))
                        conn.commit()
                        success = f'Work center "{name}" created.'
                        workcenters = capacity_planning_core.list_workcenters_with_calendar(conn)
                    except Exception as exc:
                        conn.rollback()
                        error = str(exc)
            elif action == 'update':
                wc_id = _int_or_none(request.POST.get('wc_id'))
                if wc_id:
                    try:
                        routing_core.update_workcenter(
                            conn, wc_id,
                            name=request.POST.get('name', '').strip(),
                            dept=request.POST.get('dept', ''),
                            capacity_hours_per_day=float(request.POST.get('capacity', 8) or 8),
                            labor_rate=float(request.POST.get('labor_rate', 0) or 0),
                            notes=request.POST.get('notes', ''),
                            is_active=request.POST.get('is_active') == '1',
                        )
                        capacity_planning_core.set_workcenter_calendar(
                            conn, wc_id, **_workcenter_day_flags(request.POST))
                        conn.commit()
                        success = 'Work center updated.'
                        workcenters = capacity_planning_core.list_workcenters_with_calendar(conn)
                    except Exception as exc:
                        conn.rollback()
                        error = str(exc)
    finally:
        conn.close()

    if 'export' in request.GET:
        return export_response(request, 'workcenters', [
            ('name', 'Name'), ('dept', 'Department'),
            ('capacity_hours_per_day', 'Capacity Hours/Day'),
            ('labor_rate', 'Labor Rate'), ('is_active', 'Active'),
        ], workcenters)

    return render(request, 'workcenter_list.html', _routing_ctx(
        request,
        workcenters=workcenters,
        error=error,
        success=success,
    ))


@login_required
def workcenter_calendar(request, wc_id):
    conn = get_db_connection()
    error = success = None
    try:
        capacity_planning_core.ensure_capacity_tables(conn)
        workcenters = capacity_planning_core.list_workcenters_with_calendar(conn)
        wc = next((w for w in workcenters if w['id'] == wc_id), None)
        if not wc:
            return redirect('workcenter_list')

        can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action == 'set_days':
                    capacity_planning_core.set_workcenter_calendar(
                        conn, wc_id, **_workcenter_day_flags(request.POST))
                    conn.commit()
                    success = 'Working days updated.'
                elif action == 'add_exception':
                    exc_date = request.POST.get('exception_date', '').strip()
                    hours = float(request.POST.get('hours_available', 0) or 0)
                    notes = request.POST.get('notes', '').strip()
                    if not exc_date:
                        raise ValueError('Date is required.')
                    capacity_planning_core.set_calendar_exception(
                        conn, wc_id, exc_date, hours, notes=notes)
                    conn.commit()
                    success = 'Calendar exception saved.'
                elif action == 'remove_exception':
                    exc_id = _int_or_none(request.POST.get('exception_id'))
                    if exc_id:
                        capacity_planning_core.remove_calendar_exception(conn, exc_id)
                        conn.commit()
                        success = 'Calendar exception removed.'
            except (ValueError, TypeError) as exc:
                conn.rollback()
                error = str(exc)
            workcenters = capacity_planning_core.list_workcenters_with_calendar(conn)
            wc = next((w for w in workcenters if w['id'] == wc_id), None)

        exceptions = capacity_planning_core.list_calendar_exceptions(conn, wc_id)
    finally:
        conn.close()

    return render(request, 'workcenter_calendar.html', _routing_ctx(
        request,
        wc=wc,
        exceptions=exceptions,
        error=error,
        success=success,
    ))


@login_required
def routing_detail(request, product_id):
    conn = get_db_connection()
    error = success = None
    try:
        routing_core.ensure_routing_tables(conn)
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')
        steps = routing_core.get_routing(conn, product_id)
        workcenters = routing_core.list_workcenters(conn, active_only=True)
        if request.method == 'POST':
            action = request.POST.get('action', '')
            if action == 'add':
                op_name = request.POST.get('operation_name', '').strip()
                if not op_name:
                    error = 'Operation name is required.'
                else:
                    try:
                        seq = routing_core.next_routing_seq(conn, product_id)
                        routing_core.create_routing_step(
                            conn, product_id,
                            operation_seq=seq,
                            operation_name=op_name,
                            workcenter_id=_int_or_none(request.POST.get('workcenter_id')),
                            std_hours=float(request.POST.get('std_hours', 0) or 0),
                            notes=request.POST.get('notes', ''),
                        )
                        conn.commit()
                        success = f'Step "{op_name}" added.'
                        steps = routing_core.get_routing(conn, product_id)
                    except Exception as exc:
                        conn.rollback()
                        error = str(exc)
            elif action == 'delete':
                routing_id = _int_or_none(request.POST.get('routing_id'))
                if routing_id:
                    routing_core.delete_routing_step(conn, routing_id)
                    conn.commit()
                    success = 'Step removed.'
                    steps = routing_core.get_routing(conn, product_id)
    finally:
        conn.close()
    return render(request, 'routing_detail.html', _routing_ctx(
        request,
        product=product,
        steps=steps,
        workcenters=workcenters,
        error=error,
        success=success,
    ))


# =============================================================================
# Costing  (7A)
# =============================================================================

@login_required
def cost_detail(request, product_id):
    conn = get_db_connection()
    error = success = None
    try:
        costing_core.ensure_costing_tables(conn)
        product = inv_get_product(conn, product_id)
        if not product:
            return redirect('inventory_list')
        current_cost = costing_core.get_standard_cost(conn, product_id)
        history = costing_core.list_cost_history(conn, product_id)
        if request.method == 'POST' and request.POST.get('action') == 'roll':
            can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
            if not can_edit:
                error = 'You do not have permission to roll costs.'
            else:
                try:
                    costing_core.roll_standard_cost(
                        conn, product_id,
                        created_by=request.session.get('user_email', ''),
                    )
                    conn.commit()
                    current_cost = costing_core.get_standard_cost(conn, product_id)
                    history = costing_core.list_cost_history(conn, product_id)
                    success = 'Standard cost rolled successfully.'
                except Exception as exc:
                    conn.rollback()
                    error = str(exc)
    finally:
        conn.close()
    return render(request, 'cost_detail.html', dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        product=product,
        current_cost=current_cost,
        history=history,
        error=error,
        success=success,
    ))


@login_required
def wo_cost_detail(request, wo_id):
    conn = get_db_connection()
    error = success = None
    try:
        costing_core.ensure_costing_tables(conn)
        wo = get_wo(conn, wo_id)
        if not wo:
            return redirect('wo_list')
        cost = costing_core.get_wo_cost(conn, wo_id)
        if request.method == 'POST' and request.POST.get('action') == 'compute':
            try:
                cost = costing_core.save_wo_actual_cost(
                    conn, wo_id,
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                success = 'WO actual cost computed and saved.'
            except Exception as exc:
                conn.rollback()
                error = str(exc)
    finally:
        conn.close()
    return render(request, 'wo_cost_detail.html', dict(
        user_role=request.session.get('user_role', ''),
        full_access=request.session.get('user_full_access', False),
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        wo=wo,
        cost=cost,
        error=error,
        success=success,
    ))


# ---------------------------------------------------------------------------
# Currency Management
# ---------------------------------------------------------------------------

def currency_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        init_currency_schema(conn)
        currencies = list_currencies(conn)
        base = get_base_currency(conn)
        if request.method == 'POST' and can_edit:
            try:
                code = request.POST.get('code', '').strip().upper()
                name = request.POST.get('name', '').strip()
                symbol = request.POST.get('symbol', '').strip()
                rate = float(request.POST.get('exchange_rate') or 1.0)
                is_base = request.POST.get('is_base') == '1'
                is_active = request.POST.get('is_active', '1') == '1'
                upsert_currency(conn, code, name, symbol, rate, is_base, is_active)
                conn.commit()
                success = f'{code} saved.'
                currencies = list_currencies(conn)
                base = get_base_currency(conn)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'currency_list.html', {
        'currencies': currencies,
        'base': base,
        'common': COMMON_CURRENCIES,
        'can_edit': can_edit,
        'error': error,
        'success': success,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


# ---------------------------------------------------------------------------
# Fixed Asset Management
# ---------------------------------------------------------------------------

def fixed_asset_list(request):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_f = request.GET.get('status', '').strip()
    type_f = request.GET.get('asset_type', '').strip()
    search = request.GET.get('search', '').strip()
    error = success = None
    conn = get_db_connection()
    try:
        init_fixed_asset_tables(conn)
        assets = list_fixed_assets(conn, status=status_f or None,
                                   asset_type=type_f or None,
                                   search=search or None)
        summary = get_fixed_asset_summary(conn)
        if request.method == 'POST' and can_edit:
            try:
                asset_number = request.POST.get('asset_number', '').strip() or next_asset_number(conn)
                asset_id = create_fixed_asset(
                    conn,
                    asset_number=asset_number,
                    asset_name=request.POST.get('asset_name', ''),
                    asset_type=request.POST.get('asset_type', 'Equipment'),
                    category=request.POST.get('category', ''),
                    location=request.POST.get('location', ''),
                    department=request.POST.get('department', ''),
                    vendor=request.POST.get('vendor', ''),
                    purchase_date=request.POST.get('purchase_date', ''),
                    purchase_price=float(request.POST.get('purchase_price') or 0),
                    salvage_value=float(request.POST.get('salvage_value') or 0),
                    useful_life_years=int(request.POST.get('useful_life_years') or 5),
                    depreciation_method=request.POST.get('depreciation_method', 'Straight-Line'),
                    status=request.POST.get('status', 'Active'),
                    serial_number=request.POST.get('serial_number', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                log_fixed_asset_event(conn, asset_id, 'created',
                                      f"Asset {asset_number} created.", request.session.get('user_email', ''))
                conn.commit()
                return redirect('fixed_asset_detail', asset_id=asset_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
                assets = list_fixed_assets(conn)
                summary = get_fixed_asset_summary(conn)
    finally:
        conn.close()
    if 'export' in request.GET:
        return export_response(request, 'fixed_assets', [
            ('asset_number', 'Asset #'), ('asset_name', 'Name'), ('asset_type', 'Type'),
            ('serial_number', 'Serial #'), ('purchase_date', 'Purchase Date'),
            ('purchase_price', 'Purchase Price'), ('location', 'Location'), ('status', 'Status'),
        ], assets)

    return render(request, 'fixed_asset_list.html', {
        'assets': assets,
        'summary': summary,
        'status_filter': status_f,
        'type_filter': type_f,
        'search': search,
        'asset_statuses': FIXED_ASSET_STATUSES,
        'asset_types': FIXED_ASSET_TYPES,
        'depreciation_methods': DEPRECIATION_METHODS,
        'can_edit': can_edit,
        'error': error,
        'success': success,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })


def fixed_asset_detail(request, asset_id):
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    error = success = None
    conn = get_db_connection()
    try:
        init_fixed_asset_tables(conn)
        asset = get_fixed_asset(conn, asset_id)
        if not asset:
            return redirect('fixed_asset_list')
        events = list_fixed_asset_events(conn, asset_id)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'update':
                    update_fixed_asset(
                        conn, asset_id,
                        asset_name=request.POST.get('asset_name', ''),
                        asset_type=request.POST.get('asset_type', ''),
                        category=request.POST.get('category', ''),
                        location=request.POST.get('location', ''),
                        department=request.POST.get('department', ''),
                        vendor=request.POST.get('vendor', ''),
                        purchase_date=request.POST.get('purchase_date', ''),
                        purchase_price=float(request.POST.get('purchase_price') or 0),
                        salvage_value=float(request.POST.get('salvage_value') or 0),
                        useful_life_years=int(request.POST.get('useful_life_years') or 5),
                        depreciation_method=request.POST.get('depreciation_method', ''),
                        status=request.POST.get('status', ''),
                        serial_number=request.POST.get('serial_number', ''),
                        notes=request.POST.get('notes', ''),
                        cost_center=request.POST.get('cost_center', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        in_service_date=request.POST.get('in_service_date', ''),
                    )
                    log_fixed_asset_event(conn, asset_id, 'updated', 'Record updated.',
                                          request.session.get('user_email', ''))
                elif action == 'event':
                    note = request.POST.get('event_note', '').strip()
                    etype = request.POST.get('event_type', 'note')
                    if note:
                        log_fixed_asset_event(conn, asset_id, etype, note,
                                              request.session.get('user_email', ''))
                conn.commit()
                success = 'Saved.'
                asset = get_fixed_asset(conn, asset_id)
                events = list_fixed_asset_events(conn, asset_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()

    import datetime as _dt
    dep_schedule = []
    dep_pct = 0
    if asset and asset.get('purchase_price') and asset.get('useful_life_years'):
        price = float(asset['purchase_price'])
        salvage = float(asset.get('salvage_value') or 0)
        life = int(asset['useful_life_years'])
        method = asset.get('depreciation_method', 'Straight-Line')
        in_service = asset.get('in_service_date') or asset.get('purchase_date')
        try:
            start_year = int(str(in_service)[:4]) if in_service else _dt.date.today().year
        except Exception:
            start_year = _dt.date.today().year
        cur_year = _dt.date.today().year
        acc = 0.0
        book = price
        for i in range(life):
            yr = start_year + i
            if method == 'Declining Balance':
                annual = book * (2.0 / life)
            else:
                annual = (price - salvage) / life
            annual = min(annual, max(0, book - salvage))
            acc += annual
            book = max(salvage, price - acc)
            dep_schedule.append({
                'year': yr,
                'annual_dep': round(annual, 2),
                'accumulated': round(acc, 2),
                'book_value': round(book, 2),
                'is_current': yr == cur_year,
            })
        if price > 0:
            dep_pct = round(min(100, float(asset.get('accumulated_depreciation', 0)) / price * 100), 1)

    return render(request, 'fixed_asset_detail.html', {
        'asset': asset,
        'events': events,
        'dep_schedule': dep_schedule,
        'dep_pct': dep_pct,
        'asset_statuses': FIXED_ASSET_STATUSES,
        'asset_types': FIXED_ASSET_TYPES,
        'depreciation_methods': DEPRECIATION_METHODS,
        'can_edit': can_edit,
        'error': error,
        'success': success,
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    })
