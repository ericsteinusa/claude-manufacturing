"""Menu tree data and navigation helpers.

``MENU_TREE`` describes the department / sub-menu hierarchy rendered by the
dashboard and menu views, and the lookup tables that map departments to it.
"""

from django.utils.translation import gettext_lazy as _

# Each item: (key, label, target)
# target is a script filename (str = leaf) or a dict (sub-menu node).

_TIME_CLOCK_MENU = {
    'title': _('Time Clock Menu'),
    'items': [
        ('clock_in_out', _('Clock In/Out'), {
            'title': _('Clock In/Out'),
            'items': [
                ('punch_in', _('Record Clock In'), ''),
                ('punch_out', _('Record Clock Out'), ''),
                ('cur_status', _('Current Status'), ''),
            ],
        }),
        ('view_hours', _('View Hours'), {
            'title': _('View Hours'),
            'items': [
                ('today_hrs', _("Today's Hours"), ''),
                ('week_hrs', _('Weekly Hours'), ''),
                ('month_hrs', _('Monthly Hours'), ''),
                ('period_hrs', _('Pay Period Hours'), ''),
            ],
        }),
        ('time_off', _('Time Off Requests'), {
            'title': _('Time Off Requests'),
            'items': [
                ('submit_req', _('Submit Request'), ''),
                ('pend_req', _('Pending Requests'), ''),
                ('appr_req', _('Approved Requests'), ''),
                ('req_hist', _('Request History'), ''),
            ],
        }),
        ('schedules', _('Schedules'), {
            'title': _('Schedules'),
            'items': [
                ('my_sched', _('My Schedule'), ''),
                ('upcoming', _('Upcoming Shifts'), ''),
                ('sched_cal', _('Schedule Calendar'), ''),
                ('swap_req', _('Swap Requests'), ''),
            ],
        }),
        ('ot_reports', _('Overtime Reports'), {
            'title': _('Overtime Reports'),
            'items': [
                ('cur_ot', _('Current Period OT'), ''),
                ('hist_ot', _('Historical OT'), ''),
                ('ot_by_emp', _('OT by Employee'), ''),
                ('ot_appr', _('OT Approval'), ''),
            ],
        }),
        ('attend_reports', _('Attendance Reports'), {
            'title': _('Attendance Reports'),
            'items': [
                ('daily_att', _('Daily Attendance'), ''),
                ('month_sum', _('Monthly Summary'), ''),
                ('tard_rpt', _('Tardiness Report'), ''),
                ('abs_rpt', _('Absence Report'), ''),
            ],
        }),
        ('shift_mgmt', _('Shift Management'), {
            'title': _('Shift Management'),
            'items': [
                ('view_shfts', _('View Shifts'), ''),
                ('assign_emp', _('Assign Employees'), ''),
                ('shft_tmpl', _('Shift Templates'), ''),
                ('swap_mgmt', _('Swap Management'), ''),
            ],
        }),
    ],
}

_MAINT_MENU = {
    'title': _('Maintenance Menu'),
    'items': [
        ('work_orders', _('Work Orders'), {
            'title': _('Work Orders'),
            'items': [
                ('create_wo', _('Create Work Order'), ''),
                ('open_wo', _('Open Work Orders'), ''),
                ('inprog_wo', _('In Progress'), ''),
                ('comp_wo', _('Completed'), ''),
            ],
        }),
        ('maint_schedule', _('Maintenance Schedule'), {
            'title': _('Maintenance Schedule'),
            'items': [
                ('daily_sched', _('Daily Schedule'), ''),
                ('week_sched', _('Weekly Schedule'), ''),
                ('month_sched', _('Monthly Schedule'), ''),
                ('annual_plan', _('Annual Plan'), ''),
            ],
        }),
        ('equip_maint', _('Equipment Maintenance'), {
            'title': _('Equipment Maintenance'),
            'items': [
                ('equip_list', _('Equipment List'), ''),
                ('maint_hist', _('Maintenance History'), ''),
                ('svc_records', _('Service Records'), ''),
                ('equip_stat', _('Equipment Status'), ''),
            ],
        }),
        ('parts_inv', _('Parts Inventory'), {
            'title': _('Parts Inventory'),
            'items': [
                ('view_inv', _('View Inventory'), ''),
                ('parts_req', _('Parts Request'), ''),
                ('reorder', _('Reorder List'), ''),
                ('parts_hist', _('Parts History'), ''),
            ],
        }),
        ('maint_reports', _('Maintenance Reports'), {
            'title': _('Maintenance Reports'),
            'items': [
                ('daily_rpt', _('Daily Report'), ''),
                ('week_rpt', _('Weekly Report'), ''),
                ('cost_analy', _('Cost Analysis'), ''),
                ('down_rpt', _('Downtime Report'), ''),
            ],
        }),
        ('safety_insp', _('Safety Inspections'), {
            'title': _('Safety Inspections'),
            'items': [
                ('sched_insp', _('Schedule Inspection'), ''),
                ('insp_chk', _('Inspection Checklist'), ''),
                ('insp_res', _('Inspection Results'), ''),
                ('corr_act', _('Corrective Actions'), ''),
            ],
        }),
        ('prev_maint', _('Preventive Maintenance'), {
            'title': _('Preventive Maintenance'),
            'items': [
                ('pm_sched', _('PM Schedule'), ''),
                ('pm_chk', _('PM Checklists'), ''),
                ('pm_hist', _('PM History'), ''),
                ('pm_rpts', _('PM Reports'), ''),
            ],
        }),
    ],
}

_MKT_MENU = {
    'title': _('Marketing Menu'),
    'items': [
        ('campaigns', _('Campaigns'), {
            'title': _('Campaigns'),
            'items': [
                ('act_camp', _('Active Campaigns'), ''),
                ('new_camp', _('Create Campaign'), ''),
                ('camp_cal', _('Campaign Calendar'), ''),
                ('camp_res', _('Campaign Results'), ''),
            ],
        }),
        ('mkt_research', _('Market Research'), {
            'title': _('Market Research'),
            'items': [
                ('res_proj', _('Research Projects'), ''),
                ('comp_analy', _('Competitor Analysis'), ''),
                ('surv_mgmt', _('Survey Management'), ''),
                ('mkt_trends', _('Market Trends'), ''),
            ],
        }),
        ('advertising', _('Advertising'), {
            'title': _('Advertising'),
            'items': [
                ('ad_mgmt', _('Ad Management'), ''),
                ('ad_budget', _('Ad Budget'), ''),
                ('ad_perf', _('Ad Performance'), ''),
                ('ad_cal', _('Ad Calendar'), ''),
            ],
        }),
        ('analytics', _('Analytics'), {
            'title': _('Analytics'),
            'items': [
                ('web_analy', _('Website Analytics'), ''),
                ('camp_analy', _('Campaign Analytics'), ''),
                ('sales_analy', _('Sales Analytics'), ''),
                ('cust_rpts', _('Custom Reports'), ''),
            ],
        }),
        ('content_mgmt', _('Content Management'), {
            'title': _('Content Management'),
            'items': [
                ('cont_cal', _('Content Calendar'), ''),
                ('blog', _('Blog Posts'), ''),
                ('mkt_mat', _('Marketing Materials'), ''),
                ('cont_arch', _('Content Archive'), ''),
            ],
        }),
        ('social_media', _('Social Media'), {
            'title': _('Social Media'),
            'items': [
                ('post_mgmt', _('Post Management'), ''),
                ('social_cal', _('Social Calendar'), ''),
                ('eng_rpts', _('Engagement Reports'), ''),
                ('acct_mgmt', _('Account Management'), ''),
            ],
        }),
        ('email_mkt', _('Email Marketing'), {
            'title': _('Email Marketing'),
            'items': [
                ('email_camp', _('Email Campaigns'), ''),
                ('sub_lists', _('Subscriber Lists'), ''),
                ('email_tmpl', _('Email Templates'), ''),
                ('email_analy', _('Email Analytics'), ''),
            ],
        }),
    ],
}

