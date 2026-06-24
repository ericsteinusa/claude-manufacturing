"""Django HTTP handlers for login, navigation, and account management.

Menu data lives in :mod:`manufacturing.menus`; authentication and role
persistence live in :mod:`manufacturing.accounts`.
"""

import os
import sys
import subprocess
from datetime import date, timedelta

import psycopg2

from django.shortcuts import render, redirect

from .log_utils import get_logger
from .schema import init_schema
from .db_pg import get_db_connection
from .audit_core import get_recent, get_history, AUDITED_TABLES
from .approval_core import (
    needs_approval, request_approval, approve_po, reject_po,
    get_pending_approvals, count_pending, get_po_approval,
    APPROVAL_THRESHOLD, APPROVAL_ROLES,
)
from .bom_web_core import (
    list_products, get_product, get_bom, explode_bom,
    add_bom_line, update_bom_line, delete_bom_line,
    update_item_master, ITEM_TYPES,
)
from .mrp_web_core import (
    get_demand_details, get_scheduled_receipts_detail,
    run_mrp, release_plan as mrp_release_plan,
)
from .inventory_core import (
    TRANS_TYPES,
    list_products as inv_list_products,
    get_product as inv_get_product,
    get_transactions, get_alert_counts,
    load_suppliers as inv_load_suppliers,
    record_transaction, create_product as inv_create_product,
    update_product as inv_update_product,
)
from .contacts_core import (
    contact_label,
    list_customers, get_customer, create_customer, update_customer,
    get_customer_orders,
    list_suppliers as contacts_list_suppliers,
    get_supplier, create_supplier, update_supplier,
    get_supplier_orders,
)
from .cs_calls_core import (
    validate_call, PLAN_STATUSES,
    load_customers_for_cs,
    list_tickets, get_ticket, create_ticket, update_ticket, close_ticket,
    get_escalations, get_summary_stats, get_monthly_volume,
    list_plans, create_plan, update_plan,
)
from .maintenance_core import (
    WO_STATUSES, WORK_TYPES, PRIORITIES,
    EQUIPMENT_STATUSES,
    SCHEDULE_STATUSES, FREQUENCIES,
    INSPECTION_STATUSES, INSPECTION_TYPES,
    DOWNTIME_STATUSES, DOWNTIME_CATEGORIES,
    PART_STATUSES, PART_CATEGORIES,
    MECHANIC_STATUSES, MECHANIC_TRADES, MECHANIC_SHIFTS,
    get_dashboard_counts as maint_get_dashboard_counts,
    load_mechanics,
    list_work_orders, get_work_order, create_work_order,
    update_work_order, complete_work_order,
    list_equipment, get_equipment, create_equipment, update_equipment,
    list_schedules, get_schedule, create_schedule,
    update_schedule, complete_schedule,
    list_inspections as maint_list_inspections,
    get_inspection as maint_get_inspection,
    create_inspection as maint_create_inspection,
    update_inspection as maint_update_inspection,
    complete_inspection,
    list_downtime, get_downtime, create_downtime, update_downtime,
    resolve_downtime,
    list_parts, get_part, create_part, update_part,
    list_mechanics, get_mechanic, create_mechanic, update_mechanic,
)
from .payroll_core import (
    SS_RATE, MEDICARE_RATE,
    FREQUENCIES as PAYROLL_FREQUENCIES,
    PAY_TYPES, DED_CATEGORIES, DED_METHODS,
    get_dashboard_counts as payroll_get_dashboard_counts,
    load_people as payroll_load_people,
    list_pay_rates, get_pay_rate, upsert_pay_rate, delete_pay_rate,
    list_deduction_types, get_deduction_type,
    create_deduction_type, update_deduction_type,
    list_employee_deductions, get_employee_deduction,
    create_employee_deduction, update_employee_deduction,
    delete_employee_deduction,
    list_payroll_runs, get_payroll_run, get_run_entries,
    get_pay_stub, get_stub_deductions, list_run_employees,
    get_ytd,
)
from .quality_core import (
    NCR_STATUSES, NCR_SOURCES, NCR_SEVERITIES, NCR_DISPOSITIONS,
    CAPA_STATUSES, CAPA_TYPES,
    AUDIT_STATUSES, AUDIT_TYPES,
    SUPPLIER_STATUSES, SUPPLIER_RATINGS,
    INSP_RESULTS, DEFECT_SEVERITIES,
    get_dashboard_counts,
    list_ncrs, get_ncr, create_ncr, update_ncr, close_ncr,
    list_capas, get_capa, create_capa, update_capa, close_capa,
    list_audits, get_audit, create_audit, update_audit, complete_audit,
    list_supplier_quality, get_supplier_quality,
    create_supplier_quality, update_supplier_quality,
    next_insp_number, list_inspections, get_inspection, create_inspection,
    update_inspection_result, get_defects, log_defect, resolve_defect,
    load_products_for_qa, load_work_orders_for_qa,
)
from .period_locking_core import (
    is_period_locked, close_period, reopen_period,
    list_periods, recent_months, period_label, PERIOD_ADMIN_ROLES,
)
from .purchase_orders_core import (
    PO_STATUSES, PO_STATUS_COLORS, PO_STATUS_ACTION_LABELS,
    list_pos, get_po, get_po_items,
    next_po_number, load_suppliers, load_products,
    create_po, update_po, add_po_item, delete_po_item,
    allowed_transitions, can_transition, set_po_status, receive_po_item,
)
from .time_clock_core import (
    get_current_entry, clock_in as tc_clock_in, clock_out_entry,
    list_entries, total_hours as tc_total_hours,
    get_period_dates, get_attendance,
)
from .time_clock_poller_core import (
    DEVICE_TYPES, DEVICE_TYPE_LABELS,
    list_devices, get_device, create_device, update_device, delete_device,
    list_sync_log, poll_device,
)
from .personnel_core import (
    TIME_OFF_STATUSES, TIME_OFF_TYPES,
    list_people, get_person, get_person_by_email,
    create_person, update_person,
    load_depts, load_dept_subs,
    list_time_off_requests, get_time_off_request,
    create_time_off_request, set_time_off_status,
    get_personnel_dashboard,
)
from .sales_orders_core import (
    SO_STATUSES, SO_STATUS_COLORS, SO_STATUS_ACTION_LABELS,
    list_sos, get_so, get_so_items,
    next_so_number, load_customers, load_products as load_so_products,
    create_so, update_so, add_so_item, delete_so_item,
    allowed_transitions as so_allowed_transitions,
    can_transition as so_can_transition,
    set_so_status,
)
from .work_orders_core import (
    WO_STATUSES, WO_STATUS_COLORS, WO_STATUS_ACTION_LABELS,
    list_wos, get_wo, get_wo_materials,
    next_wo_number, load_products as load_wo_products,
    create_wo, update_wo, add_wo_material, set_wo_status,
    can_transition as wo_can_transition,
    allowed_transitions as wo_allowed_transitions,
)
from .reports_core import (
    po_summary, wo_summary, inventory_alerts, cs_summary,
)
from .menus import (
    DASHBOARD_DEPARTMENTS,
    MANAGER_MENU_KEYS,
    _walk_tree,
)
from .accounts import (
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

log = get_logger(__name__)

# Menu leaves that are served as web pages rather than launched as a desktop
# Qt subprocess via run_script. Keyed by (dept, leaf_key) -> URL. The PO
# viewer (open/status/history) all land on the filterable list.
WEB_LEAF_URLS = {
    ('purchasing', 'new_po'): '/po/new/',
    ('purchasing', 'open_pos'): '/po/',
    ('purchasing', 'po_status'): '/po/',
    ('purchasing', 'po_hist'): '/po/',
    ('reports', 'rpt_dashboard'): '/reports/',
    ('maintenance', 'create_wo'): '/wo/new/',
    ('maintenance', 'open_wo'): '/wo/?status=open',
    ('maintenance', 'inprog_wo'): '/wo/?status=in_progress',
    ('maintenance', 'comp_wo'): '/wo/?status=completed',
    ('production', 'create_wo'): '/wo/new/',
    ('production', 'open_wo'): '/wo/?status=open',
    ('production', 'inprog_wo'): '/wo/?status=in_progress',
    ('production', 'comp_wo'): '/wo/?status=completed',
    ('sales', 'new_order'): '/so/new/',
    ('sales', 'open_orders'): '/so/?status=confirmed',
    ('sales', 'order_hist'): '/so/',
    ('sales', 'order_stat'): '/so/',
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
    ('personnel', 'month_sum'): '/time-clock/attendance/?period=month',
    ('personnel', 'tard_rpt'): '/time-clock/attendance/',
    ('personnel', 'abs_rpt'): '/time-clock/attendance/',
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
    ('maintenance', 'view_inv'): '/inventory/',
    ('maintenance', 'parts_req'): '/inventory/',
    ('maintenance', 'reorder'): '/inventory/?filter=low',
    ('maintenance', 'parts_hist'): '/inventory/',
    # Maintenance
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
    ('maintenance', 'daily_rpt'): '/maint/',
    ('maintenance', 'week_rpt'): '/maint/',
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
    ('maintenance', 'maint_budg'): '/maint/',
    ('maintenance', 'budg_act'): '/maint/',
    ('maintenance', 'budg_req'): '/maint/',
    ('maintenance', 'month_sum'): '/maint/',
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
    ('quality_assurance', 'daily_qa'): '/qa/',
    ('quality_assurance', 'week_sum'): '/qa/',
    ('quality_assurance', 'month_rpt'): '/qa/',
    ('quality_assurance', 'kpi_dash'): '/qa/',
    ('quality_assurance', 'supp_score'): '/qa/suppliers/',
    ('quality_assurance', 'inc_insp'): '/qa/inspections/',
    ('quality_assurance', 'supp_audit'): '/qa/suppliers/',
    ('quality_assurance', 'supp_rpts'): '/qa/suppliers/',
    ('quality_assurance', 'new_comp'): '/qa/ncr/',
    ('quality_assurance', 'open_comp'): '/qa/ncr/?status=Open',
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
    # Accounts Payable
    ('accounting', 'acct_pay'):   '/ap/',
    ('accounting', 'acct_mgr'):   '/ap/',
    ('accounting', 'ap'):         '/ap/',
    ('accounting', 'acct_rcv'):   '/ar/',
    ('accounting', 'rcv'):        '/ar/',
    # General Ledger / Financial Reports
    ('accounting', 'inc_stmt'):   '/gl/income-statement/',
    ('accounting', 'bal_sheet'):  '/gl/balance-sheet/',
    ('accounting', 'cash_flow'):  '/gl/',
    ('accounting', 'cust_rpts'):  '/gl/',
    ('accounting', 'fin_reports'): '/gl/',
    ('accounting', 'credit'):     '/gl/',
    ('finance', 'fin_plan'):       '/fin/',
    ('finance', 'fin_forecast'):   '/fin/',
    ('finance', 'fin_analysis'):   '/fin/',
    ('finance', 'fin_reporting'):  '/fin/',
    ('finance', 'treasury_ops'):   '/fin/',
    ('finance', 'capital_mgmt'):   '/fin/',
    ('finance', 'tax_planning'):   '/fin/',
    ('finance', 'treasury_mgmt'):  '/fin/',
    ('finance', 'invest_mgmt'):    '/fin/',
    ('finance', 'fin_rpts_mgr'):   '/gl/',
    # Purchasing dashboard
    ('purchasing', 'prod_entry'):  '/inventory/new/',
    ('purchasing', 'vend_eval'):   '/suppliers/',
    ('purchasing', 'vend_perf'):   '/suppliers/',
    ('purchasing', 'vend_cont'):   '/suppliers/',
    ('purchasing', 'spend_sum'):   '/purch/',
    ('purchasing', 'po_rpts'):     '/purch/',
    ('purchasing', 'budg_act'):    '/purch/',
    ('purchasing', 'cat_rpts'):    '/purch/',
    ('purchasing', 'act_cont'):    '/purch/',
    ('purchasing', 'new_cont'):    '/purch/',
    ('purchasing', 'cont_renew'):  '/purch/',
    ('purchasing', 'cont_arch'):   '/purch/',
    ('purchasing', 'pend_recv'):   '/po/',
    ('purchasing', 'recv_items'):  '/po/',
    ('purchasing', 'disc_rpts'):   '/po/',
    ('purchasing', 'recv_hist'):   '/po/',
    ('purchasing', 'new_req'):     '/po/new/',
    ('purchasing', 'pend_appr'):   '/po/approvals/',
    ('purchasing', 'appr_reqs'):   '/po/',
    ('purchasing', 'appr_pos'):    '/po/',
    ('purchasing', 'rej_pos'):     '/po/',
    ('purchasing', 'appr_hist'):   '/po/',
    ('purchasing', 'purch_budg'):  '/purch/',
    ('purchasing', 'budg_rpts'):   '/purch/',
    ('purchasing', 'spend_analy'): '/purch/',
    ('purchasing', 'vend_rpt'):    '/purch/',
    ('purchasing', 'cat_analy'):   '/purch/',
    ('purchasing', 'month_sum'):   '/purch/',
    ('purchasing', 'spend_rpt'):   '/purch/',
    ('purchasing', 'pend_renew'):  '/purch/',
    ('purchasing', 'cont_rpts'):   '/purch/',
    # Personnel dashboard
    ('personnel', 'pers_crm'):     '/people/',
    ('personnel', 'reg_form'):     '/register/',
    ('personnel', 'upd_pass'):     '/change-password/',
    ('personnel', 'dept_entry'):   '/pers/',
    ('personnel', 'dept_sub'):     '/pers/',
    ('personnel', 'ben_enroll'):   '/payroll/',
    ('personnel', 'ben_sum'):      '/payroll/',
    ('personnel', 'cobra'):        '/payroll/',
    ('personnel', 'ben_rpts'):     '/payroll/',
    ('personnel', 'sched_rev'):    '/people/',
    ('personnel', 'pend_revs'):    '/people/',
    ('personnel', 'rev_hist'):     '/people/',
    ('personnel', 'perf_rpts'):    '/people/',
    ('personnel', 'new_rec'):      '/people/',
    ('personnel', 'rec_hist'):     '/people/',
    ('personnel', 'disc_rpts'):    '/people/',
    ('personnel', 'train_cal'):    '/people/',
    ('personnel', 'train_recs'):   '/people/',
    ('personnel', 'course_mgmt'):  '/people/',
    ('personnel', 'cert_track'):   '/people/',
    ('personnel', 'hire_chk'):     '/people/',
    ('personnel', 'onb_stat'):     '/people/',
    ('personnel', 'doc_coll'):     '/people/',
    ('personnel', 'onb_rpts'):     '/people/',
    ('personnel', 'open_pos'):     '/pers/',
    ('personnel', 'appl_track'):   '/pers/',
    ('personnel', 'int_sched'):    '/pers/',
    ('personnel', 'offer_mgmt'):   '/pers/',
    ('personnel', 'term_proc'):    '/pers/',
    ('personnel', 'exit_int'):     '/pers/',
    ('personnel', 'final_pay'):    '/payroll/',
    ('personnel', 'offboard'):     '/pers/',
    ('personnel', 'sal_review'):   '/payroll/pay-rates/',
    ('personnel', 'sal_adj'):      '/payroll/pay-rates/',
    ('personnel', 'comp_rpts'):    '/payroll/',
    ('personnel', 'pay_grades'):   '/payroll/pay-rates/',
    ('personnel', 'hd_rpt'):       '/pers/',
    ('personnel', 'turn_rpt'):     '/pers/',
    ('personnel', 'month_sum'):    '/pers/',
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
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        if not email or not password:
            return render(request, 'home.html', {
                'error': 'Please enter both email and password.',
                'email_value': email,
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
        })

    if request.session.get('user_email'):
        return redirect('dashboard')

    return render(request, 'home.html', {})


def dashboard(request):
    email = request.session.get('user_email')
    if not email:
        return redirect('home')
    if not request.session.get('user_full_access'):
        dept_key = request.session.get('user_dept_key')
        if dept_key:
            return redirect('dept_menu', dept=dept_key)
    menu_items = [
        ('/dept/{}/'.format(key), label)
        for key, label in DASHBOARD_DEPARTMENTS
    ]
    pending_approvals = 0
    if request.session.get('user_role') in APPROVAL_ROLES:
        conn = get_db_connection()
        try:
            pending_approvals = count_pending(conn)
        finally:
            conn.close()
    return render(request, 'dashboard.html', {
        'email': email,
        'user_role': request.session.get('user_role', ''),
        'dept_name': request.session.get('user_dept_name', ''),
        'full_access': request.session.get('user_full_access', False),
        'menu_items': menu_items,
        'pending_approvals': pending_approvals,
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
        elif (dept, key) in WEB_LEAF_URLS:
            # Served as a real web page instead of launching a desktop window.
            url = WEB_LEAF_URLS[(dept, key)]
        else:
            url = '/run/{}/{}/'.format(dept, '/'.join(new_parts))
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


def run_script(request, dept, subpath):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('dept_menu', dept=dept)
    if not request.session.get('user_full_access'):
        user_dept = request.session.get('user_dept_key', '')
        if not user_dept:
            return redirect('dashboard')
        if dept != user_dept:
            return redirect('dept_menu', dept=user_dept)
    parts = [p for p in subpath.split('/') if p]
    if not parts:
        return redirect('dashboard')
    parent_parts, leaf_key = parts[:-1], parts[-1]
    node = _walk_tree(dept, parent_parts)
    if node:
        for key, _label, target in node['items']:
            if key == leaf_key and isinstance(target, str):
                mfg_dir = os.path.dirname(__file__)
                module_name = os.path.splitext(target)[0].replace('/', '.').replace(os.sep, '.')
                project_dir = os.path.dirname(mfg_dir)
                log.info(
                    "User %s launching manufacturing.%s (%s/%s)",
                    request.session.get('user_email'), module_name,
                    dept, subpath)
                try:
                    subprocess.Popen(
                        [sys.executable, '-m',
                            f'manufacturing.{module_name}', leaf_key],
                        cwd=project_dir,
                    )
                except Exception:
                    log.error(
                        "Failed to launch manufacturing.%s", module_name,
                        exc_info=True)
                    raise
                break
    if parent_parts:
        return redirect('/dept/{}/{}/'.format(dept, '/'.join(parent_parts)))
    return redirect('/dept/{}/'.format(dept))


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


def _po_access(request, write=False):
    """Gate PO pages: logged in, and either full access or Purchasing dept.

    With ``write=True`` also blocks ``READ_ONLY_ROLES`` from mutating (they may
    still view), mirroring the gating in :func:`run_script`. Returns a redirect
    response to send the user to, or ``None`` if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') != 'purchasing':
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('po_list')
    return None


def _po_context(request, **extra):
    """Toolbar context shared by the PO templates (matches base.html)."""
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def po_list(request):
    denied = _po_access(request)
    if denied:
        return denied

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


def po_detail(request, po_id):
    denied = _po_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        items = get_po_items(conn, po_id) if po else []
        products = load_products(conn) if (po and can_edit) else []
        approval = get_po_approval(conn, po_id) if po else None
    finally:
        conn.close()

    if not po:
        return redirect('po_list')

    po['status_color'] = PO_STATUS_COLORS.get(po['status'], '#ffffff')

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


def po_new(request):
    denied = _po_access(request, write=True)
    if denied:
        return denied

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


def po_edit(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied

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


def po_add_item(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
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


def po_remove_item(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
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


def po_set_status(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_detail', po_id=po_id)

    target = request.POST.get('status')
    conn = get_db_connection()
    try:
        po = get_po(conn, po_id)
        if po and can_transition(po['status'], target):
            if target == 'sent' and needs_approval(po.get('total', 0)):
                request_approval(
                    conn, po_id,
                    requested_by=request.session.get('user_email', ''),
                )
            else:
                set_po_status(conn, po_id, target)
            conn.commit()
    finally:
        conn.close()
    return redirect('po_detail', po_id=po_id)


def po_receive_item(request, po_id):
    denied = _po_access(request, write=True)
    if denied:
        return denied
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
                conn.commit()
        finally:
            conn.close()
    return redirect('po_detail', po_id=po_id)


# ---------------------------------------------------------------------------
# Reports dashboard (web)
# ---------------------------------------------------------------------------


def _reports_access(request):
    """Gate the reports dashboard: logged in + full access or reports dept."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') != 'reports':
            return redirect('dashboard')
    return None


def reports_dashboard(request):
    denied = _reports_access(request)
    if denied:
        return denied

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


def _wo_access(request, write=False):
    """Gate WO pages: login + full_access or maintenance/production dept.

    With ``write=True`` also blocks READ_ONLY_ROLES from mutating.
    Returns a redirect or None if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _WO_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('wo_list')
    return None


def _wo_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def wo_list(request):
    denied = _wo_access(request)
    if denied:
        return denied

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


def wo_detail(request, wo_id):
    denied = _wo_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        wo = get_wo(conn, wo_id)
        materials = get_wo_materials(conn, wo_id) if wo else []
        products = load_wo_products(conn) if (wo and can_edit) else []
    finally:
        conn.close()

    if not wo:
        return redirect('wo_list')

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


def wo_new(request):
    denied = _wo_access(request, write=True)
    if denied:
        return denied

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


def wo_edit(request, wo_id):
    denied = _wo_access(request, write=True)
    if denied:
        return denied

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


def wo_add_material(request, wo_id):
    denied = _wo_access(request, write=True)
    if denied:
        return denied
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


def wo_set_status(request, wo_id):
    denied = _wo_access(request, write=True)
    if denied:
        return denied
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


def _so_access(request, write=False):
    """Gate SO pages: logged in, and either full access or Sales dept.

    With ``write=True`` also blocks ``READ_ONLY_ROLES`` from mutating.
    Returns a redirect or None if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') != 'sales':
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('so_list')
    return None


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


def so_list(request):
    denied = _so_access(request)
    if denied:
        return denied

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


def so_detail(request, so_id):
    denied = _so_access(request)
    if denied:
        return denied

    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        items = get_so_items(conn, so_id) if so else []
        products = load_so_products(conn) if (so and can_edit) else []
    finally:
        conn.close()

    if not so:
        return redirect('so_list')

    so['status_color'] = SO_STATUS_COLORS.get(so['status'], '#ffffff')
    so['customer_name'] = _so_customer_name(so)

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


def so_new(request):
    denied = _so_access(request, write=True)
    if denied:
        return denied

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


def so_edit(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied

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


def so_add_item(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied
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


def so_remove_item(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied
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


def so_set_status(request, so_id):
    denied = _so_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('so_detail', so_id=so_id)

    target = request.POST.get('status')
    conn = get_db_connection()
    try:
        so = get_so(conn, so_id)
        if so and so_can_transition(so['status'], target):
            set_so_status(conn, so_id, target)
            conn.commit()
    finally:
        conn.close()
    return redirect('so_detail', so_id=so_id)


# ---------------------------------------------------------------------------
# Personnel — employee directory + time-off requests (web)
# ---------------------------------------------------------------------------

_PERSONNEL_ROLES = {'HR / Personnel'}


def _people_access(request, write=False):
    """Gate personnel pages: logged in + full_access, HR/Personnel role, or
    personnel dept. With write=True also blocks READ_ONLY_ROLES.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        role = request.session.get('user_role', '')
        dept = request.session.get('user_dept_key', '')
        if role not in _PERSONNEL_ROLES and dept != 'personnel':
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('people_list')
    return None


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


def people_list(request):
    denied = _people_access(request)
    if denied:
        return denied

    dept_id = _int_or_none(request.GET.get('dept_id'))
    search = (request.GET.get('search') or '').strip() or None

    conn = get_db_connection()
    try:
        people = list_people(conn, dept_id=dept_id, search=search)
        depts = load_depts(conn)
    finally:
        conn.close()

    return render(request, 'people_list.html', _people_context(
        request,
        people=people,
        depts=depts,
        dept_id=dept_id,
        search=search or '',
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url='/dept/personnel/pers_menu/emp_records/',
    ))


def people_detail(request, person_id):
    denied = _people_access(request)
    if denied:
        return denied

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


def people_new(request):
    denied = _people_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        if request.method == 'POST':
            data, error = _people_form(request)
            if not error:
                person_id = create_person(
                    conn, **data,
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


def people_edit(request, person_id):
    denied = _people_access(request, write=True)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        person = get_person(conn, person_id)
        if not person:
            return redirect('people_list')

        if request.method == 'POST':
            data, error = _people_form(request)
            if not error:
                update_person(conn, person_id, **data)
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


def _dev_access(request):
    """Return True if the logged-in user can manage time clock devices."""
    return _is_hr(request)


def tc_device_list(request):
    """List all registered time clock terminals."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request):
        return redirect('time_clock_status')

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


def tc_device_new(request):
    """Add a new time clock device — asks for type, then shows config fields."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request):
        return redirect('time_clock_status')

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


def tc_device_detail(request, device_id: int):
    """Edit a device or view its sync log."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request):
        return redirect('time_clock_status')

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


def tc_device_poll(request, device_id: int):
    """Trigger an immediate poll of a device."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request) or request.method != 'POST':
        return redirect('tc_device_list')

    conn = get_db_connection()
    try:
        result = poll_device(conn, device_id)
        conn.commit()
    finally:
        conn.close()

    return redirect('tc_device_detail', device_id=device_id)


def tc_device_delete(request, device_id: int):
    """Delete a device and its sync log."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _dev_access(request) or request.method != 'POST':
        return redirect('tc_device_list')

    conn = get_db_connection()
    try:
        delete_device(conn, device_id)
        conn.commit()
    finally:
        conn.close()

    return redirect('tc_device_list')


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

_AUDIT_ROLES = FULL_ACCESS_ROLES | {'Auditor'}


def _audit_access(request):
    return request.session.get('user_role') in _AUDIT_ROLES


def audit_log(request):
    """Recent audit log entries, filterable by table and user."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _audit_access(request):
        return redirect('dashboard')

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


def audit_record(request, table_name: str, record_id: int):
    """Full history for a single record."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not _audit_access(request):
        return redirect('dashboard')

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

def _periods_access(request, *, write: bool = False):
    """Return a redirect if the user may not access the periods page."""
    if not request.session.get('user_email'):
        return redirect('home')
    role = request.session.get('user_role', '')
    if write and role not in PERIOD_ADMIN_ROLES:
        return redirect('periods')
    if not write and role not in PERIOD_ADMIN_ROLES:
        return redirect('dashboard')
    return None


def periods(request):
    """List closed periods and show close/reopen controls."""
    denied = _periods_access(request)
    if denied:
        return denied

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

def _approval_access(request):
    """Redirect if the user is not authorised to approve/reject POs."""
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') not in APPROVAL_ROLES:
        return redirect('dashboard')
    return None


def po_approvals(request):
    """Queue of POs waiting for approval (President / VP only)."""
    denied = _approval_access(request)
    if denied:
        return denied

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


def po_approve(request, approval_id):
    """Approve a pending PO."""
    denied = _approval_access(request)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_approvals')

    notes = (request.POST.get('notes') or '').strip()
    conn = get_db_connection()
    try:
        approve_po(conn, approval_id,
                   decided_by=request.session.get('user_email', ''),
                   notes=notes)
        conn.commit()
    except ValueError:
        conn.rollback()
    finally:
        conn.close()
    return redirect('po_approvals')


def po_reject(request, approval_id):
    """Reject a pending PO, returning it to draft."""
    denied = _approval_access(request)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('po_approvals')

    notes = (request.POST.get('notes') or '').strip()
    conn = get_db_connection()
    try:
        reject_po(conn, approval_id,
                  decided_by=request.session.get('user_email', ''),
                  notes=notes)
        conn.commit()
    except ValueError:
        conn.rollback()
    finally:
        conn.close()
    return redirect('po_approvals')


# ---------------------------------------------------------------------------
# Bill of Materials (web)
# ---------------------------------------------------------------------------

_BOM_DEPT_KEYS = {'engineering', 'production'}


def _bom_access(request, write=False):
    """Gate BOM pages: logged in + full_access or engineering/production dept.

    With ``write=True`` also blocks READ_ONLY_ROLES from mutating.
    Returns a redirect or None if allowed.
    """
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _BOM_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('bom_list')
    return None


def _bom_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
    }
    ctx.update(extra)
    return ctx


def bom_list(request):
    denied = _bom_access(request)
    if denied:
        return denied

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

    return render(request, 'bom_list.html', _bom_context(
        request,
        products=products,
        item_type=item_type,
        item_types=ITEM_TYPES,
        can_edit=request.session.get('user_role') not in READ_ONLY_ROLES,
        back_url=back_url,
    ))


def bom_detail(request, product_id):
    denied = _bom_access(request)
    if denied:
        return denied

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


def bom_explode(request, product_id):
    denied = _bom_access(request)
    if denied:
        return denied

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


def _mrp_access(request, write=False):
    """Gate MRP pages: logged-in + full_access or production/engineering dept."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _MRP_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('mrp_home')
    return None


def _mrp_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def mrp_home(request):
    denied = _mrp_access(request)
    if denied:
        return denied

    conn = get_db_connection()
    try:
        demand_rows = get_demand_details(conn)
        scheduled = get_scheduled_receipts_detail(conn)
    finally:
        conn.close()

    # Annotate each demand row with scheduled receipts and net requirement.
    for row in demand_rows:
        row['scheduled'] = scheduled.get(row['id'], 0.0)
        row['net'] = max(0.0, row['demand_qty'] - row['on_hand'] - row['scheduled'])

    has_plan = 'mrp_plan' in request.session and bool(request.session['mrp_plan'])
    return render(request, 'mrp_home.html', _mrp_context(
        request,
        demand_rows=demand_rows,
        has_plan=has_plan,
    ))


def mrp_run(request):
    denied = _mrp_access(request, write=True)
    if denied:
        return denied
    if request.method != 'POST':
        return redirect('mrp_home')

    conn = get_db_connection()
    try:
        plan = run_mrp(conn)
    finally:
        conn.close()

    request.session['mrp_plan'] = plan
    return redirect('mrp_plan')


def mrp_plan(request):
    denied = _mrp_access(request)
    if denied:
        return denied

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


def mrp_release(request):
    denied = _mrp_access(request, write=True)
    if denied:
        return denied
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
    ))


# ---------------------------------------------------------------------------
# Inventory (web)
# ---------------------------------------------------------------------------

_INV_DEPT_KEYS = {'production', 'engineering', 'maintenance', 'purchasing'}


def _inv_access(request, write=False):
    """Gate inventory pages: logged-in + full_access or relevant dept."""
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _INV_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('inventory_list')
    return None


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


def inventory_list(request):
    denied = _inv_access(request)
    if denied:
        return denied

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


def inventory_new(request):
    denied = _inv_access(request, write=True)
    if denied:
        return denied

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


def inventory_detail(request, product_id):
    denied = _inv_access(request)
    if denied:
        return denied

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
                    product = inv_get_product(conn, product_id)
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


def inventory_transaction(request, product_id):
    """POST only — record a stock movement for a product."""
    denied = _inv_access(request, write=True)
    if denied:
        return denied
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


def _customer_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _CUSTOMER_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('customer_list')
    return None


def _supplier_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _SUPPLIER_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('supplier_list')
    return None


def _contacts_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def customer_list(request):
    denied = _customer_access(request)
    if denied:
        return denied
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        customers = list_customers(conn, search=search or None)
    finally:
        conn.close()
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


def customer_new(request):
    denied = _customer_access(request, write=True)
    if denied:
        return denied
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


def customer_detail(request, customer_id):
    denied = _customer_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = None
    success = None
    try:
        contact = get_customer(conn, customer_id)
        if not contact:
            return redirect('customer_list')
        if request.method == 'POST' and can_edit:
            try:
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
        error=error,
        success=success,
        can_edit=can_edit,
    ))


# ---------------------------------------------------------------------------
# Suppliers (web)
# ---------------------------------------------------------------------------

def supplier_list(request):
    denied = _supplier_access(request)
    if denied:
        return denied
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    try:
        suppliers = contacts_list_suppliers(conn, search=search or None)
    finally:
        conn.close()
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


def supplier_new(request):
    denied = _supplier_access(request, write=True)
    if denied:
        return denied
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


def supplier_detail(request, supplier_id):
    denied = _supplier_access(request)
    if denied:
        return denied
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


def _cs_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _CS_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('cs_ticket_list')
    return None


def _cs_context(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def cs_ticket_list(request):
    denied = _cs_access(request)
    if denied:
        return denied
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
    return render(request, 'cs_list.html', _cs_context(
        request,
        tickets=tickets,
        open_count=open_count,
        overdue_count=overdue_count,
        search=search,
        status_filter=status_filter,
        my_only=my_only,
    ))


def cs_ticket_new(request):
    denied = _cs_access(request, write=True)
    if denied:
        return denied
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


def cs_ticket_detail(request, ticket_id):
    denied = _cs_access(request)
    if denied:
        return denied
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


def cs_escalations(request):
    denied = _cs_access(request)
    if denied:
        return denied
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


def cs_reports(request):
    denied = _cs_access(request)
    if denied:
        return denied
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


def cs_plans(request):
    denied = _cs_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    status_filter = request.GET.get('status', '').strip()
    conn = get_db_connection()
    error = None
    success = None
    plans = []
    try:
        plans = list_plans(conn, status=status_filter or None)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action == 'create':
                    create_plan(
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
                    update_plan(
                        conn, pid,
                        title=request.POST.get('title', ''),
                        description=request.POST.get('description', ''),
                        owner=request.POST.get('owner', ''),
                        target_date=request.POST.get('target_date', ''),
                        status=request.POST.get('status', 'Open'),
                    )
                    conn.commit()
                    success = 'Plan updated.'
                plans = list_plans(conn, status=status_filter or None)
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


# ---------------------------------------------------------------------------
# Quality Assurance (web)
# ---------------------------------------------------------------------------

_QA_DEPT_KEYS = {'quality_assurance', 'production', 'purchasing'}


def _qa_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _QA_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('qa_dashboard')
    return None


def _qa_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def qa_dashboard(request):
    denied = _qa_access(request)
    if denied:
        return denied
    conn = get_db_connection()
    try:
        counts = get_dashboard_counts(conn)
    finally:
        conn.close()
    return render(request, 'qa_dashboard.html', _qa_ctx(request, counts=counts))


# --- NCR ---

def qa_ncr_list(request):
    denied = _qa_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    ncrs = []
    try:
        ncrs = list_ncrs(conn, status=status_filter or None,
                         search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_ncr(
                    conn,
                    title=request.POST.get('title', ''),
                    source=request.POST.get('source', ''),
                    severity=request.POST.get('severity', ''),
                    product=request.POST.get('product', ''),
                    detected_date=request.POST.get('detected_date', ''),
                    disposition=request.POST.get('disposition', 'Pending'),
                    owner=request.POST.get('owner', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_ncr_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                ncrs = list_ncrs(conn, status=status_filter or None,
                                 search=search or None)
    finally:
        conn.close()
    return render(request, 'qa_ncr_list.html', _qa_ctx(
        request, ncrs=ncrs, status_filter=status_filter, search=search,
        ncr_statuses=NCR_STATUSES, ncr_sources=NCR_SOURCES,
        ncr_severities=NCR_SEVERITIES, ncr_dispositions=NCR_DISPOSITIONS,
        error=error, success=success,
    ))


def qa_ncr_detail(request, ncr_id):
    denied = _qa_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    ncr = None
    try:
        ncr = get_ncr(conn, ncr_id)
        if not ncr:
            return redirect('qa_ncr_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'close':
                    close_ncr(conn, ncr_id)
                    success = 'NCR closed.'
                else:
                    update_ncr(
                        conn, ncr_id,
                        title=request.POST.get('title', ''),
                        source=request.POST.get('source', ''),
                        severity=request.POST.get('severity', ''),
                        product=request.POST.get('product', ''),
                        detected_date=request.POST.get('detected_date', ''),
                        disposition=request.POST.get('disposition', ''),
                        owner=request.POST.get('owner', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'NCR updated.'
                conn.commit()
                ncr = get_ncr(conn, ncr_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_ncr_detail.html', _qa_ctx(
        request, ncr=ncr, can_edit=can_edit,
        ncr_statuses=NCR_STATUSES, ncr_sources=NCR_SOURCES,
        ncr_severities=NCR_SEVERITIES, ncr_dispositions=NCR_DISPOSITIONS,
        error=error, success=success,
    ))


# --- CAPA ---

def qa_capa_list(request):
    denied = _qa_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    capas = []
    try:
        capas = list_capas(conn, status=status_filter or None,
                           search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_capa(
                    conn,
                    title=request.POST.get('title', ''),
                    capa_type=request.POST.get('capa_type', 'Corrective'),
                    ncr_ref=request.POST.get('ncr_ref', ''),
                    owner=request.POST.get('owner', ''),
                    due_date=request.POST.get('due_date', ''),
                    action_plan=request.POST.get('action_plan', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_capa_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                capas = list_capas(conn, status=status_filter or None,
                                   search=search or None)
    finally:
        conn.close()
    return render(request, 'qa_capa_list.html', _qa_ctx(
        request, capas=capas, status_filter=status_filter, search=search,
        capa_statuses=CAPA_STATUSES, capa_types=CAPA_TYPES,
        error=error, success=success,
    ))


def qa_capa_detail(request, capa_id):
    denied = _qa_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    capa = None
    try:
        capa = get_capa(conn, capa_id)
        if not capa:
            return redirect('qa_capa_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'close':
                    close_capa(conn, capa_id)
                    success = 'CAPA closed.'
                else:
                    update_capa(
                        conn, capa_id,
                        title=request.POST.get('title', ''),
                        capa_type=request.POST.get('capa_type', ''),
                        ncr_ref=request.POST.get('ncr_ref', ''),
                        owner=request.POST.get('owner', ''),
                        due_date=request.POST.get('due_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        status=request.POST.get('status', ''),
                        action_plan=request.POST.get('action_plan', ''),
                    )
                    success = 'CAPA updated.'
                conn.commit()
                capa = get_capa(conn, capa_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_capa_detail.html', _qa_ctx(
        request, capa=capa, can_edit=can_edit,
        capa_statuses=CAPA_STATUSES, capa_types=CAPA_TYPES,
        error=error, success=success,
    ))


# --- Audits ---

def qa_audit_list(request):
    denied = _qa_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    conn = get_db_connection()
    error = success = None
    audits = []
    try:
        audits = list_audits(conn, status=status_filter or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_audit(
                    conn,
                    title=request.POST.get('title', ''),
                    audit_type=request.POST.get('audit_type', ''),
                    auditor=request.POST.get('auditor', ''),
                    scheduled_date=request.POST.get('scheduled_date', ''),
                    findings=request.POST.get('findings', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_audit_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                audits = list_audits(conn, status=status_filter or None)
    finally:
        conn.close()
    return render(request, 'qa_audit_list.html', _qa_ctx(
        request, audits=audits, status_filter=status_filter,
        audit_statuses=AUDIT_STATUSES, audit_types=AUDIT_TYPES,
        error=error, success=success,
    ))


def qa_audit_detail(request, audit_id):
    denied = _qa_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    audit = None
    try:
        audit = get_audit(conn, audit_id)
        if not audit:
            return redirect('qa_audit_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_audit(conn, audit_id,
                                   result=request.POST.get('result', ''),
                                   findings=request.POST.get('findings', ''))
                    success = 'Audit marked complete.'
                else:
                    update_audit(
                        conn, audit_id,
                        title=request.POST.get('title', ''),
                        audit_type=request.POST.get('audit_type', ''),
                        auditor=request.POST.get('auditor', ''),
                        scheduled_date=request.POST.get('scheduled_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        result=request.POST.get('result', ''),
                        status=request.POST.get('status', ''),
                        findings=request.POST.get('findings', ''),
                    )
                    success = 'Audit updated.'
                conn.commit()
                audit = get_audit(conn, audit_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_audit_detail.html', _qa_ctx(
        request, audit=audit, can_edit=can_edit,
        audit_statuses=AUDIT_STATUSES, audit_types=AUDIT_TYPES,
        error=error, success=success,
    ))


# --- Supplier Quality ---

def qa_supplier_list(request):
    denied = _qa_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    suppliers = []
    try:
        suppliers = list_supplier_quality(conn, status=status_filter or None,
                                          search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_supplier_quality(
                    conn,
                    supplier=request.POST.get('supplier', ''),
                    material=request.POST.get('material', ''),
                    rating=request.POST.get('rating', ''),
                    ppm=request.POST.get('ppm', ''),
                    last_audit=request.POST.get('last_audit', ''),
                    status=request.POST.get('status', 'Pending'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_supplier_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                suppliers = list_supplier_quality(conn, status=status_filter or None,
                                                  search=search or None)
    finally:
        conn.close()
    return render(request, 'qa_supplier_list.html', _qa_ctx(
        request, suppliers=suppliers, status_filter=status_filter, search=search,
        supplier_statuses=SUPPLIER_STATUSES, supplier_ratings=SUPPLIER_RATINGS,
        error=error, success=success,
    ))


def qa_supplier_detail(request, sq_id):
    denied = _qa_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    supplier = None
    try:
        supplier = get_supplier_quality(conn, sq_id)
        if not supplier:
            return redirect('qa_supplier_list')
        if request.method == 'POST' and can_edit:
            try:
                update_supplier_quality(
                    conn, sq_id,
                    supplier=request.POST.get('supplier', ''),
                    material=request.POST.get('material', ''),
                    rating=request.POST.get('rating', ''),
                    ppm=request.POST.get('ppm', ''),
                    last_audit=request.POST.get('last_audit', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                supplier = get_supplier_quality(conn, sq_id)
                success = 'Supplier quality record updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_supplier_detail.html', _qa_ctx(
        request, supplier=supplier, can_edit=can_edit,
        supplier_statuses=SUPPLIER_STATUSES, supplier_ratings=SUPPLIER_RATINGS,
        error=error, success=success,
    ))


# --- Inspections ---

def qa_inspection_list(request):
    denied = _qa_access(request)
    if denied:
        return denied
    result_filter = request.GET.get('result', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    inspections = []
    products = []
    work_orders = []
    try:
        inspections = list_inspections(conn, result=result_filter or None,
                                       search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            products = load_products_for_qa(conn)
            work_orders = load_work_orders_for_qa(conn)
            try:
                pid_raw = request.POST.get('product_id', '')
                wid_raw = request.POST.get('wo_id', '')
                insp_num = next_insp_number(conn)
                create_inspection(
                    conn,
                    insp_number=insp_num,
                    product_id=int(pid_raw) if pid_raw else None,
                    wo_id=int(wid_raw) if wid_raw else None,
                    insp_date=request.POST.get('insp_date', ''),
                    inspector=request.POST.get('inspector', ''),
                    result=request.POST.get('result', 'pending'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('qa_inspection_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                inspections = list_inspections(conn, result=result_filter or None,
                                               search=search or None)
        else:
            products = load_products_for_qa(conn)
            work_orders = load_work_orders_for_qa(conn)
    finally:
        conn.close()
    return render(request, 'qa_inspection_list.html', _qa_ctx(
        request, inspections=inspections, result_filter=result_filter,
        search=search, insp_results=INSP_RESULTS,
        products=products, work_orders=work_orders,
        error=error, success=success,
    ))


def qa_inspection_detail(request, insp_id):
    denied = _qa_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    inspection = None
    defects = []
    try:
        inspection = get_inspection(conn, insp_id)
        if not inspection:
            return redirect('qa_inspection_list')
        defects = get_defects(conn, insp_id)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', '')
            try:
                if action in ('passed', 'failed', 'on_hold', 'pending'):
                    update_inspection_result(conn, insp_id, action)
                    success = f'Inspection marked {action}.'
                elif action == 'log_defect':
                    log_defect(
                        conn, insp_id,
                        defect_type=request.POST.get('defect_type', ''),
                        severity=request.POST.get('severity', 'minor'),
                        description=request.POST.get('description', ''),
                        created_by=request.session.get('user_email', ''),
                    )
                    success = 'Defect logged.'
                elif action == 'resolve_defect':
                    did = int(request.POST.get('defect_id', 0))
                    resolve_defect(conn, did)
                    success = 'Defect resolved.'
                conn.commit()
                inspection = get_inspection(conn, insp_id)
                defects = get_defects(conn, insp_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'qa_inspection_detail.html', _qa_ctx(
        request, inspection=inspection, defects=defects, can_edit=can_edit,
        defect_severities=DEFECT_SEVERITIES,
        error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Maintenance (web)
# ---------------------------------------------------------------------------

_MAINT_DEPT_KEYS = {'maintenance', 'production', 'purchasing'}


def _maint_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        if request.session.get('user_dept_key') not in _MAINT_DEPT_KEYS:
            return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('maint_dashboard')
    return None


def _maint_ctx(request, **extra):
    ctx = {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': request.session.get('user_role') not in READ_ONLY_ROLES,
    }
    ctx.update(extra)
    return ctx


def maint_dashboard(request):
    denied = _maint_access(request)
    if denied:
        return denied
    conn = get_db_connection()
    try:
        counts = maint_get_dashboard_counts(conn)
    finally:
        conn.close()
    return render(request, 'maint_dashboard.html',
                  _maint_ctx(request, counts=counts))


# --- Work Orders ---

def maint_wo_list(request):
    denied = _maint_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    wos = []
    mechanics = []
    try:
        wos = list_work_orders(conn, status=status_filter or None,
                               priority=priority_filter or None,
                               search=search or None)
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_work_order(
                    conn,
                    title=request.POST.get('title', ''),
                    equipment=request.POST.get('equipment', ''),
                    work_type=request.POST.get('work_type', 'Repair'),
                    priority=request.POST.get('priority', 'Medium'),
                    assigned_to=request.POST.get('assigned_to', ''),
                    requested_date=request.POST.get('requested_date', ''),
                    due_date=request.POST.get('due_date', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_wo_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                wos = list_work_orders(conn, status=status_filter or None,
                                       priority=priority_filter or None,
                                       search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_wo_list.html', _maint_ctx(
        request, wos=wos, mechanics=mechanics,
        status_filter=status_filter, priority_filter=priority_filter,
        search=search, wo_statuses=WO_STATUSES, work_types=WORK_TYPES,
        priorities=PRIORITIES, error=error, success=success,
    ))


def maint_wo_detail(request, wo_id):
    denied = _maint_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    wo = None
    mechanics = []
    try:
        wo = get_work_order(conn, wo_id)
        if not wo:
            return redirect('maint_wo_list')
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_work_order(conn, wo_id)
                    success = 'Work order completed.'
                else:
                    update_work_order(
                        conn, wo_id,
                        title=request.POST.get('title', ''),
                        equipment=request.POST.get('equipment', ''),
                        work_type=request.POST.get('work_type', ''),
                        priority=request.POST.get('priority', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        requested_date=request.POST.get('requested_date', ''),
                        due_date=request.POST.get('due_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Work order updated.'
                conn.commit()
                wo = get_work_order(conn, wo_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_wo_detail.html', _maint_ctx(
        request, wo=wo, mechanics=mechanics, can_edit=can_edit,
        wo_statuses=WO_STATUSES, work_types=WORK_TYPES, priorities=PRIORITIES,
        error=error, success=success,
    ))


# --- Equipment ---

def maint_equipment_list(request):
    denied = _maint_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    equipment = []
    try:
        equipment = list_equipment(conn, status=status_filter or None,
                                   search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_equipment(
                    conn,
                    name=request.POST.get('name', ''),
                    asset_tag=request.POST.get('asset_tag', ''),
                    location=request.POST.get('location', ''),
                    manufacturer=request.POST.get('manufacturer', ''),
                    install_date=request.POST.get('install_date', ''),
                    last_service=request.POST.get('last_service', ''),
                    status=request.POST.get('status', 'Operational'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_equipment_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                equipment = list_equipment(conn, status=status_filter or None,
                                           search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_equipment_list.html', _maint_ctx(
        request, equipment=equipment, status_filter=status_filter,
        search=search, equipment_statuses=EQUIPMENT_STATUSES,
        error=error, success=success,
    ))


def maint_equipment_detail(request, eq_id):
    denied = _maint_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    eq = None
    try:
        eq = get_equipment(conn, eq_id)
        if not eq:
            return redirect('maint_equipment_list')
        if request.method == 'POST' and can_edit:
            try:
                update_equipment(
                    conn, eq_id,
                    name=request.POST.get('name', ''),
                    asset_tag=request.POST.get('asset_tag', ''),
                    location=request.POST.get('location', ''),
                    manufacturer=request.POST.get('manufacturer', ''),
                    install_date=request.POST.get('install_date', ''),
                    last_service=request.POST.get('last_service', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                eq = get_equipment(conn, eq_id)
                success = 'Equipment updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_equipment_detail.html', _maint_ctx(
        request, eq=eq, can_edit=can_edit,
        equipment_statuses=EQUIPMENT_STATUSES,
        error=error, success=success,
    ))


# --- PM Schedules ---

def maint_schedule_list(request):
    denied = _maint_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    schedules = []
    mechanics = []
    try:
        schedules = list_schedules(conn, status=status_filter or None,
                                   search=search or None)
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_schedule(
                    conn,
                    task=request.POST.get('task', ''),
                    equipment=request.POST.get('equipment', ''),
                    frequency=request.POST.get('frequency', 'Monthly'),
                    assigned_to=request.POST.get('assigned_to', ''),
                    last_done=request.POST.get('last_done', ''),
                    next_due=request.POST.get('next_due', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_schedule_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                schedules = list_schedules(conn, status=status_filter or None,
                                           search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_schedule_list.html', _maint_ctx(
        request, schedules=schedules, mechanics=mechanics,
        status_filter=status_filter, search=search,
        schedule_statuses=SCHEDULE_STATUSES, frequencies=FREQUENCIES,
        error=error, success=success,
    ))


def maint_schedule_detail(request, sched_id):
    denied = _maint_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    schedule = None
    mechanics = []
    try:
        schedule = get_schedule(conn, sched_id)
        if not schedule:
            return redirect('maint_schedule_list')
        mechanics = load_mechanics(conn)
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_schedule(conn, sched_id)
                    success = 'PM task marked complete.'
                else:
                    update_schedule(
                        conn, sched_id,
                        task=request.POST.get('task', ''),
                        equipment=request.POST.get('equipment', ''),
                        frequency=request.POST.get('frequency', ''),
                        assigned_to=request.POST.get('assigned_to', ''),
                        last_done=request.POST.get('last_done', ''),
                        next_due=request.POST.get('next_due', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Schedule updated.'
                conn.commit()
                schedule = get_schedule(conn, sched_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_schedule_detail.html', _maint_ctx(
        request, schedule=schedule, mechanics=mechanics, can_edit=can_edit,
        schedule_statuses=SCHEDULE_STATUSES, frequencies=FREQUENCIES,
        error=error, success=success,
    ))


# --- Inspections ---

def maint_inspection_list(request):
    denied = _maint_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    inspections = []
    try:
        inspections = maint_list_inspections(conn, status=status_filter or None,
                                             search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                maint_create_inspection(
                    conn,
                    area=request.POST.get('area', ''),
                    inspection_type=request.POST.get('inspection_type', 'General'),
                    inspector=request.POST.get('inspector', ''),
                    scheduled_date=request.POST.get('scheduled_date', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_inspection_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                inspections = maint_list_inspections(
                    conn, status=status_filter or None, search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_inspection_list.html', _maint_ctx(
        request, inspections=inspections, status_filter=status_filter,
        search=search, inspection_statuses=INSPECTION_STATUSES,
        inspection_types=INSPECTION_TYPES,
        error=error, success=success,
    ))


def maint_inspection_detail(request, insp_id):
    denied = _maint_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    inspection = None
    try:
        inspection = maint_get_inspection(conn, insp_id)
        if not inspection:
            return redirect('maint_inspection_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'complete':
                    complete_inspection(
                        conn, insp_id,
                        result=request.POST.get('result', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Inspection completed.'
                else:
                    maint_update_inspection(
                        conn, insp_id,
                        area=request.POST.get('area', ''),
                        inspection_type=request.POST.get('inspection_type', ''),
                        inspector=request.POST.get('inspector', ''),
                        scheduled_date=request.POST.get('scheduled_date', ''),
                        completed_date=request.POST.get('completed_date', ''),
                        result=request.POST.get('result', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Inspection updated.'
                conn.commit()
                inspection = maint_get_inspection(conn, insp_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_inspection_detail.html', _maint_ctx(
        request, inspection=inspection, can_edit=can_edit,
        inspection_statuses=INSPECTION_STATUSES,
        inspection_types=INSPECTION_TYPES,
        error=error, success=success,
    ))


# --- Downtime ---

def maint_downtime_list(request):
    denied = _maint_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    downtime_records = []
    try:
        downtime_records = list_downtime(conn, status=status_filter or None,
                                         search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_downtime(
                    conn,
                    equipment=request.POST.get('equipment', ''),
                    reason=request.POST.get('reason', ''),
                    category=request.POST.get('category', 'Breakdown'),
                    down_date=request.POST.get('down_date', ''),
                    hours=request.POST.get('hours', ''),
                    cost=request.POST.get('cost', ''),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_downtime_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                downtime_records = list_downtime(conn, status=status_filter or None,
                                                 search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_downtime_list.html', _maint_ctx(
        request, downtime_records=downtime_records,
        status_filter=status_filter, search=search,
        downtime_statuses=DOWNTIME_STATUSES,
        downtime_categories=DOWNTIME_CATEGORIES,
        error=error, success=success,
    ))


def maint_downtime_detail(request, dt_id):
    denied = _maint_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    record = None
    try:
        record = get_downtime(conn, dt_id)
        if not record:
            return redirect('maint_downtime_list')
        if request.method == 'POST' and can_edit:
            action = request.POST.get('action', 'update')
            try:
                if action == 'resolve':
                    resolve_downtime(conn, dt_id)
                    success = 'Downtime marked resolved.'
                else:
                    update_downtime(
                        conn, dt_id,
                        equipment=request.POST.get('equipment', ''),
                        reason=request.POST.get('reason', ''),
                        category=request.POST.get('category', ''),
                        down_date=request.POST.get('down_date', ''),
                        hours=request.POST.get('hours', ''),
                        cost=request.POST.get('cost', ''),
                        status=request.POST.get('status', ''),
                        notes=request.POST.get('notes', ''),
                    )
                    success = 'Record updated.'
                conn.commit()
                record = get_downtime(conn, dt_id)
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_downtime_detail.html', _maint_ctx(
        request, record=record, can_edit=can_edit,
        downtime_statuses=DOWNTIME_STATUSES,
        downtime_categories=DOWNTIME_CATEGORIES,
        error=error, success=success,
    ))


# --- Parts ---

def maint_parts_list(request):
    denied = _maint_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    parts = []
    try:
        parts = list_parts(conn, status=status_filter or None,
                           search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_part(
                    conn,
                    name=request.POST.get('name', ''),
                    part_number=request.POST.get('part_number', ''),
                    category=request.POST.get('category', 'Other'),
                    location=request.POST.get('location', ''),
                    quantity=request.POST.get('quantity', ''),
                    reorder_level=request.POST.get('reorder_level', ''),
                    unit_cost=request.POST.get('unit_cost', ''),
                    status=request.POST.get('status', 'In Stock'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_parts_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                parts = list_parts(conn, status=status_filter or None,
                                   search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_parts_list.html', _maint_ctx(
        request, parts=parts, status_filter=status_filter, search=search,
        part_statuses=PART_STATUSES, part_categories=PART_CATEGORIES,
        error=error, success=success,
    ))


def maint_part_detail(request, part_id):
    denied = _maint_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    part = None
    try:
        part = get_part(conn, part_id)
        if not part:
            return redirect('maint_parts_list')
        if request.method == 'POST' and can_edit:
            try:
                update_part(
                    conn, part_id,
                    name=request.POST.get('name', ''),
                    part_number=request.POST.get('part_number', ''),
                    category=request.POST.get('category', ''),
                    location=request.POST.get('location', ''),
                    quantity=request.POST.get('quantity', ''),
                    reorder_level=request.POST.get('reorder_level', ''),
                    unit_cost=request.POST.get('unit_cost', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                part = get_part(conn, part_id)
                success = 'Part updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_part_detail.html', _maint_ctx(
        request, part=part, can_edit=can_edit,
        part_statuses=PART_STATUSES, part_categories=PART_CATEGORIES,
        error=error, success=success,
    ))


# --- Mechanics ---

def maint_mechanics_list(request):
    denied = _maint_access(request)
    if denied:
        return denied
    status_filter = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    conn = get_db_connection()
    error = success = None
    mechanics = []
    try:
        mechanics = list_mechanics(conn, status=status_filter or None,
                                   search=search or None)
        if request.method == 'POST' and request.session.get('user_role') not in READ_ONLY_ROLES:
            try:
                create_mechanic(
                    conn,
                    name=request.POST.get('name', ''),
                    trade=request.POST.get('trade', 'General'),
                    shift=request.POST.get('shift', 'Day'),
                    phone=request.POST.get('phone', ''),
                    status=request.POST.get('status', 'Active'),
                    notes=request.POST.get('notes', ''),
                    created_by=request.session.get('user_email', ''),
                )
                conn.commit()
                return redirect('maint_mechanics_list')
            except Exception as e:
                conn.rollback()
                error = str(e)
                mechanics = list_mechanics(conn, status=status_filter or None,
                                           search=search or None)
    finally:
        conn.close()
    return render(request, 'maint_mechanics_list.html', _maint_ctx(
        request, mechanics=mechanics, status_filter=status_filter,
        search=search, mechanic_statuses=MECHANIC_STATUSES,
        mechanic_trades=MECHANIC_TRADES, mechanic_shifts=MECHANIC_SHIFTS,
        error=error, success=success,
    ))


def maint_mechanic_detail(request, mech_id):
    denied = _maint_access(request)
    if denied:
        return denied
    can_edit = request.session.get('user_role') not in READ_ONLY_ROLES
    conn = get_db_connection()
    error = success = None
    mechanic = None
    try:
        mechanic = get_mechanic(conn, mech_id)
        if not mechanic:
            return redirect('maint_mechanics_list')
        if request.method == 'POST' and can_edit:
            try:
                update_mechanic(
                    conn, mech_id,
                    name=request.POST.get('name', ''),
                    trade=request.POST.get('trade', ''),
                    shift=request.POST.get('shift', ''),
                    phone=request.POST.get('phone', ''),
                    status=request.POST.get('status', ''),
                    notes=request.POST.get('notes', ''),
                )
                conn.commit()
                mechanic = get_mechanic(conn, mech_id)
                success = 'Mechanic updated.'
            except Exception as e:
                conn.rollback()
                error = str(e)
    finally:
        conn.close()
    return render(request, 'maint_mechanic_detail.html', _maint_ctx(
        request, mechanic=mechanic, can_edit=can_edit,
        mechanic_statuses=MECHANIC_STATUSES,
        mechanic_trades=MECHANIC_TRADES, mechanic_shifts=MECHANIC_SHIFTS,
        error=error, success=success,
    ))


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

_PAYROLL_DEPT_KEYS = {'payroll', 'accounting', 'finance'}


def _payroll_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_full_access'):
        return None
    dept = request.session.get('user_dept_key', '')
    if dept not in _PAYROLL_DEPT_KEYS:
        return redirect('dashboard')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('dashboard')
    return None


def _payroll_ctx(request, **extra):
    return {
        'email': request.session.get('user_email', ''),
        'user_role': request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'can_edit': (
            request.session.get('user_full_access')
            or request.session.get('user_dept_key') in _PAYROLL_DEPT_KEYS
        ) and request.session.get('user_role') not in READ_ONLY_ROLES,
        **extra,
    }


def payroll_dashboard(request):
    block = _payroll_access(request)
    if block:
        return block
    conn = get_db_connection()
    try:
        counts = payroll_get_dashboard_counts(conn)
        runs = list_payroll_runs(conn)[:5]
    finally:
        conn.close()
    return render(request, 'payroll_dashboard.html', _payroll_ctx(
        request, counts=counts, recent_runs=runs,
    ))


def payroll_pay_rates(request):
    block = _payroll_access(request)
    if block:
        return block
    can_edit = _payroll_ctx(request)['can_edit']
    search = request.GET.get('search', '').strip()
    success = error = ''

    if request.method == 'POST' and can_edit:
        action = request.POST.get('action', '')
        conn = get_db_connection()
        try:
            if action == 'upsert':
                pid = int(request.POST.get('people_id', 0))
                pay_type = request.POST.get('pay_type', 'hourly')
                try:
                    pay_rate = float(request.POST.get('pay_rate', '0') or '0')
                except ValueError:
                    pay_rate = 0.0
                eff_date = request.POST.get('effective_date', '').strip()
                upsert_pay_rate(conn, pid, pay_type, pay_rate, eff_date)
                conn.commit()
                success = 'Pay rate saved.'
            elif action == 'delete':
                pid = int(request.POST.get('people_id', 0))
                delete_pay_rate(conn, pid)
                conn.commit()
                success = 'Pay rate removed.'
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    conn = get_db_connection()
    try:
        employees = list_pay_rates(conn, search=search or None)
        people = payroll_load_people(conn)
    finally:
        conn.close()
    return render(request, 'payroll_pay_rates.html', _payroll_ctx(
        request, employees=employees, people=people,
        pay_types=PAY_TYPES, search=search,
        success=success, error=error,
    ))


def payroll_deductions(request):
    block = _payroll_access(request)
    if block:
        return block
    can_edit = _payroll_ctx(request)['can_edit']
    people_filter = request.GET.get('people_id', '').strip()
    success = error = ''

    if request.method == 'POST' and can_edit:
        action = request.POST.get('action', '')
        conn = get_db_connection()
        try:
            if action == 'create_type':
                name = request.POST.get('name', '').strip()
                cat = request.POST.get('category', 'Other')
                is_pre = request.POST.get('is_pre_tax') == '1'
                create_deduction_type(conn, name, cat, is_pre)
                conn.commit()
                success = 'Deduction type added.'
            elif action == 'update_type':
                did = int(request.POST.get('ded_id', 0))
                name = request.POST.get('name', '').strip()
                cat = request.POST.get('category', 'Other')
                is_pre = request.POST.get('is_pre_tax') == '1'
                is_act = request.POST.get('is_active') == '1'
                update_deduction_type(conn, did, name, cat, is_pre, is_act)
                conn.commit()
                success = 'Deduction type updated.'
            elif action == 'assign':
                pid = int(request.POST.get('people_id', 0))
                tid = int(request.POST.get('deduction_type_id', 0))
                method = request.POST.get('calc_method', 'flat')
                try:
                    amt = float(request.POST.get('amount', '0') or '0')
                except ValueError:
                    amt = 0.0
                is_act = request.POST.get('is_active', '1') == '1'
                notes = request.POST.get('notes', '')
                create_employee_deduction(conn, pid, tid, method, amt, is_act, notes)
                conn.commit()
                success = 'Deduction assigned.'
            elif action == 'remove_assign':
                eid = int(request.POST.get('emp_ded_id', 0))
                delete_employee_deduction(conn, eid)
                conn.commit()
                success = 'Assignment removed.'
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    conn = get_db_connection()
    try:
        ded_types = list_deduction_types(conn)
        active_types = list_deduction_types(conn, active_only=True)
        pid = int(people_filter) if people_filter else None
        emp_deds = list_employee_deductions(conn, people_id=pid)
        people = payroll_load_people(conn)
    finally:
        conn.close()
    return render(request, 'payroll_deductions.html', _payroll_ctx(
        request, ded_types=ded_types, active_types=active_types,
        emp_deds=emp_deds, people=people,
        ded_categories=DED_CATEGORIES, ded_methods=DED_METHODS,
        people_filter=people_filter,
        success=success, error=error,
    ))


def payroll_history(request):
    block = _payroll_access(request)
    if block:
        return block
    conn = get_db_connection()
    try:
        runs = list_payroll_runs(conn)
    finally:
        conn.close()
    return render(request, 'payroll_history.html', _payroll_ctx(
        request, runs=runs,
    ))


def payroll_run_detail(request, run_id):
    block = _payroll_access(request)
    if block:
        return block
    conn = get_db_connection()
    try:
        run = get_payroll_run(conn, run_id)
        if not run:
            return redirect('/payroll/history/')
        entries = get_run_entries(conn, run_id)
    finally:
        conn.close()
    total_gross = sum(e.get('gross_pay') or 0 for e in entries)
    total_net   = sum(e.get('net_pay') or 0 for e in entries)
    return render(request, 'payroll_run_detail.html', _payroll_ctx(
        request, run=run, entries=entries,
        total_gross=total_gross, total_net=total_net,
    ))


def payroll_stub_detail(request, entry_id):
    block = _payroll_access(request)
    if block:
        return block
    conn = get_db_connection()
    try:
        stub = get_pay_stub(conn, entry_id)
        if not stub:
            return redirect('/payroll/history/')
        deds = get_stub_deductions(conn, entry_id)
    finally:
        conn.close()
    pre_tax  = [d for d in deds if d.get('is_pre_tax')]
    post_tax = [d for d in deds if not d.get('is_pre_tax')]
    total_tax = (
        (stub.get('federal_tax') or 0)
        + (stub.get('state_tax') or 0)
        + (stub.get('social_security') or 0)
        + (stub.get('medicare') or 0)
    )
    return render(request, 'payroll_stub_detail.html', _payroll_ctx(
        request, stub=stub, pre_tax=pre_tax, post_tax=post_tax,
        total_tax=total_tax,
        ss_rate=SS_RATE, medicare_rate=MEDICARE_RATE,
    ))


def payroll_ytd(request):
    block = _payroll_access(request)
    if block:
        return block
    import datetime as _dt
    cur_year = _dt.date.today().year
    try:
        year = int(request.GET.get('year', cur_year))
    except ValueError:
        year = cur_year
    people_id_str = request.GET.get('people_id', '').strip()
    pid = int(people_id_str) if people_id_str else None

    conn = get_db_connection()
    try:
        rows = get_ytd(conn, year, pid)
        people = payroll_load_people(conn)
    finally:
        conn.close()

    totals = {k: 0.0 for k in
              ('reg_hrs', 'ot_hrs', 'gross', 'pre_deds',
               'fed', 'state_tax', 'ss', 'medicare', 'net')}
    run_count_total = 0
    for r in rows:
        for k in totals:
            totals[k] += r.get(k) or 0.0
        run_count_total += r.get('run_count') or 0

    years = list(range(cur_year, cur_year - 6, -1))
    return render(request, 'payroll_ytd.html', _payroll_ctx(
        request, rows=rows, totals=totals,
        run_count_total=run_count_total,
        year=year, years=years,
        people=people, people_id=pid,
    ))


from .accounting_core import (
    INVOICE_STATUSES, PAYMENT_METHODS, ACCOUNT_TYPES, DEBIT_NORMAL,
    load_vendors, load_customers,
    get_ap_dashboard, list_ap_invoices, get_ap_invoice,
    create_ap_invoice, update_ap_invoice, set_ap_status,
    list_ap_payments, record_ap_payment,
    get_ar_dashboard, list_ar_invoices, get_ar_invoice,
    create_ar_invoice, update_ar_invoice, set_ar_status,
    list_ar_payments, record_ar_payment,
    list_accounts, get_account, create_account, update_account, account_balance,
    list_journals, get_journal, get_journal_lines,
    create_journal, post_journal, void_journal,
    trial_balance, income_statement, balance_sheet,
)

_ACCOUNTING_DEPT_KEYS = {'accounting', 'finance'}


def _acct_access(request, write=False):
    email = request.session.get('user_email')
    if not email:
        return redirect('/')
    role = request.session.get('user_role', '')
    if role in FULL_ACCESS_ROLES:
        return None
    dept = request.session.get('user_dept', '')
    if dept not in _ACCOUNTING_DEPT_KEYS:
        return redirect('/dashboard/')
    if write and role in READ_ONLY_ROLES:
        return redirect('/dashboard/')
    return None


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

def ap_list(request):
    block = _acct_access(request)
    if block:
        return block
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        block = _acct_access(request, write=True)
        if block:
            conn.close()
            return block
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


def ap_invoice_detail(request, inv_id=None):
    block = _acct_access(request)
    if block:
        return block
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        block = _acct_access(request, write=True)
        if block:
            conn.close()
            return block
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
    conn.close()
    if inv_id and not invoice:
        return redirect('/ap/')
    ctx = _acct_ctx(request,
        invoice=invoice, payments=payments, vendors=vendors,
        statuses=INVOICE_STATUSES, payment_methods=PAYMENT_METHODS,
        inv_id=inv_id, success=success, error=error,
    )
    return render(request, 'ap_invoice_detail.html', ctx)


# ── Accounts Receivable ─────────────────────────────────────────────────────

def ar_list(request):
    block = _acct_access(request)
    if block:
        return block
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        block = _acct_access(request, write=True)
        if block:
            conn.close()
            return block
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


def ar_invoice_detail(request, inv_id=None):
    block = _acct_access(request)
    if block:
        return block
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        block = _acct_access(request, write=True)
        if block:
            conn.close()
            return block
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
    conn.close()
    if inv_id and not invoice:
        return redirect('/ar/')
    ctx = _acct_ctx(request,
        invoice=invoice, payments=payments, customers=customers,
        statuses=INVOICE_STATUSES, payment_methods=PAYMENT_METHODS,
        inv_id=inv_id, success=success, error=error,
    )
    return render(request, 'ar_invoice_detail.html', ctx)


# ── General Ledger ───────────────────────────────────────────────────────────

def gl_dashboard(request):
    block = _acct_access(request)
    if block:
        return block
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


def gl_accounts(request):
    block = _acct_access(request)
    if block:
        return block
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        block = _acct_access(request, write=True)
        if block:
            conn.close()
            return block
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


def gl_journals(request):
    block = _acct_access(request)
    if block:
        return block
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


def gl_journal_detail(request, journal_id=None):
    block = _acct_access(request)
    if block:
        return block
    conn = get_db_connection()
    success = error = ''
    if request.method == 'POST':
        action = request.POST.get('action', '')
        try:
            if action == 'create':
                block = _acct_access(request, write=True)
                if block:
                    conn.close()
                    return block
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
                block = _acct_access(request, write=True)
                if block:
                    conn.close()
                    return block
                post_journal(conn, journal_id)
                conn.commit()
                success = 'Journal entry posted.'
            elif action == 'void' and journal_id:
                block = _acct_access(request, write=True)
                if block:
                    conn.close()
                    return block
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


def gl_trial_balance(request):
    block = _acct_access(request)
    if block:
        return block
    conn = get_db_connection()
    as_of = request.GET.get('as_of', '')
    result = trial_balance(conn, as_of=as_of or None)
    conn.close()
    ctx = _acct_ctx(request, as_of=as_of, **result)
    return render(request, 'gl_trial_balance.html', ctx)


def gl_income_statement(request):
    block = _acct_access(request)
    if block:
        return block
    import datetime as _dt
    today = _dt.date.today()
    date_from = request.GET.get('date_from', f'{today.year}-01-01')
    date_to   = request.GET.get('date_to', today.isoformat())
    conn = get_db_connection()
    result = income_statement(conn, date_from, date_to)
    conn.close()
    ctx = _acct_ctx(request, date_from=date_from, date_to=date_to, **result)
    return render(request, 'gl_income_statement.html', ctx)


def gl_balance_sheet(request):
    block = _acct_access(request)
    if block:
        return block
    as_of = request.GET.get('as_of', '')
    conn = get_db_connection()
    result = balance_sheet(conn, as_of=as_of or None)
    conn.close()
    ctx = _acct_ctx(request, as_of=as_of, **result)
    return render(request, 'gl_balance_sheet.html', ctx)


from .engineering_core import (
    PROJECT_STATUSES, TASK_STATUSES, ECR_STATUSES, PRIORITIES,
    load_products, load_people,
    get_eng_dashboard, next_project_number, next_ecr_number,
    list_projects, get_project, create_project, update_project,
    list_project_tasks, create_task, update_task, get_task,
    list_ecrs, get_ecr, create_ecr, update_ecr, set_ecr_status,
    eng_reports as _eng_reports_data,
)

_ENGINEERING_DEPT_KEYS = {'engineering'}


def _eng_access(request, write=False):
    if request.session.get('user_role') in FULL_ACCESS_ROLES:
        return None
    dept = request.session.get('user_dept', '')
    if dept not in _ENGINEERING_DEPT_KEYS:
        return redirect('/dashboard/')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('/dashboard/')
    return None


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


def eng_dashboard(request):
    block = _eng_access(request)
    if block:
        return block
    with get_db_connection() as conn:
        dash = get_eng_dashboard(conn)
        recent_projects = list_projects(conn)[:8]
        recent_ecrs = list_ecrs(conn)[:8]
    ctx = _eng_ctx(request, dash=dash,
                   recent_projects=recent_projects, recent_ecrs=recent_ecrs)
    return render(request, 'eng_dashboard.html', ctx)


def eng_projects(request):
    block = _eng_access(request)
    if block:
        return block
    status = request.GET.get('status', '')
    engineer = request.GET.get('engineer', '')
    search = request.GET.get('search', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST' and request.POST.get('action') == 'new':
            block2 = _eng_access(request, write=True)
            if block2:
                return block2
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


def eng_project_detail(request, project_id=None):
    block = _eng_access(request)
    if block:
        return block
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            block2 = _eng_access(request, write=True)
            if block2:
                return block2
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


def eng_ecrs(request):
    block = _eng_access(request)
    if block:
        return block
    status = request.GET.get('status', '')
    proj_filter = request.GET.get('project_id', '')
    search = request.GET.get('search', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST' and request.POST.get('action') == 'new':
            block2 = _eng_access(request, write=True)
            if block2:
                return block2
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


def eng_ecr_detail(request, ecr_id=None):
    block = _eng_access(request)
    if block:
        return block
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            block2 = _eng_access(request, write=True)
            if block2:
                return block2
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


def eng_reports_view(request):
    block = _eng_access(request)
    if block:
        return block
    with get_db_connection() as conn:
        data = _eng_reports_data(conn)
    ctx = _eng_ctx(request, **data)
    return render(request, 'eng_reports.html', ctx)

from .sales_core import (
    SO_STATUSES, SO_STATUS_ACTION_LABELS,
    allowed_transitions, can_transition, customer_label,
    next_so_number, list_sos, get_so, get_so_items,
    load_customers, load_products,
    create_so, update_so, add_so_item, delete_so_item, set_so_status,
    QUOTE_STATUSES, TARGET_STATUSES,
    get_sales_dashboard,
    list_quotes, get_quote, create_quote, update_quote, set_quote_status,
    list_targets, create_target, update_target,
)

_SALES_DEPT_KEYS = {'sales'}


def _sales_access(request, write=False):
    if request.session.get('user_role') in FULL_ACCESS_ROLES:
        return None
    dept = request.session.get('user_dept', '')
    if dept not in _SALES_DEPT_KEYS:
        return redirect('/dashboard/')
    if write and request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('/dashboard/')
    return None


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


def sales_dashboard(request):
    block = _sales_access(request)
    if block:
        return block
    with get_db_connection() as conn:
        dash = get_sales_dashboard(conn)
        recent_orders = list_sos(conn)[:8]
        recent_quotes = list_quotes(conn)[:8]
    ctx = _sales_ctx(request, dash=dash,
                     recent_orders=recent_orders, recent_quotes=recent_quotes)
    return render(request, 'sales_dashboard.html', ctx)


def sales_orders_list(request):
    block = _sales_access(request)
    if block:
        return block
    status = request.GET.get('status', '')
    customer_id = request.GET.get('customer_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST' and request.POST.get('action') == 'new':
            block2 = _sales_access(request, write=True)
            if block2:
                return block2
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


def sales_order_detail(request, so_id=None):
    block = _sales_access(request)
    if block:
        return block
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            block2 = _sales_access(request, write=True)
            if block2:
                return block2
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


def sales_quotes(request):
    block = _sales_access(request)
    if block:
        return block
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            block2 = _sales_access(request, write=True)
            if block2:
                return block2
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


def sales_targets(request):
    block = _sales_access(request)
    if block:
        return block
    rep_filter = request.GET.get('rep', '')
    period_filter = request.GET.get('period', '')
    error = success = ''
    with get_db_connection() as conn:
        if request.method == 'POST':
            block2 = _sales_access(request, write=True)
            if block2:
                return block2
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

from .production_core import get_production_dashboard
from .purchasing_core import get_purchasing_dashboard
from .finance_core import get_finance_dashboard


def _prod_access(request, write=False):
    if not request.session.get('user_email'):
        return redirect('/')
    role = request.session.get('user_role', '')
    dept = request.session.get('user_dept', '')
    if role in FULL_ACCESS_ROLES:
        return None
    if dept != 'production':
        return redirect('/dashboard/')
    if write and role in READ_ONLY_ROLES:
        return redirect('/prod/')
    return None


def _prod_ctx(request, **extra):
    role = request.session.get('user_role', '')
    return {
        'email': request.session.get('user_email', ''),
        'user_role': role,
        'full_access': role in FULL_ACCESS_ROLES,
        'can_edit': role not in READ_ONLY_ROLES,
        **extra,
    }


def prod_dashboard(request):
    err = _prod_access(request)
    if err:
        return err
    with get_db_connection() as conn:
        data = get_production_dashboard(conn)
    ctx = _prod_ctx(request, **data)
    return render(request, 'prod_dashboard.html', ctx)


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


def purch_dashboard(request):
    err = _po_access(request)
    if err:
        return err
    with get_db_connection() as conn:
        data = get_purchasing_dashboard(conn)
    ctx = _purch_ctx(request, **data)
    return render(request, 'purchasing_dashboard.html', ctx)


# ---------------------------------------------------------------------------
# Personnel dashboard
# ---------------------------------------------------------------------------

def pers_dashboard(request):
    err = _people_access(request)
    if err:
        return err
    with get_db_connection() as conn:
        data = get_personnel_dashboard(conn)
    ctx = _people_context(request, **data)
    return render(request, 'personnel_dashboard.html', ctx)


# ---------------------------------------------------------------------------
# Customer Service dashboard
# ---------------------------------------------------------------------------

def cs_dashboard_view(request):
    err = _cs_access(request)
    if err:
        return err
    with get_db_connection() as conn:
        stats = get_summary_stats(conn)
        recent_tickets = list_tickets(conn)[:8]
    ctx = _cs_context(request, stats=stats, recent_tickets=recent_tickets)
    return render(request, 'cs_dashboard.html', ctx)


# ---------------------------------------------------------------------------
# Finance dashboard
# ---------------------------------------------------------------------------

def fin_dashboard(request):
    err = _acct_access(request)
    if err:
        return err
    with get_db_connection() as conn:
        data = get_finance_dashboard(conn)
    ctx = _acct_ctx(request, **data)
    return render(request, 'finance_dashboard.html', ctx)