_SALES_MENU = {
    'title': _('Sales Menu'),
    'items': [
        ('sales_orders', _('Sales Orders'), {
            'title': _('Sales Orders'),
            'items': [
                ('new_order', _('New Order'), ''),
                ('open_orders', _('Open Orders'), ''),
                ('order_hist', _('Order History'), ''),
                ('order_stat', _('Order Status'), ''),
            ],
        }),
        ('cust_accounts', _('Customer Accounts'), {
            'title': _('Customer Accounts'),
            'items': [
                ('acct_list', _('Account List'), ''),
                ('new_acct', _('New Account'), ''),
                ('acct_det', _('Account Details'), ''),
                ('acct_hist', _('Account History'), ''),
            ],
        }),
        ('sales_reports', _('Sales Reports'), {
            'title': _('Sales Reports'),
            'items': [
                ('daily_sales', _('Daily Sales'), ''),
                ('month_sales', _('Monthly Sales'), ''),
                ('annual_rpt', _('Annual Report'), ''),
                ('by_rep', _('Sales by Rep'), ''),
            ],
        }),
        ('quotes', _('Quotes'), {
            'title': _('Quotes'),
            'items': [
                ('new_quote', _('Create Quote'), ''),
                ('act_quotes', _('Active Quotes'), ''),
                ('quote_hist', _('Quote History'), ''),
                ('conv_order', _('Convert to Order'), ''),
            ],
        }),
        ('leads', _('Leads & Opportunities'), {
            'title': _('Leads & Opportunities'),
            'items': [
                ('new_lead', _('New Lead'), ''),
                ('act_leads', _('Active Leads'), ''),
                ('opp_pipe', _('Opportunities Pipeline'), ''),
                ('lead_rpts', _('Lead Reports'), ''),
            ],
        }),
        ('contracts', _('Contracts'), {
            'title': _('Contracts'),
            'items': [
                ('act_cont', _('Active Contracts'), ''),
                ('new_cont', _('Create Contract'), ''),
                ('cont_renew', _('Contract Renewals'), ''),
                ('cont_arch', _('Contract Archive'), ''),
            ],
        }),
        ('forecasting', _('Sales Forecasting'), {
            'title': _('Sales Forecasting'),
            'items': [
                ('cur_fore', _('Current Forecast'), ''),
                ('fore_rep', _('Forecast by Rep'), ''),
                ('fore_prod', _('Forecast by Product'), ''),
                ('fore_rpts', _('Forecast Reports'), ''),
            ],
        }),
    ],
}

_PROD_MENU = {
    'title': _('Production Menu'),
    'items': [
        ('work_orders', _('Work Orders'), {
            'title': _('Work Orders'),
            'items': [
                ('create_wo', _('Create Work Order'), ''),
                ('open_wo', _('Open Work Orders'), ''),
                ('inprog_wo', _('In Progress'), ''),
                ('comp_wo', _('Completed'), ''),
            ],
        }),
        ('mrp', _('MRP Planning'), {
            'title': _('Material Requirements Planning'),
            'items': [
                ('mrp_home', _('MRP Home'), ''),
                ('run_mrp', _('Run MRP Plan'), ''),
                ('mrp_demand', _('View Demand'), ''),
                ('mrp_rpts', _('MRP Reports'), ''),
            ],
        }),
        ('prod_schedule', _('Production Schedule'), {
            'title': _('Production Schedule'),
            'items': [
                ('daily_sched', _('Daily Schedule'), ''),
                ('week_sched', _('Weekly Schedule'), ''),
                ('month_sched', _('Monthly Schedule'), ''),
                ('sched_cal', _('Schedule Calendar'), ''),
                ('gantt_sched', _('Gantt Chart'), ''),
            ],
        }),
        ('inventory', _('Inventory'), {
            'title': _('Inventory'),
            'items': [
                ('raw_mat', _('Raw Materials'), ''),
                ('fin_goods', _('Finished Goods'), ''),
                ('wip_inv', _('WIP Inventory'), ''),
                ('inv_rpts', _('Inventory Reports'), ''),
                ('cost_valuation', _('FIFO/LIFO/Avg Valuation'), ''),
            ],
        }),
        ('equip_status', _('Equipment Status'), {
            'title': _('Equipment Status'),
            'items': [
                ('equip_list', _('Equipment List'), ''),
                ('stat_dash', _('Status Dashboard'), ''),
                ('down_log', _('Downtime Log'), ''),
                ('maint_req', _('Maintenance Requests'), ''),
            ],
        }),
        ('quality_ctrl', _('Quality Control'), {
            'title': _('Quality Control'),
            'items': [
                ('insp_res', _('Inspection Results'), ''),
                ('non_conf', _('Non-Conformances'), ''),
                ('qc_rpts', _('QC Reports'), ''),
                ('rej_analy', _('Reject Analysis'), ''),
            ],
        }),
        ('prod_reports', _('Production Reports'), {
            'title': _('Production Reports'),
            'items': [
                ('daily_prod', _('Daily Production'), ''),
                ('week_sum', _('Weekly Summary'), ''),
                ('eff_rpt', _('Efficiency Report'), ''),
                ('scrap_rpt', _('Scrap Report'), ''),
            ],
        }),
        ('labor_tracking', _('Labor Tracking'), {
            'title': _('Labor Tracking'),
            'items': [
                ('cur_labor', _('Current Labor'), ''),
                ('labor_shft', _('Labor by Shift'), ''),
                ('labor_job', _('Labor by Job'), ''),
                ('labor_rpts', _('Labor Reports'), ''),
            ],
        }),
    ],
}

_SHIP_MENU = {
    'title': _('Shipping Department'),
    'items': [
        ('ship_orders', _('Shipment Orders'), {
            'title': _('Shipment Orders'),
            'items': [
                ('new_ship', _('New Shipment'), ''),
                ('pend_ship', _('Pending Shipments'), ''),
                ('shipped', _('Shipped Orders'), ''),
                ('deliv_conf', _('Delivery Confirmation'), ''),
            ],
        }),
        ('ship_schedule', _('Shipping Schedule'), {
            'title': _('Shipping Schedule'),
            'items': [
                ('today_sched', _("Today's Schedule"), ''),
                ('week_sched', _('Weekly Schedule'), ''),
                ('sched_cal', _('Schedule Calendar'), ''),
                ('rush_orders', _('Rush Orders'), ''),
            ],
        }),
        ('receiving', _('Receiving'), {
            'title': _('Receiving'),
            'items': [
                ('inbound', _('Inbound Shipments'), ''),
                ('recv_items', _('Receive Items'), ''),
                ('recv_rpts', _('Receiving Reports'), ''),
                ('disc_rpts', _('Discrepancy Reports'), ''),
            ],
        }),
        ('carrier_mgmt', _('Carrier Management'), {
            'title': _('Carrier Management'),
            'items': [
                ('carr_list', _('Carrier List'), ''),
                ('carr_rates', _('Carrier Rates'), ''),
                ('perf_rpts', _('Performance Reports'), ''),
                ('carr_cont', _('Carrier Contracts'), ''),
            ],
        }),
        ('tracking', _('Tracking'), {
            'title': _('Tracking'),
            'items': [
                ('track_ship', _('Track Shipment'), ''),
                ('track_dash', _('Tracking Dashboard'), ''),
                ('deliv_stat', _('Delivery Status'), ''),
                ('exc_rpts', _('Exception Reports'), ''),
            ],
        }),
        ('ship_reports', _('Shipping Reports'), {
            'title': _('Shipping Reports'),
            'items': [
                ('daily_rpt', _('Daily Report'), ''),
                ('week_sum', _('Weekly Summary'), ''),
                ('cost_analy', _('Cost Analysis'), ''),
                ('perf_rpt', _('Performance Report'), ''),
            ],
        }),
        ('returns_proc', _('Returns Processing'), {
            'title': _('Returns Processing'),
            'items': [
                ('new_return', _('New Return'), ''),
                ('pend_ret', _('Pending Returns'), ''),
                ('ret_hist', _('Return History'), ''),
                ('ret_rpts', _('Return Reports'), ''),
            ],
        }),
        ('wms', _('Warehouse Management'), {
            'title': _('Warehouse Management'),
            'items': [
                ('warehouses', _('Warehouses'), ''),
                ('bin_master', _('Bin Master'), ''),
                ('putaway_rules', _('Put-Away Rules'), ''),
                ('pick_lists', _('Pick Lists'), ''),
                ('wave_picking', _('Wave Picking'), ''),
                ('pack_station', _('Pack Station'), ''),
                ('transfers', _('Warehouse Transfers'), ''),
                ('rfid_readers', _('RFID Readers'), ''),
                ('rfid_tags', _('RFID Tags'), ''),
            ],
        }),
    ],
}

_QA_LAB_MENU = {
    'title': _('QA Laboratory Menu'),
    'items': [
        ('test_requests', _('Test Requests'), {
            'title': _('Test Requests'),
            'items': [
                ('new_req', _('New Request'), ''),
                ('pend_req', _('Pending Requests'), ''),
                ('inprog_req', _('In Progress'), ''),
                ('comp_tests', _('Completed Tests'), ''),
            ],
        }),
        ('lab_results', _('Lab Results'), {
            'title': _('Lab Results'),
            'items': [
                ('recent_res', _('Recent Results'), ''),
                ('search_res', _('Search Results'), ''),
                ('failed', _('Failed Tests'), ''),
                ('res_rpts', _('Result Reports'), ''),
            ],
        }),
        ('insp_reports', _('Inspection Reports'), {
            'title': _('Inspection Reports'),
            'items': [
                ('create_rpt', _('Create Report'), ''),
                ('pend_rpts', _('Pending Reports'), ''),
                ('rpt_arch', _('Report Archive'), ''),
                ('rpt_sum', _('Report Summary'), ''),
            ],
        }),
        ('non_conformance', _('Non-Conformance'), {
            'title': _('Non-Conformance'),
            'items': [
                ('new_ncr', _('New NCR'), ''),
                ('open_ncrs', _('Open NCRs'), ''),
                ('ncr_hist', _('NCR History'), ''),
                ('ncr_rpts', _('NCR Reports'), ''),
            ],
        }),
        ('calibration', _('Calibration'), {
            'title': _('Calibration'),
            'items': [
                ('cal_sched', _('Calibration Schedule'), ''),
                ('cal_records', _('Calibration Records'), ''),
                ('overdue', _('Overdue Items'), ''),
                ('cal_rpts', _('Calibration Reports'), ''),
            ],
        }),
        ('sample_mgmt', _('Sample Management'), {
            'title': _('Sample Management'),
            'items': [
                ('recv_sample', _('Receive Sample'), ''),
                ('samp_track', _('Sample Tracking'), ''),
                ('samp_disp', _('Sample Disposal'), ''),
                ('samp_rpts', _('Sample Reports'), ''),
            ],
        }),
        ('lab_reports', _('Lab Reports'), {
            'title': _('Lab Reports'),
            'items': [
                ('daily_rpts', _('Daily Reports'), ''),
                ('week_sum', _('Weekly Summary'), ''),
                ('month_rpt', _('Monthly Report'), ''),
                ('cust_rpts', _('Custom Reports'), ''),
            ],
        }),
    ],
}

_QA_MENU = {
    'title': _('Quality Assurance Menu'),
    'items': [
        ('qa_lab', _('QA Laboratory Menu'), _QA_LAB_MENU),
    ],
}

_PERS_MENU = {
    'title': _('Personnel Menu'),
    'items': [
        ('pers_crm', _('Personnel CRM'), ''),
        ('reg_form', _('Registration Form'), ''),
        ('upd_pass', _('Update Password'), ''),
        ('disp_dept', _('Display Department'), ''),
        ('dept_entry', _('Dept Entry'), ''),
        ('dept_sub', _('Dept Sub Entry'), ''),
        ('time_clock', _('Time Clock'), _TIME_CLOCK_MENU),
        ('emp_records', _('Employee Records'), {
            'title': _('Employee Records'),
            'items': [
                ('view_recs', _('View Records'), ''),
                ('new_emp', _('New Employee'), ''),
                ('upd_rec', _('Update Record'), ''),
                ('emp_hist', _('Employment History'), ''),
            ],
        }),
        ('benefits', _('Benefits'), {
            'title': _('Benefits'),
            'items': [
                ('ben_enroll', _('Benefits Enrollment'), ''),
                ('ben_sum', _('Benefits Summary'), ''),
                ('cobra', _('COBRA Management'), ''),
                ('ben_rpts', _('Benefits Reports'), ''),
            ],
        }),
        ('perf_review', _('Performance Reviews'), {
            'title': _('Performance Reviews'),
            'items': [
                ('sched_rev', _('Schedule Review'), ''),
                ('pend_revs', _('Pending Reviews'), ''),
                ('rev_hist', _('Review History'), ''),
                ('perf_rpts', _('Performance Reports'), ''),
            ],
        }),
        ('disc_records', _('Disciplinary Records'), {
            'title': _('Disciplinary Records'),
            'items': [
                ('new_rec', _('New Record'), ''),
                ('view_recs', _('View Records'), ''),
                ('rec_hist', _('Record History'), ''),
                ('disc_rpts', _('Disciplinary Reports'), ''),
            ],
        }),
        ('training', _('Training & Development'), {
            'title': _('Training & Development'),
            'items': [
                ('train_cal', _('Training Calendar'), ''),
                ('train_recs', _('Training Records'), ''),
                ('course_mgmt', _('Course Management'), ''),
                ('cert_track', _('Certification Tracking'), ''),
            ],
        }),
        ('onboarding', _('Onboarding'), {
            'title': _('Onboarding'),
            'items': [
                ('hire_chk', _('New Hire Checklist'), ''),
                ('onb_stat', _('Onboarding Status'), ''),
                ('doc_coll', _('Document Collection'), ''),
                ('onb_rpts', _('Onboarding Reports'), ''),
            ],
        }),
    ],
}

_CS_MENU = {
    'title': _('Customer Service Menu'),
    'items': [
        ('cust_entry', _('Customer Entry Screen'), ''),
        ('open_tickets', _('Open Tickets'), {
            'title': _('Open Tickets'),
            'items': [
                ('all_tickets', _('View All Tickets'), ''),
                ('my_tickets', _('My Tickets'), ''),
                ('hi_pri', _('High Priority'), ''),
                ('tick_search', _('Ticket Search'), ''),
            ],
        }),
        ('cust_accounts', _('Customer Accounts'), {
            'title': _('Customer Accounts'),
            'items': [
                ('acct_list', _('Account List'), ''),
                ('new_acct', _('New Account'), ''),
                ('acct_det', _('Account Details'), ''),
                ('acct_hist', _('Account History'), ''),
            ],
        }),
        ('returns', _('Returns & Refunds'), {
            'title': _('Returns & Refunds'),
            'items': [
                ('new_return', _('New Return'), ''),
                ('pend_ret', _('Pending Returns'), ''),
                ('refund_proc', _('Refund Processing'), ''),
                ('ret_rpts', _('Returns Reports'), ''),
            ],
        }),
        ('knowledge_base', _('Knowledge Base'), {
            'title': _('Knowledge Base'),
            'items': [
                ('browse', _('Browse Articles'), ''),
                ('create_art', _('Create Article'), ''),
                ('art_mgmt', _('Article Management'), ''),
                ('kb_search', _('Search Knowledge Base'), ''),
            ],
        }),
        ('svc_reports', _('Service Reports'), {
            'title': _('Service Reports'),
            'items': [
                ('daily_rpt', _('Daily Report'), ''),
                ('week_sum', _('Weekly Summary'), ''),
                ('res_rpts', _('Resolution Reports'), ''),
                ('csat_rpts', _('Customer Satisfaction'), ''),
            ],
        }),
        ('surveys', _('Surveys & Feedback'), {
            'title': _('Surveys & Feedback'),
            'items': [
                ('act_surv', _('Active Surveys'), ''),
                ('new_surv', _('Create Survey'), ''),
                ('surv_res', _('Survey Results'), ''),
                ('feed_rpts', _('Feedback Reports'), ''),
            ],
        }),
    ],
}

_IT_TECH = {
    'title': _('IT Technician'),
    'items': [
        ('it_tasks', _('IT Tasks'), ''),
        ('help_desk', _('Help Desk Tickets'), {
            'title': _('Help Desk Tickets'),
            'items': [
                ('new_ticket', _('New Ticket'), ''),
                ('open_tick', _('Open Tickets'), ''),
                ('my_tickets', _('My Assigned Tickets'), ''),
                ('tick_hist', _('Ticket History'), ''),
            ],
        }),
        ('asset_mgmt', _('Asset Management'), {
            'title': _('Asset Management'),
            'items': [
                ('asset_inv', _('Asset Inventory'), ''),
                ('new_asset', _('New Asset'), ''),
                ('asset_hist', _('Asset History'), ''),
                ('disposition', _('Disposition'), ''),
            ],
        }),
        ('net_status', _('Network Status'), {
            'title': _('Network Status'),
            'items': [
                ('net_dash', _('Network Dashboard'), ''),
                ('bw_monitor', _('Bandwidth Monitor'), ''),
                ('net_map', _('Network Map'), ''),
                ('inc_log', _('Incident Log'), ''),
            ],
        }),
        ('sw_install', _('Software Installations'), {
            'title': _('Software Installations'),
            'items': [
                ('pend_inst', _('Pending Installs'), ''),
                ('sw_inv', _('Software Inventory'), ''),
                ('lic_mgmt', _('License Management'), ''),
                ('inst_hist', _('Installation History'), ''),
            ],
        }),
        ('hw_repairs', _('Hardware Repairs'), {
            'title': _('Hardware Repairs'),
            'items': [
                ('new_repair', _('New Repair Request'), ''),
                ('inprog', _('In Progress'), ''),
                ('comp_rep', _('Completed Repairs'), ''),
                ('rep_hist', _('Repair History'), ''),
            ],
        }),
        ('user_accts', _('User Account Management'), {
            'title': _('User Account Management'),
            'items': [
                ('create_acct', _('Create Account'), ''),
                ('reset_pw', _('Reset Password'), ''),
                ('acct_stat', _('Account Status'), ''),
                ('acct_audit', _('Account Audit'), ''),
            ],
        }),
    ],
}

_PURCH_MENU = {
    'title': _('Purchasing Menu'),
    'items': [
        ('prod_entry', _('Product Entry'), ''),
        ('sup_entry', _('Supplier Entry'), ''),
        ('purch_orders', _('Purchase Orders'), {
            'title': _('Purchase Orders'),
            'items': [
                ('new_po', _('New PO'), ''),
                ('open_pos', _('Open POs'), ''),
                ('po_status', _('PO Status'), ''),
                ('po_hist', _('PO History'), ''),
            ],
        }),
        ('vendor_mgmt', _('Vendor Management'), {
            'title': _('Vendor Management'),
            'items': [
                ('vend_list', _('Vendor List'), ''),
                ('new_vend', _('New Vendor'), ''),
                ('vend_perf', _('Vendor Performance'), ''),
                ('vend_cont', _('Vendor Contracts'), ''),
            ],
        }),
        ('purch_reports', _('Purchase Reports'), {
            'title': _('Purchase Reports'),
            'items': [
                ('spend_sum', _('Spending Summary'), ''),
                ('po_rpts', _('PO Reports'), ''),
                ('budg_act', _('Budget vs. Actual'), ''),
                ('cat_rpts', _('Category Reports'), ''),
            ],
        }),
        ('receiving', _('Receiving'), {
            'title': _('Receiving'),
            'items': [
                ('pend_recv', _('Pending Receipts'), ''),
                ('recv_items', _('Receive Items'), ''),
                ('disc_rpts', _('Discrepancy Reports'), ''),
                ('recv_hist', _('Receiving History'), ''),
            ],
        }),
        ('contracts', _('Contract Management'), {
            'title': _('Contract Management'),
            'items': [
                ('act_cont', _('Active Contracts'), ''),
                ('new_cont', _('New Contract'), ''),
                ('cont_renew', _('Contract Renewals'), ''),
                ('cont_arch', _('Contract Archive'), ''),
            ],
        }),
        ('requisitions', _('Requisitions'), {
            'title': _('Requisitions'),
            'items': [
                ('new_req', _('New Requisition'), ''),
                ('pend_appr', _('Pending Approval'), ''),
                ('appr_reqs', _('Approved Requisitions'),
                 ''),
                ('req_hist', _('Requisition History'),
                 ''),
            ],
        }),
    ],
}

MENU_TREE = {
    'accounting': {
        'title': _('Accounting Main Menu'),
        'items': [
            ('acct_pay', _('Accounts Payable'), ''),
            ('acct_mgr', _('Accounting Manager'), {
                'title': _('Accounting Manager'),
                'items': [
                    ('ap', _('Accounts Payable'), ''),
                    ('rcv', _('Accounts Receivable'), ''),
                    ('credit', _('Credit Department'), ''),
                    ('pay', _('Payroll Department'), ''),
                    ('fin_reports', _('Financial Reports'), {
                        'title': _('Financial Reports'),
                        'items': [
                            ('inc_stmt', _('Income Statement'),
                             ''),
                            ('bal_sheet', _('Balance Sheet'),
                             ''),
                            ('cash_flow', _('Cash Flow'), ''),
                            ('cust_rpts', _('Custom Reports'),
                             ''),
                        ],
                    }),
                    ('budget_mgmt', _('Budget Management'), {
                        'title': _('Budget Management'),
                        'items': [
                            ('budg_plan', _('Budget Planning'), ''),
                            ('budg_act', _('Budget vs. Actual'),
                             ''),
                            ('budg_amend', _('Budget Amendments'),
                             ''),
                            ('budg_rpts', _('Budget Reports'), ''),
                        ],
                    }),
                    ('audit_mgmt', _('Audit Management'), {
                        'title': _('Audit Management'),
                        'items': [
                            ('audit_sched', _('Audit Schedule'), ''),
                            ('findings', _('Audit Findings'), ''),
                            ('corr_act', _('Corrective Actions'),
                             ''),
                            ('audit_rpts', _('Audit Reports'), ''),
                        ],
                    }),
                ],
            }),
            ('acct_rcv', _('Accounts Receivable'), ''),
            ('credit', _('Credit Department'), ''),
            ('payroll', _('Payroll Department'), ''),
            ('gen_ledger', _('General Ledger'), ''),
            ('multi_entity', _('Multi-Entity'), {
                'title': _('Multi-Entity'),
                'items': [
                    ('companies', _('Companies'), ''),
                    ('intercompany', _('Intercompany Transactions'),
                     ''),
                    ('consol_fin', _('Consolidated Financials'),
                     ''),
                ],
            }),
            ('budget_mgmt', _('Budget Management'), {
                'title': _('Budget Management'),
                'items': [
                    ('budg_plan', _('Budget Planning'), ''),
                    ('budg_act', _('Budget vs. Actual'), ''),
                    ('budg_amend', _('Budget Amendments'), ''),
                    ('budg_rpts', _('Budget Reports'), ''),
                ],
            }),
            ('fin_reports', _('Financial Reports'), {
                'title': _('Financial Reports'),
                'items': [
                    ('inc_stmt', _('Income Statement'), ''),
                    ('bal_sheet', _('Balance Sheet'), ''),
                    ('cash_flow', _('Cash Flow'), ''),
                    ('cust_rpts', _('Custom Reports'), ''),
                ],
            }),
            ('tax_mgmt', _('Tax Management'), {
                'title': _('Tax Management'),
                'items': [
                    ('tax_cal', _('Tax Calendar'), ''),
                    ('tax_filing', _('Tax Filing'), ''),
                    ('tax_pay', _('Tax Payments'), ''),
                    ('tax_rpts', _('Tax Reports'), ''),
                ],
            }),
            ('exp_reports', _('Expense Reports'), {
                'title': _('Expense Reports'),
                'items': [
                    ('sub_exp', _('Submit Expense'), ''),
                    ('pend_appr', _('Pending Approval'), ''),
                    ('appr_exp', _('Approved Expenses'), ''),
                    ('exp_sum', _('Expense Summary'), ''),
                ],
            }),
            ('bank_recon', _('Bank Reconciliation'), {
                'title': _('Bank Reconciliation'),
                'items': [
                    ('recon_acct', _('Reconcile Account'), ''),
                    ('pend_items', _('Pending Items'), ''),
                    ('recon_hist', _('Reconciliation History'),
                     ''),
                    ('bank_rpts', _('Bank Reports'), ''),
                ],
            }),
        ],
    },
    'customer_service': {
        'title': _('Customer Service Main Menu'),
        'items': [
            ('cs_mgr', _('CS Manager Menu'), {
                'title': _('CS Manager Menu'),
                'items': [
                    ('cs_menu', _('Customer Service Menu'), _CS_MENU),
                    ('ticket_rpts', _('Ticket Reports'), {
                        'title': _('Ticket Reports'),
                        'items': [
                            ('daily_tick', _('Daily Ticket Report'),
                             ''),
                            ('week_sum', _('Weekly Summary'), ''),
                            ('res_analy', _('Resolution Analysis'),
                             ''),
                            ('sla_rpts', _('SLA Reports'), ''),
                        ],
                    }),
                    ('staff_mgmt', _('Staff Management'), {
                        'title': _('Staff Management'),
                        'items': [
                            ('staff_sched', _('Staff Schedule'),
                             ''),
                            ('perf_met', _('Performance Metrics'),
                             ''),
                            ('staff_train', _('Staff Training'),
                             ''),
                            ('staff_rpts', _('Staff Reports'),
                             ''),
                        ],
                    }),
                    ('cust_sat', _('Customer Satisfaction'), {
                        'title': _('Customer Satisfaction'),
                        'items': [
                            ('csat_res', _('CSAT Survey Results'),
                             ''),
                            ('nps_rpts', _('NPS Reports'), ''),
                            ('sat_trends', _('Satisfaction Trends'),
                             ''),
                            ('impr_plans', _('Improvement Plans'),
                             ''),
                        ],
                    }),
                    ('escalations', _('Escalations'), {
                        'title': _('Escalations'),
                        'items': [
                            ('act_esc', _('Active Escalations'),
                             ''),
                            ('esc_hist', _('Escalation History'),
                             ''),
                            ('esc_rpts', _('Escalation Reports'),
                             ''),
                            ('res_track', _('Resolution Tracking'),
                             ''),
                        ],
                    }),
                ],
            }),
            ('cs_menu', _('Customer Service Menu'), _CS_MENU),
        ],
    },
    'engineering': {
        'title': _('Engineering Main Menu'),
        'items': [
            ('eng_mgr', _('Engineering Manager'), {
                'title': _('Engineering Manager'),
                'items': [
                    ('engineers', _('Engineers'), ''),
                    ('proj_appr', _('Project Approvals'), {
                        'title': _('Project Approvals'),
                        'items': [
                            ('pend_appr', _('Pending Approvals'), ''),
                            ('appr_proj', _('Approved Projects'), ''),
                            ('rej_proj', _('Rejected Projects'), ''),
                            ('appr_hist', _('Approval History'), ''),
                        ],
                    }),
                    ('resource', _('Resource Management'), {
                        'title': _('Resource Management'),
                        'items': [
                            ('res_alloc', _('Resource Allocation'), ''),
                            ('cap_plan', _('Capacity Planning'), ''),
                            ('res_rpts', _('Resource Reports'), ''),
                            ('avail_cal', _('Availability Calendar'),
                             ''),
                        ],
                    }),
                    ('budget', _('Budget Management'), {
                        'title': _('Budget Management'),
                        'items': [
                            ('eng_budg', _('Engineering Budget'),
                             ''),
                            ('budg_act', _('Budget vs. Actual'),
                             ''),
                            ('cost_rpts', _('Cost Reports'), ''),
                            ('budg_req', _('Budget Requests'), ''),
                        ],
                    }),
                    ('eng_reports', _('Engineering Reports'), {
                        'title': _('Engineering Reports'),
                        'items': [
                            ('proj_stat', _('Project Status'), ''),
                            ('res_util', _('Resource Utilization'), ''),
                            ('kpi_dash', _('KPI Dashboard'), ''),
                            ('month_rpts', _('Monthly Reports'), ''),
                        ],
                    }),
                ],
            }),
            ('engineers', _('Engineers'), ''),
            ('proj_mgmt', _('Project Management'), {
                'title': _('Project Management'),
                'items': [
                    ('act_proj', _('Active Projects'), ''),
                    ('new_proj', _('New Project'), ''),
                    ('proj_time', _('Project Timeline'), ''),
                    ('proj_rpts', _('Project Reports'), ''),
                ],
            }),
            ('design_docs', _('Design Documents'), {
                'title': _('Design Documents'),
                'items': [
                    ('doc_lib', _('Document Library'), ''),
                    ('new_doc', _('New Document'), ''),
                    ('doc_review', _('Document Review'), ''),
                    ('archive', _('Archive'), ''),
                ],
            }),
            ('bom', _('Bill of Materials'), {
                'title': _('Bill of Materials'),
                'items': [
                    ('bom_list', _('BOM List'), ''),
                    ('new_bom', _('Create BOM'), ''),
                    ('bom_rev', _('BOM Revision'), ''),
                    ('bom_rpts', _('BOM Reports'), ''),
                ],
            }),
            ('chg_orders', _('Change Orders'), {
                'title': _('Change Orders'),
                'items': [
                    ('new_co', _('New Change Order'), ''),
                    ('pend_appr', _('Pending Approval'), ''),
                    ('appr_chg', _('Approved Changes'), ''),
                    ('chg_hist', _('Change History'), ''),
                ],
            }),
            ('test_val', _('Test & Validation'), {
                'title': _('Test & Validation'),
                'items': [
                    ('test_plans', _('Test Plans'), ''),
                    ('test_res', _('Test Results'), ''),
                    ('val_rpts', _('Validation Reports'), ''),
                    ('issue_track', _('Issue Tracking'), ''),
                ],
            }),
            ('eng_reports', _('Engineering Reports'), {
                'title': _('Engineering Reports'),
                'items': [
                    ('proj_stat', _('Project Status'), ''),
                    ('design_rev', _('Design Review'), ''),
                    ('res_rpt', _('Resource Report'), ''),
                    ('cust_rpts', _('Custom Reports'), ''),
                ],
            }),
            ('standards', _('Standards & Compliance'), {
                'title': _('Standards & Compliance'),
                'items': [
                    ('std_lib', _('Standards Library'), ''),
                    ('comp_chk', _('Compliance Checklist'), ''),
                    ('audit_res', _('Audit Results'), ''),
                    ('reg_upd', _('Regulatory Updates'), ''),
                ],
            }),
        ],
    },
    'information_tech': {
        'title': _('Information Technology Main Menu'),
        'items': [
            ('it_mgr', _('IT Manager'), {
                'title': _('IT Manager'),
                'items': [
                    ('it_tech', _('IT Technician'), _IT_TECH),
                    ('budget', _('Budget & Procurement'), {
                        'title': _('Budget & Procurement'),
                        'items': [
                            ('it_budg', _('IT Budget'), ''),
                            ('hw_proc', _('Hardware Procurement'),
                             ''),
                            ('sw_lic', _('Software Licensing'), ''),
                            ('proc_rpts', _('Procurement Reports'),
                             ''),
                        ],
                    }),
                    ('vendor_con', _('Vendor Contracts'), {
                        'title': _('Vendor Contracts'),
                        'items': [
                            ('act_cont', _('Active Contracts'), ''),
                            ('cont_renew', _('Contract Renewals'), ''),
                            ('vend_perf', _('Vendor Performance'), ''),
                            ('cont_arch', _('Contract Archive'), ''),
                        ],
                    }),
                    ('it_projects', _('IT Projects'), {
                        'title': _('IT Projects'),
                        'items': [
                            ('act_proj', _('Active Projects'), ''),
                            ('proj_pipe', _('Project Pipeline'), ''),
                            ('proj_rpts', _('Project Reports'), ''),
                            ('res_alloc', _('Resource Allocation'), ''),
                        ],
                    }),
                    ('security', _('Security Management'), {
                        'title': _('Security Management'),
                        'items': [
                            ('sec_dash', _('Security Dashboard'), ''),
                            ('inc_rpts', _('Incident Reports'), ''),
                            ('vuln_mgmt', _('Vulnerability Management'),
                             ''),
                            ('comp_rpts', _('Compliance Reports'), ''),
                        ],
                    }),
                ],
            }),
            ('it_tech', _('IT Technician'), _IT_TECH),
        ],
    },
    'maintenance': {
        'title': _('Maintenance Main Menu'),
        'items': [
            ('maint_mgr', _('Maintenance Manager'), {
                'title': _('Maintenance Manager'),
                'items': [
                    ('maint', _('Maintenance'), _MAINT_MENU),
                    ('wo_approvals', _('Work Order Approvals'), {
                        'title': _('Work Order Approvals'),
                        'items': [
                            ('pend_appr', _('Pending Approvals'),
                             ''),
                            ('appr_wo', _('Approved Work Orders'),
                             ''),
                            ('rej_wo', _('Rejected'), ''),
                            ('appr_hist', _('Approval History'),
                             ''),
                        ],
                    }),
                    ('budget_mgmt', _('Budget Management'), {
                        'title': _('Budget Management'),
                        'items': [
                            ('maint_budg', _('Maintenance Budget'),
                             ''),
                            ('budg_act', _('Budget vs. Actual'),
                             ''),
                            ('cost_analy', _('Cost Analysis'), ''),
                            ('budg_req', _('Budget Requests'), ''),
                        ],
                    }),
                    ('maint_rpts', _('Maintenance Reports'), {
                        'title': _('Maintenance Reports'),
                        'items': [
                            ('daily_rpt', _('Daily Report'), ''),
                            ('month_sum', _('Monthly Summary'),
                             ''),
                            ('equip_rpts', _('Equipment Reports'),
                             ''),
                            ('cost_rpts', _('Cost Reports'), ''),
                        ],
                    }),
                ],
            }),
            ('maint', _('Maintenance'), _MAINT_MENU),
            ('predictive_maint', _('Predictive Maintenance'), ''),
        ],
    },
    'marketing': {
        'title': _('Marketing Main Menu'),
        'items': [
            ('mkt_mgr', _('Marketing Manager Menu'), {
                'title': _('Marketing Manager Menu'),
                'items': [
                    ('mkt_menu', _('Marketing Menu'), _MKT_MENU),
                    ('mkt_budget', _('Marketing Budget'), {
                        'title': _('Marketing Budget'),
                        'items': [
                            ('budg_over', _('Budget Overview'), ''),
                            ('budg_camp', _('Budget by Campaign'),
                             ''),
                            ('budg_act', _('Budget vs. Actual'),
                             ''),
                            ('budg_req', _('Budget Requests'), ''),
                        ],
                    }),
                    ('camp_appr', _('Campaign Approvals'), {
                        'title': _('Campaign Approvals'),
                        'items': [
                            ('pend_appr', _('Pending Approvals'),
                             ''),
                            ('appr_camp', _('Approved Campaigns'),
                             ''),
                            ('camp_arch', _('Campaign Archive'),
                             ''),
                            ('appr_hist', _('Approval History'),
                             ''),
                        ],
                    }),
                    ('mkt_reports', _('Marketing Reports'), {
                        'title': _('Marketing Reports'),
                        'items': [
                            ('camp_perf', _('Campaign Performance'),
                             ''),
                            ('roi_rpts', _('ROI Reports'),
                             ''),
                            ('month_sum', _('Monthly Summary'),
                             ''),
                            ('kpi_dash', _('KPI Dashboard'),
                             ''),
                        ],
                    }),
                ],
            }),
            ('mkt_menu', _('Marketing Menu'), _MKT_MENU),
        ],
    },
    'personnel': {
        'title': _('Personnel Main Menu'),
        'items': [
            ('pers_mgr', _('Personnel Manager Menu'), {
                'title': _('Personnel Manager Menu'),
                'items': [
                    ('pers_menu', _('Personnel Menu'), _PERS_MENU),
                    ('hiring', _('Hiring & Recruitment'), {
                        'title': _('Hiring & Recruitment'),
                        'items': [
                            ('open_pos', _('Open Positions'),
                             ''),
                            ('appl_track', _('Applicant Tracking'),
                             ''),
                            ('int_sched', _('Interview Schedule'),
                             ''),
                            ('offer_mgmt', _('Offer Management'),
                             ''),
                        ],
                    }),
                    ('term', _('Terminations'), {
                        'title': _('Terminations'),
                        'items': [
                            ('term_proc', _('Termination Process'),
                             ''),
                            ('exit_int', _('Exit Interviews'),
                             ''),
                            ('final_pay', _('Final Pay Processing'),
                             ''),
                            ('offboard', _('Offboarding Checklist'),
                             ''),
                        ],
                    }),
                    ('salary', _('Salary Management'), {
                        'title': _('Salary Management'),
                        'items': [
                            ('sal_review', _('Salary Review'),
                             ''),
                            ('sal_adj', _('Salary Adjustments'),
                             ''),
                            ('comp_rpts', _('Compensation Reports'),
                             ''),
                            ('pay_grades', _('Pay Grades'),
                             ''),
                        ],
                    }),
                    ('hr_reports', _('HR Reports'), {
                        'title': _('HR Reports'),
                        'items': [
                            ('hd_rpt', _('Headcount Report'),
                             ''),
                            ('turn_rpt', _('Turnover Report'),
                             ''),
                            ('comp_rpts', _('Compliance Reports'),
                             ''),
                            ('month_sum', _('Monthly Summary'),
                             ''),
                        ],
                    }),
                ],
            }),
            ('pers_menu', _('Personnel Menu'), _PERS_MENU),
        ],
    },
    'production': {
        'title': _('Production Main Menu'),
        'items': [
            ('prod_mgr', _('Production Manager'), {
                'title': _('Production Manager'),
                'items': [
                    ('prod', _('Production'), _PROD_MENU),
                    ('shipping', _('Shipping'), _SHIP_MENU),
                    ('prod_reports', _('Production Reports'), {
                        'title': _('Production Reports'),
                        'items': [
                            ('daily_prod', _('Daily Production'),
                             ''),
                            ('week_sum', _('Weekly Summary'), ''),
                            ('eff_rpts', _('Efficiency Reports'),
                             ''),
                            ('kpi_dash', _('KPI Dashboard'), ''),
                        ],
                    }),
                    ('resource', _('Resource Management'), {
                        'title': _('Resource Management'),
                        'items': [
                            ('res_alloc', _('Resource Allocation'),
                             ''),
                            ('cap_plan', _('Capacity Planning'),
                             ''),
                            ('res_rpts', _('Resource Reports'),
                             ''),
                            ('wf_plan', _('Workforce Planning'),
                             ''),
                        ],
                    }),
                    ('budget', _('Budget Management'), {
                        'title': _('Budget Management'),
                        'items': [
                            ('prod_budg', _('Production Budget'),
                             ''),
                            ('cost_analy', _('Cost Analysis'), ''),
                            ('budg_act', _('Budget vs. Actual'),
                             ''),
                            ('budg_rpts', _('Budget Reports'), ''),
                        ],
                    }),
                ],
            }),
            ('prod', _('Production'), _PROD_MENU),
            ('shipping', _('Shipping'), _SHIP_MENU),
            ('shop_floor', _('Shop Floor'), {
                'title': _('Shop Floor'),
                'items': [
                    ('sf_entry', _('Production/Downtime Entry'),
                     ''),
                    ('sf_shift_plan', _('Shift Plan'), ''),
                    ('sf_dashboard', _('Live OEE Dashboard'),
                     ''),
                    ('sf_tv', _('Shop Floor TV Display'), ''),
                ],
            }),
        ],
    },
    'purchasing': {
        'title': _('Purchasing Main Menu'),
        'items': [
            ('purch_mgr', _('Purchasing Manager Menu'), {
                'title': _('Purchasing Manager Menu'),
                'items': [
                    ('purch', _('Purchasing Menu'), _PURCH_MENU),
                    ('po_approvals', _('PO Approvals'), {
                        'title': _('PO Approvals'),
                        'items': [
                            ('pend_appr', _('Pending Approvals'),
                             ''),
                            ('appr_pos', _('Approved POs'),
                             ''),
                            ('rej_pos', _('Rejected POs'),
                             ''),
                            ('appr_hist', _('Approval History'),
                             ''),
                        ],
                    }),
                    ('budget', _('Budget Management'), {
                        'title': _('Budget Management'),
                        'items': [
                            ('purch_budg', _('Purchasing Budget'),
                             ''),
                            ('budg_act', _('Budget vs. Actual'),
                             ''),
                            ('spend_analy', _('Spending Analysis'),
                             ''),
                            ('budg_rpts', _('Budget Reports'), ''),
                        ],
                    }),
                    ('vendor_mgmt', _('Vendor Management'), {
                        'title': _('Vendor Management'),
                        'items': [
                            ('vend_list', _('Vendor List'),
                             ''),
                            ('vend_eval', _('Vendor Evaluation'),
                             ''),
                            ('vend_perf', _('Vendor Performance'),
                             ''),
                            ('appr_vend', _('Approved Vendors'),
                             ''),
                        ],
                    }),
                    ('purch_rpts', _('Purchasing Reports'), {
                        'title': _('Purchasing Reports'),
                        'items': [
                            ('spend_rpt', _('Spending Report'),
                             ''),
                            ('vend_rpt', _('Vendor Report'),
                             ''),
                            ('cat_analy', _('Category Analysis'),
                             ''),
                            ('month_sum', _('Monthly Summary'),
                             ''),
                        ],
                    }),
                    ('contracts', _('Contract Management'), {
                        'title': _('Contract Management'),
                        'items': [
                            ('act_cont', _('Active Contracts'),
                             ''),
                            ('pend_renew', _('Pending Renewals'),
                             ''),
                            ('cont_arch', _('Contract Archive'),
                             ''),
                            ('cont_rpts', _('Contract Reports'),
                             ''),
                        ],
                    }),
                    ('consultants', _('Consultant Management'), {
                        'title': _('Consultant Management'),
                        'items': [
                            ('cons_list', _('Consultants'), ''),
                            ('cons_eng', _('Engagements'), ''),
                            ('cons_inv', _('Invoices'), ''),
                            ('cons_rpt', _('Spend Report'), ''),
                        ],
                    }),
                ],
            }),
            ('purch', _('Purchasing Menu'), _PURCH_MENU),
        ],
    },
    'quality_assurance': {
        'title': _('Quality Assurance Main Menu'),
        'items': [
            ('qa_mgr', _('QA Manager Menu'), {
                'title': _('QA Manager Menu'),
                'items': [
                    ('qa_menu', _('Quality Assurance Menu'), _QA_MENU),
                    ('audit_mgmt', _('Audit Management'), {
                        'title': _('Audit Management'),
                        'items': [
                            ('audit_sched', _('Audit Schedule'),
                             ''),
                            ('act_audits', _('Active Audits'), ''),
                            ('findings', _('Audit Findings'), ''),
                            ('corr_act', _('Corrective Actions'),
                             ''),
                        ],
                    }),
                    ('compliance', _('Compliance'), {
                        'title': _('Compliance'),
                        'items': [
                            ('comp_dash', _('Compliance Dashboard'),
                             ''),
                            ('reg_req', _('Regulatory Requirements'),
                             ''),
                            ('comp_rpts', _('Compliance Reports'),
                             ''),
                            ('non_comp', _('Non-Compliance Issues'),
                             ''),
                        ],
                    }),
                    ('corr_action', _('Corrective Actions'), {
                        'title': _('Corrective Actions'),
                        'items': [
                            ('open_cars', _('Open CARs'), ''),
                            ('inprog_cars', _('In Progress'), ''),
                            ('closed_cars', _('Closed CARs'), ''),
                            ('car_rpts', _('CAR Reports'), ''),
                        ],
                    }),
                    ('qa_reports', _('QA Reports'), {
                        'title': _('QA Reports'),
                        'items': [
                            ('daily_qa', _('Daily QA Report'), ''),
                            ('week_sum', _('Weekly Summary'), ''),
                            ('month_rpt', _('Monthly Report'), ''),
                            ('kpi_dash', _('KPI Dashboard'), ''),
                        ],
                    }),
                    ('supp_qual', _('Supplier Quality'), {
                        'title': _('Supplier Quality'),
                        'items': [
                            ('supp_score', _('Supplier Scorecards'),
                             ''),
                            ('inc_insp', _('Incoming Inspection'),
                             ''),
                            ('sampling_plans', _('Sampling Plans'),
                             ''),
                            ('supp_audit', _('Supplier Audits'),
                             ''),
                            ('supp_rpts', _('Supplier Reports'),
                             ''),
                        ],
                    }),
                    ('cust_comp', _('Customer Complaints'), {
                        'title': _('Customer Complaints'),
                        'items': [
                            ('new_comp', _('New Complaint'), ''),
                            ('open_comp', _('Open Complaints'), ''),
                            ('res_track', _('Resolution Tracking'),
                             ''),
                            ('comp_rpts', _('Complaint Reports'),
                             ''),
                        ],
                    }),
                    ('doc_control', _('Document Control'), {
                        'title': _('Document Control'),
                        'items': [
                            ('doc_lib', _('Document Library'), ''),
                            ('new_doc', _('New Document'), ''),
                            ('doc_review', _('Document Review'),
                             ''),
                            ('rev_hist', _('Revision History'), ''),
                        ],
                    }),
                ],
            }),
            ('qa_menu', _('Quality Assurance Menu'), _QA_MENU),
        ],
    },
    'sales': {
        'title': _('Sales Main Menu'),
        'items': [
            ('sales_mgr', _('Sales Manager Menu'), {
                'title': _('Sales Manager Menu'),
                'items': [
                    ('sales', _('Sales Menu'), _SALES_MENU),
                    ('sales_targets', _('Sales Targets'), {
                        'title': _('Sales Targets'),
                        'items': [
                            ('set_tgt', _('Set Targets'), ''),
                            ('tgt_act', _('Target vs. Actual'),
                             ''),
                            ('tgt_rep', _('Target by Rep'), ''),
                            ('tgt_rpts', _('Target Reports'),
                             ''),
                        ],
                    }),
                    ('territory', _('Territory Management'), {
                        'title': _('Territory Management'),
                        'items': [
                            ('terr_map', _('Territory Map'), ''),
                            ('terr_assign', _('Territory Assignments'),
                             ''),
                            ('terr_perf', _('Territory Performance'),
                             ''),
                            ('terr_rpts', _('Territory Reports'),
                             ''),
                        ],
                    }),
                    ('commission', _('Commission Tracking'), {
                        'title': _('Commission Tracking'),
                        'items': [
                            ('comm_calc', _('Commission Calculator'),
                             ''),
                            ('comm_rpts', _('Commission Reports'),
                             ''),
                            ('pay_hist', _('Payment History'),
                             ''),
                            ('comm_plans', _('Commission Plans'),
                             ''),
                        ],
                    }),
                    ('staff_perf', _('Staff Performance'), {
                        'title': _('Staff Performance'),
                        'items': [
                            ('perf_dash', _('Performance Dashboard'),
                             ''),
                            ('rep_rank', _('Rep Rankings'), ''),
                            ('perf_revs', _('Performance Reviews'),
                             ''),
                            ('coaching', _('Coaching Notes'),
                             ''),
                        ],
                    }),
                ],
            }),
            ('sales', _('Sales Menu'), _SALES_MENU),
            ('demand_forecast', _('AI Demand Forecast'), ''),
        ],
    },
    'budget_management': {
        'title': _('Budget Management'),
        'items': [
            ('budget_mgr', _('Budget Manager'), {
                'title': _('Budget Manager'),
                'items': [
                    ('bud_overview', _('Budgets'), ''),
                    ('bud_detail_mgr', _('Budget Detail'), ''),
                    ('bva_mgr', _('Budget vs. Actual'), ''),
                    ('variance_mgr', _('Variance Report'), ''),
                    ('dept_summary', _('Department Summaries'),
                     ''),
                    ('approval_wf', _('Approval Workflow'), ''),
                ],
            }),
            ('budgets', _('Budgets'), ''),
            ('bud_detail', _('Budget Detail'), ''),
            ('bva', _('Budget vs. Actual'), ''),
            ('variance', _('Variance Report'), ''),
        ],
    },
    'finance': {
        'title': _('Finance Main Menu'),
        'items': [
            ('fin_mgr', _('Finance Manager'), {
                'title': _('Finance Manager'),
                'items': [
                    ('fin_plan', _('Financial Planning'), ''),
                    ('fin_forecast', _('Budget & Forecasting'),
                     ''),
                    ('treasury_mgmt', _('Treasury Management'),
                     ''),
                    ('invest_mgmt', _('Investment Management'),
                     ''),
                    ('fin_rpts_mgr', _('Financial Reports'),
                     ''),
                ],
            }),
            ('fin_analysis', _('Financial Analysis'), ''),
            ('fin_reporting', _('Financial Reporting'), ''),
            ('treasury_ops', _('Treasury Operations'), ''),
            ('capital_mgmt', _('Capital Management'), ''),
            ('tax_planning', _('Tax Planning'), ''),
        ],
    },
    'legal': {
        'title': _('Legal Main Menu'),
        'items': [
            ('legal_mgr', _('Legal Manager'), {
                'title': _('Legal Manager'),
                'items': [
                    ('contracts_mgmt', _('Contract Management'),
                     ''),
                    ('litigation_mgmt', _('Litigation Management'),
                     ''),
                    ('compliance_mgmt', _('Compliance Management'),
                     ''),
                    ('corp_gov', _('Corporate Governance'), ''),
                ],
            }),
            ('contracts', _('Contracts'), ''),
            ('compliance', _('Compliance'), ''),
            ('litigation', _('Litigation'), ''),
            ('ip_mgmt', _('Intellectual Property'), ''),
            ('emp_law', _('Employment Law'), ''),
        ],
    },
    'risk_management': {
        'title': _('Risk Management Main Menu'),
        'items': [
            ('risk_mgr', _('Risk Manager'), {
                'title': _('Risk Manager'),
                'items': [
                    ('risk_register_mgr', _('Risk Register'), ''),
                    ('kri', _('Key Risk Indicators'), ''),
                    ('biz_continuity', _('Business Continuity'),
                     ''),
                    ('audit_compliance', _('Audit & Compliance'),
                     ''),
                ],
            }),
            ('risk_assess', _('Risk Assessment'), ''),
            ('risk_register', _('Risk Register'), ''),
            ('insurance', _('Insurance Management'), ''),
            ('biz_cont', _('Business Continuity'), ''),
            ('comp_audit', _('Compliance & Audit'), ''),
        ],
    },
    'reports': {
        'title': _('Reports'),
        'items': [
            ('rpt_dashboard', _('Dashboard'), ''),
        ],
    },
}


DEPT_MENU_KEY = {
    'Accounting': 'accounting',
    'Customer Service': 'customer_service',
    'Engineering': 'engineering',
    'Information Tech': 'information_tech',
    'Information Technologies': 'information_tech',
    'Maintenance': 'maintenance',
    'Marketing': 'marketing',
    'Personnel': 'personnel',
    'Production': 'production',
    'Purchasing': 'purchasing',
    'Quality Assurance': 'quality_assurance',
    'Sales': 'sales',
    'Budget Management': 'budget_management',
    'Finance': 'finance',
    'Legal': 'legal',
    'Risk Management': 'risk_management',
    'Warehouse': 'warehouse',
    'Reports': 'reports',
}

DASHBOARD_DEPARTMENTS = [
    ('accounting', _('Accounting')),
    ('customer_service', _('Customer Service')),
    ('engineering', _('Engineering')),
    ('information_tech', _('Information Tech')),
    ('maintenance', _('Maintenance')),
    ('marketing', _('Marketing')),
    ('personnel', _('Personnel')),
    ('production', _('Production')),
    ('inventory', _('Inventory')),
    ('purchasing', _('Purchasing')),
    ('quality_assurance', _('Quality Assurance')),
    ('sales', _('Sales')),
    ('budget_management', _('Budget Management')),
    ('finance', _('Finance')),
    ('legal', _('Legal')),
    ('risk_management', _('Risk Management')),
    ('reports', _('Reports')),
]

# Menu node keys that are only shown to managers.
MANAGER_MENU_KEYS = {
    'acct_mgr', 'cs_mgr', 'eng_mgr', 'it_mgr', 'maint_mgr', 'mkt_mgr',
    'pers_mgr', 'prod_mgr', 'purch_mgr', 'qa_mgr', 'sales_mgr',
    'budget_mgr', 'fin_mgr', 'legal_mgr', 'risk_mgr',
}


def _walk_tree(dept, parts):
    """Walk MENU_TREE by dept + list of key parts.

    Returns the node dict, or None.
    """
    node = MENU_TREE.get(dept)
    if node is None:
        return None
    for part in parts:
        found = None
        for key, _label, target in node.get('items', []):
            if key == part:
                found = target
                break
        if not isinstance(found, dict):
            return None
        node = found
    return node
