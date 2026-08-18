"""Menu tree data and navigation helpers.

``MENU_TREE`` describes the department / sub-menu hierarchy rendered by the
dashboard and menu views, and the lookup tables that map departments to it.
"""

# Each item: (key, label, target)
# target is a script filename (str = leaf) or a dict (sub-menu node).

_TIME_CLOCK_MENU = {
    'title': 'Time Clock Menu',
    'items': [
        ('clock_in_out', 'Clock In/Out', {
            'title': 'Clock In/Out',
            'items': [
                ('punch_in', 'Record Clock In', ''),
                ('punch_out', 'Record Clock Out', ''),
                ('cur_status', 'Current Status', ''),
            ],
        }),
        ('view_hours', 'View Hours', {
            'title': 'View Hours',
            'items': [
                ('today_hrs', "Today's Hours", ''),
                ('week_hrs', 'Weekly Hours', ''),
                ('month_hrs', 'Monthly Hours', ''),
                ('period_hrs', 'Pay Period Hours', ''),
            ],
        }),
        ('time_off', 'Time Off Requests', {
            'title': 'Time Off Requests',
            'items': [
                ('submit_req', 'Submit Request', ''),
                ('pend_req', 'Pending Requests', ''),
                ('appr_req', 'Approved Requests', ''),
                ('req_hist', 'Request History', ''),
            ],
        }),
        ('schedules', 'Schedules', {
            'title': 'Schedules',
            'items': [
                ('my_sched', 'My Schedule', ''),
                ('upcoming', 'Upcoming Shifts', ''),
                ('sched_cal', 'Schedule Calendar', ''),
                ('swap_req', 'Swap Requests', ''),
            ],
        }),
        ('ot_reports', 'Overtime Reports', {
            'title': 'Overtime Reports',
            'items': [
                ('cur_ot', 'Current Period OT', ''),
                ('hist_ot', 'Historical OT', ''),
                ('ot_by_emp', 'OT by Employee', ''),
                ('ot_appr', 'OT Approval', ''),
            ],
        }),
        ('attend_reports', 'Attendance Reports', {
            'title': 'Attendance Reports',
            'items': [
                ('daily_att', 'Daily Attendance', ''),
                ('month_sum', 'Monthly Summary', ''),
                ('tard_rpt', 'Tardiness Report', ''),
                ('abs_rpt', 'Absence Report', ''),
            ],
        }),
        ('shift_mgmt', 'Shift Management', {
            'title': 'Shift Management',
            'items': [
                ('view_shfts', 'View Shifts', ''),
                ('assign_emp', 'Assign Employees', ''),
                ('shft_tmpl', 'Shift Templates', ''),
                ('swap_mgmt', 'Swap Management', ''),
            ],
        }),
    ],
}

_MAINT_MENU = {
    'title': 'Maintenance Menu',
    'items': [
        ('work_orders', 'Work Orders', {
            'title': 'Work Orders',
            'items': [
                ('create_wo', 'Create Work Order', ''),
                ('open_wo', 'Open Work Orders', ''),
                ('inprog_wo', 'In Progress', ''),
                ('comp_wo', 'Completed', ''),
            ],
        }),
        ('maint_schedule', 'Maintenance Schedule', {
            'title': 'Maintenance Schedule',
            'items': [
                ('daily_sched', 'Daily Schedule', ''),
                ('week_sched', 'Weekly Schedule', ''),
                ('month_sched', 'Monthly Schedule', ''),
                ('annual_plan', 'Annual Plan', ''),
            ],
        }),
        ('equip_maint', 'Equipment Maintenance', {
            'title': 'Equipment Maintenance',
            'items': [
                ('equip_list', 'Equipment List', ''),
                ('maint_hist', 'Maintenance History', ''),
                ('svc_records', 'Service Records', ''),
                ('equip_stat', 'Equipment Status', ''),
            ],
        }),
        ('parts_inv', 'Parts Inventory', {
            'title': 'Parts Inventory',
            'items': [
                ('view_inv', 'View Inventory', ''),
                ('parts_req', 'Parts Request', ''),
                ('reorder', 'Reorder List', ''),
                ('parts_hist', 'Parts History', ''),
            ],
        }),
        ('maint_reports', 'Maintenance Reports', {
            'title': 'Maintenance Reports',
            'items': [
                ('daily_rpt', 'Daily Report', ''),
                ('week_rpt', 'Weekly Report', ''),
                ('cost_analy', 'Cost Analysis', ''),
                ('down_rpt', 'Downtime Report', ''),
            ],
        }),
        ('safety_insp', 'Safety Inspections', {
            'title': 'Safety Inspections',
            'items': [
                ('sched_insp', 'Schedule Inspection', ''),
                ('insp_chk', 'Inspection Checklist', ''),
                ('insp_res', 'Inspection Results', ''),
                ('corr_act', 'Corrective Actions', ''),
            ],
        }),
        ('prev_maint', 'Preventive Maintenance', {
            'title': 'Preventive Maintenance',
            'items': [
                ('pm_sched', 'PM Schedule', ''),
                ('pm_chk', 'PM Checklists', ''),
                ('pm_hist', 'PM History', ''),
                ('pm_rpts', 'PM Reports', ''),
            ],
        }),
    ],
}

_MKT_MENU = {
    'title': 'Marketing Menu',
    'items': [
        ('campaigns', 'Campaigns', {
            'title': 'Campaigns',
            'items': [
                ('act_camp', 'Active Campaigns', ''),
                ('new_camp', 'Create Campaign', ''),
                ('camp_cal', 'Campaign Calendar', ''),
                ('camp_res', 'Campaign Results', ''),
            ],
        }),
        ('mkt_research', 'Market Research', {
            'title': 'Market Research',
            'items': [
                ('res_proj', 'Research Projects', ''),
                ('comp_analy', 'Competitor Analysis', ''),
                ('surv_mgmt', 'Survey Management', ''),
                ('mkt_trends', 'Market Trends', ''),
            ],
        }),
        ('advertising', 'Advertising', {
            'title': 'Advertising',
            'items': [
                ('ad_mgmt', 'Ad Management', ''),
                ('ad_budget', 'Ad Budget', ''),
                ('ad_perf', 'Ad Performance', ''),
                ('ad_cal', 'Ad Calendar', ''),
            ],
        }),
        ('analytics', 'Analytics', {
            'title': 'Analytics',
            'items': [
                ('web_analy', 'Website Analytics', ''),
                ('camp_analy', 'Campaign Analytics', ''),
                ('sales_analy', 'Sales Analytics', ''),
                ('cust_rpts', 'Custom Reports', ''),
            ],
        }),
        ('content_mgmt', 'Content Management', {
            'title': 'Content Management',
            'items': [
                ('cont_cal', 'Content Calendar', ''),
                ('blog', 'Blog Posts', ''),
                ('mkt_mat', 'Marketing Materials', ''),
                ('cont_arch', 'Content Archive', ''),
            ],
        }),
        ('social_media', 'Social Media', {
            'title': 'Social Media',
            'items': [
                ('post_mgmt', 'Post Management', ''),
                ('social_cal', 'Social Calendar', ''),
                ('eng_rpts', 'Engagement Reports', ''),
                ('acct_mgmt', 'Account Management', ''),
            ],
        }),
        ('email_mkt', 'Email Marketing', {
            'title': 'Email Marketing',
            'items': [
                ('email_camp', 'Email Campaigns', ''),
                ('sub_lists', 'Subscriber Lists', ''),
                ('email_tmpl', 'Email Templates', ''),
                ('email_analy', 'Email Analytics', ''),
            ],
        }),
    ],
}

_SALES_MENU = {
    'title': 'Sales Menu',
    'items': [
        ('sales_orders', 'Sales Orders', {
            'title': 'Sales Orders',
            'items': [
                ('new_order', 'New Order', ''),
                ('open_orders', 'Open Orders', ''),
                ('order_hist', 'Order History', ''),
                ('order_stat', 'Order Status', ''),
            ],
        }),
        ('cust_accounts', 'Customer Accounts', {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list', 'Account List', ''),
                ('new_acct', 'New Account', ''),
                ('acct_det', 'Account Details', ''),
                ('acct_hist', 'Account History', ''),
            ],
        }),
        ('sales_reports', 'Sales Reports', {
            'title': 'Sales Reports',
            'items': [
                ('daily_sales', 'Daily Sales', ''),
                ('month_sales', 'Monthly Sales', ''),
                ('annual_rpt', 'Annual Report', ''),
                ('by_rep', 'Sales by Rep', ''),
            ],
        }),
        ('quotes', 'Quotes', {
            'title': 'Quotes',
            'items': [
                ('new_quote', 'Create Quote', ''),
                ('act_quotes', 'Active Quotes', ''),
                ('quote_hist', 'Quote History', ''),
                ('conv_order', 'Convert to Order', ''),
            ],
        }),
        ('leads', 'Leads & Opportunities', {
            'title': 'Leads & Opportunities',
            'items': [
                ('new_lead', 'New Lead', ''),
                ('act_leads', 'Active Leads', ''),
                ('opp_pipe', 'Opportunities Pipeline', ''),
                ('lead_rpts', 'Lead Reports', ''),
            ],
        }),
        ('contracts', 'Contracts', {
            'title': 'Contracts',
            'items': [
                ('act_cont', 'Active Contracts', ''),
                ('new_cont', 'Create Contract', ''),
                ('cont_renew', 'Contract Renewals', ''),
                ('cont_arch', 'Contract Archive', ''),
            ],
        }),
        ('forecasting', 'Sales Forecasting', {
            'title': 'Sales Forecasting',
            'items': [
                ('cur_fore', 'Current Forecast', ''),
                ('fore_rep', 'Forecast by Rep', ''),
                ('fore_prod', 'Forecast by Product', ''),
                ('fore_rpts', 'Forecast Reports', ''),
            ],
        }),
    ],
}

_PROD_MENU = {
    'title': 'Production Menu',
    'items': [
        ('work_orders', 'Work Orders', {
            'title': 'Work Orders',
            'items': [
                ('create_wo', 'Create Work Order', ''),
                ('open_wo', 'Open Work Orders', ''),
                ('inprog_wo', 'In Progress', ''),
                ('comp_wo', 'Completed', ''),
            ],
        }),
        ('mrp', 'MRP Planning', {
            'title': 'Material Requirements Planning',
            'items': [
                ('mrp_home', 'MRP Home', ''),
                ('run_mrp', 'Run MRP Plan', ''),
                ('mrp_demand', 'View Demand', ''),
                ('mrp_rpts', 'MRP Reports', ''),
            ],
        }),
        ('prod_schedule', 'Production Schedule', {
            'title': 'Production Schedule',
            'items': [
                ('daily_sched', 'Daily Schedule', ''),
                ('week_sched', 'Weekly Schedule', ''),
                ('month_sched', 'Monthly Schedule', ''),
                ('sched_cal', 'Schedule Calendar', ''),
                ('gantt_sched', 'Gantt Chart', ''),
            ],
        }),
        ('inventory', 'Inventory', {
            'title': 'Inventory',
            'items': [
                ('raw_mat', 'Raw Materials', ''),
                ('fin_goods', 'Finished Goods', ''),
                ('wip_inv', 'WIP Inventory', ''),
                ('inv_rpts', 'Inventory Reports', ''),
                ('cost_valuation', 'FIFO/LIFO/Avg Valuation', ''),
            ],
        }),
        ('equip_status', 'Equipment Status', {
            'title': 'Equipment Status',
            'items': [
                ('equip_list', 'Equipment List', ''),
                ('stat_dash', 'Status Dashboard', ''),
                ('down_log', 'Downtime Log', ''),
                ('maint_req', 'Maintenance Requests', ''),
            ],
        }),
        ('quality_ctrl', 'Quality Control', {
            'title': 'Quality Control',
            'items': [
                ('insp_res', 'Inspection Results', ''),
                ('non_conf', 'Non-Conformances', ''),
                ('qc_rpts', 'QC Reports', ''),
                ('rej_analy', 'Reject Analysis', ''),
            ],
        }),
        ('prod_reports', 'Production Reports', {
            'title': 'Production Reports',
            'items': [
                ('daily_prod', 'Daily Production', ''),
                ('week_sum', 'Weekly Summary', ''),
                ('eff_rpt', 'Efficiency Report', ''),
                ('scrap_rpt', 'Scrap Report', ''),
            ],
        }),
        ('labor_tracking', 'Labor Tracking', {
            'title': 'Labor Tracking',
            'items': [
                ('cur_labor', 'Current Labor', ''),
                ('labor_shft', 'Labor by Shift', ''),
                ('labor_job', 'Labor by Job', ''),
                ('labor_rpts', 'Labor Reports', ''),
            ],
        }),
    ],
}

_SHIP_MENU = {
    'title': 'Shipping Department',
    'items': [
        ('ship_orders', 'Shipment Orders', {
            'title': 'Shipment Orders',
            'items': [
                ('new_ship', 'New Shipment', ''),
                ('pend_ship', 'Pending Shipments', ''),
                ('shipped', 'Shipped Orders', ''),
                ('deliv_conf', 'Delivery Confirmation', ''),
            ],
        }),
        ('ship_schedule', 'Shipping Schedule', {
            'title': 'Shipping Schedule',
            'items': [
                ('today_sched', "Today's Schedule", ''),
                ('week_sched', 'Weekly Schedule', ''),
                ('sched_cal', 'Schedule Calendar', ''),
                ('rush_orders', 'Rush Orders', ''),
            ],
        }),
        ('receiving', 'Receiving', {
            'title': 'Receiving',
            'items': [
                ('inbound', 'Inbound Shipments', ''),
                ('recv_items', 'Receive Items', ''),
                ('recv_rpts', 'Receiving Reports', ''),
                ('disc_rpts', 'Discrepancy Reports', ''),
            ],
        }),
        ('carrier_mgmt', 'Carrier Management', {
            'title': 'Carrier Management',
            'items': [
                ('carr_list', 'Carrier List', ''),
                ('carr_rates', 'Carrier Rates', ''),
                ('perf_rpts', 'Performance Reports', ''),
                ('carr_cont', 'Carrier Contracts', ''),
            ],
        }),
        ('tracking', 'Tracking', {
            'title': 'Tracking',
            'items': [
                ('track_ship', 'Track Shipment', ''),
                ('track_dash', 'Tracking Dashboard', ''),
                ('deliv_stat', 'Delivery Status', ''),
                ('exc_rpts', 'Exception Reports', ''),
            ],
        }),
        ('ship_reports', 'Shipping Reports', {
            'title': 'Shipping Reports',
            'items': [
                ('daily_rpt', 'Daily Report', ''),
                ('week_sum', 'Weekly Summary', ''),
                ('cost_analy', 'Cost Analysis', ''),
                ('perf_rpt', 'Performance Report', ''),
            ],
        }),
        ('returns_proc', 'Returns Processing', {
            'title': 'Returns Processing',
            'items': [
                ('new_return', 'New Return', ''),
                ('pend_ret', 'Pending Returns', ''),
                ('ret_hist', 'Return History', ''),
                ('ret_rpts', 'Return Reports', ''),
            ],
        }),
        ('wms', 'Warehouse Management', {
            'title': 'Warehouse Management',
            'items': [
                ('warehouses', 'Warehouses', ''),
                ('bin_master', 'Bin Master', ''),
                ('putaway_rules', 'Put-Away Rules', ''),
                ('pick_lists', 'Pick Lists', ''),
                ('wave_picking', 'Wave Picking', ''),
                ('pack_station', 'Pack Station', ''),
                ('transfers', 'Warehouse Transfers', ''),
                ('rfid_readers', 'RFID Readers', ''),
                ('rfid_tags', 'RFID Tags', ''),
            ],
        }),
    ],
}

_QA_LAB_MENU = {
    'title': 'QA Laboratory Menu',
    'items': [
        ('test_requests', 'Test Requests', {
            'title': 'Test Requests',
            'items': [
                ('new_req', 'New Request', ''),
                ('pend_req', 'Pending Requests', ''),
                ('inprog_req', 'In Progress', ''),
                ('comp_tests', 'Completed Tests', ''),
            ],
        }),
        ('lab_results', 'Lab Results', {
            'title': 'Lab Results',
            'items': [
                ('recent_res', 'Recent Results', ''),
                ('search_res', 'Search Results', ''),
                ('failed', 'Failed Tests', ''),
                ('res_rpts', 'Result Reports', ''),
            ],
        }),
        ('insp_reports', 'Inspection Reports', {
            'title': 'Inspection Reports',
            'items': [
                ('create_rpt', 'Create Report', ''),
                ('pend_rpts', 'Pending Reports', ''),
                ('rpt_arch', 'Report Archive', ''),
                ('rpt_sum', 'Report Summary', ''),
            ],
        }),
        ('non_conformance', 'Non-Conformance', {
            'title': 'Non-Conformance',
            'items': [
                ('new_ncr', 'New NCR', ''),
                ('open_ncrs', 'Open NCRs', ''),
                ('ncr_hist', 'NCR History', ''),
                ('ncr_rpts', 'NCR Reports', ''),
            ],
        }),
        ('calibration', 'Calibration', {
            'title': 'Calibration',
            'items': [
                ('cal_sched', 'Calibration Schedule', ''),
                ('cal_records', 'Calibration Records', ''),
                ('overdue', 'Overdue Items', ''),
                ('cal_rpts', 'Calibration Reports', ''),
            ],
        }),
        ('sample_mgmt', 'Sample Management', {
            'title': 'Sample Management',
            'items': [
                ('recv_sample', 'Receive Sample', ''),
                ('samp_track', 'Sample Tracking', ''),
                ('samp_disp', 'Sample Disposal', ''),
                ('samp_rpts', 'Sample Reports', ''),
            ],
        }),
        ('lab_reports', 'Lab Reports', {
            'title': 'Lab Reports',
            'items': [
                ('daily_rpts', 'Daily Reports', ''),
                ('week_sum', 'Weekly Summary', ''),
                ('month_rpt', 'Monthly Report', ''),
                ('cust_rpts', 'Custom Reports', ''),
            ],
        }),
    ],
}

_QA_MENU = {
    'title': 'Quality Assurance Menu',
    'items': [
        ('qa_lab', 'QA Laboratory Menu', _QA_LAB_MENU),
    ],
}

_PERS_MENU = {
    'title': 'Personnel Menu',
    'items': [
        ('pers_crm', 'Personnel CRM', ''),
        ('reg_form', 'Registration Form', ''),
        ('upd_pass', 'Update Password', ''),
        ('disp_dept', 'Display Department', ''),
        ('dept_entry', 'Dept Entry', ''),
        ('dept_sub', 'Dept Sub Entry', ''),
        ('time_clock', 'Time Clock', _TIME_CLOCK_MENU),
        ('emp_records', 'Employee Records', {
            'title': 'Employee Records',
            'items': [
                ('view_recs', 'View Records', ''),
                ('new_emp', 'New Employee', ''),
                ('upd_rec', 'Update Record', ''),
                ('emp_hist', 'Employment History', ''),
            ],
        }),
        ('benefits', 'Benefits', {
            'title': 'Benefits',
            'items': [
                ('ben_enroll', 'Benefits Enrollment', ''),
                ('ben_sum', 'Benefits Summary', ''),
                ('cobra', 'COBRA Management', ''),
                ('ben_rpts', 'Benefits Reports', ''),
            ],
        }),
        ('perf_review', 'Performance Reviews', {
            'title': 'Performance Reviews',
            'items': [
                ('sched_rev', 'Schedule Review', ''),
                ('pend_revs', 'Pending Reviews', ''),
                ('rev_hist', 'Review History', ''),
                ('perf_rpts', 'Performance Reports', ''),
            ],
        }),
        ('disc_records', 'Disciplinary Records', {
            'title': 'Disciplinary Records',
            'items': [
                ('new_rec', 'New Record', ''),
                ('view_recs', 'View Records', ''),
                ('rec_hist', 'Record History', ''),
                ('disc_rpts', 'Disciplinary Reports', ''),
            ],
        }),
        ('training', 'Training & Development', {
            'title': 'Training & Development',
            'items': [
                ('train_cal', 'Training Calendar', ''),
                ('train_recs', 'Training Records', ''),
                ('course_mgmt', 'Course Management', ''),
                ('cert_track', 'Certification Tracking', ''),
            ],
        }),
        ('onboarding', 'Onboarding', {
            'title': 'Onboarding',
            'items': [
                ('hire_chk', 'New Hire Checklist', ''),
                ('onb_stat', 'Onboarding Status', ''),
                ('doc_coll', 'Document Collection', ''),
                ('onb_rpts', 'Onboarding Reports', ''),
            ],
        }),
    ],
}

_CS_MENU = {
    'title': 'Customer Service Menu',
    'items': [
        ('cust_entry', 'Customer Entry Screen', ''),
        ('open_tickets', 'Open Tickets', {
            'title': 'Open Tickets',
            'items': [
                ('all_tickets', 'View All Tickets', ''),
                ('my_tickets', 'My Tickets', ''),
                ('hi_pri', 'High Priority', ''),
                ('tick_search', 'Ticket Search', ''),
            ],
        }),
        ('cust_accounts', 'Customer Accounts', {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list', 'Account List', ''),
                ('new_acct', 'New Account', ''),
                ('acct_det', 'Account Details', ''),
                ('acct_hist', 'Account History', ''),
            ],
        }),
        ('returns', 'Returns & Refunds', {
            'title': 'Returns & Refunds',
            'items': [
                ('new_return', 'New Return', ''),
                ('pend_ret', 'Pending Returns', ''),
                ('refund_proc', 'Refund Processing', ''),
                ('ret_rpts', 'Returns Reports', ''),
            ],
        }),
        ('knowledge_base', 'Knowledge Base', {
            'title': 'Knowledge Base',
            'items': [
                ('browse', 'Browse Articles', ''),
                ('create_art', 'Create Article', ''),
                ('art_mgmt', 'Article Management', ''),
                ('kb_search', 'Search Knowledge Base', ''),
            ],
        }),
        ('svc_reports', 'Service Reports', {
            'title': 'Service Reports',
            'items': [
                ('daily_rpt', 'Daily Report', ''),
                ('week_sum', 'Weekly Summary', ''),
                ('res_rpts', 'Resolution Reports', ''),
                ('csat_rpts', 'Customer Satisfaction', ''),
            ],
        }),
        ('surveys', 'Surveys & Feedback', {
            'title': 'Surveys & Feedback',
            'items': [
                ('act_surv', 'Active Surveys', ''),
                ('new_surv', 'Create Survey', ''),
                ('surv_res', 'Survey Results', ''),
                ('feed_rpts', 'Feedback Reports', ''),
            ],
        }),
    ],
}

_IT_TECH = {
    'title': 'IT Technician',
    'items': [
        ('it_tasks', 'IT Tasks', ''),
        ('help_desk', 'Help Desk Tickets', {
            'title': 'Help Desk Tickets',
            'items': [
                ('new_ticket', 'New Ticket', ''),
                ('open_tick', 'Open Tickets', ''),
                ('my_tickets', 'My Assigned Tickets', ''),
                ('tick_hist', 'Ticket History', ''),
            ],
        }),
        ('asset_mgmt', 'Asset Management', {
            'title': 'Asset Management',
            'items': [
                ('asset_inv', 'Asset Inventory', ''),
                ('new_asset', 'New Asset', ''),
                ('asset_hist', 'Asset History', ''),
                ('disposition', 'Disposition', ''),
            ],
        }),
        ('net_status', 'Network Status', {
            'title': 'Network Status',
            'items': [
                ('net_dash', 'Network Dashboard', ''),
                ('bw_monitor', 'Bandwidth Monitor', ''),
                ('net_map', 'Network Map', ''),
                ('inc_log', 'Incident Log', ''),
            ],
        }),
        ('sw_install', 'Software Installations', {
            'title': 'Software Installations',
            'items': [
                ('pend_inst', 'Pending Installs', ''),
                ('sw_inv', 'Software Inventory', ''),
                ('lic_mgmt', 'License Management', ''),
                ('inst_hist', 'Installation History', ''),
            ],
        }),
        ('hw_repairs', 'Hardware Repairs', {
            'title': 'Hardware Repairs',
            'items': [
                ('new_repair', 'New Repair Request', ''),
                ('inprog', 'In Progress', ''),
                ('comp_rep', 'Completed Repairs', ''),
                ('rep_hist', 'Repair History', ''),
            ],
        }),
        ('user_accts', 'User Account Management', {
            'title': 'User Account Management',
            'items': [
                ('create_acct', 'Create Account', ''),
                ('reset_pw', 'Reset Password', ''),
                ('acct_stat', 'Account Status', ''),
                ('acct_audit', 'Account Audit', ''),
            ],
        }),
    ],
}

_PURCH_MENU = {
    'title': 'Purchasing Menu',
    'items': [
        ('prod_entry', 'Product Entry', ''),
        ('sup_entry', 'Supplier Entry', ''),
        ('purch_orders', 'Purchase Orders', {
            'title': 'Purchase Orders',
            'items': [
                ('new_po', 'New PO', ''),
                ('open_pos', 'Open POs', ''),
                ('po_status', 'PO Status', ''),
                ('po_hist', 'PO History', ''),
            ],
        }),
        ('vendor_mgmt', 'Vendor Management', {
            'title': 'Vendor Management',
            'items': [
                ('vend_list', 'Vendor List', ''),
                ('new_vend', 'New Vendor', ''),
                ('vend_perf', 'Vendor Performance', ''),
                ('vend_cont', 'Vendor Contracts', ''),
            ],
        }),
        ('purch_reports', 'Purchase Reports', {
            'title': 'Purchase Reports',
            'items': [
                ('spend_sum', 'Spending Summary', ''),
                ('po_rpts', 'PO Reports', ''),
                ('budg_act', 'Budget vs. Actual', ''),
                ('cat_rpts', 'Category Reports', ''),
            ],
        }),
        ('receiving', 'Receiving', {
            'title': 'Receiving',
            'items': [
                ('pend_recv', 'Pending Receipts', ''),
                ('recv_items', 'Receive Items', ''),
                ('disc_rpts', 'Discrepancy Reports', ''),
                ('recv_hist', 'Receiving History', ''),
            ],
        }),
        ('contracts', 'Contract Management', {
            'title': 'Contract Management',
            'items': [
                ('act_cont', 'Active Contracts', ''),
                ('new_cont', 'New Contract', ''),
                ('cont_renew', 'Contract Renewals', ''),
                ('cont_arch', 'Contract Archive', ''),
            ],
        }),
        ('requisitions', 'Requisitions', {
            'title': 'Requisitions',
            'items': [
                ('new_req', 'New Requisition', ''),
                ('pend_appr', 'Pending Approval', ''),
                ('appr_reqs', 'Approved Requisitions',
                 ''),
                ('req_hist', 'Requisition History',
                 ''),
            ],
        }),
    ],
}

MENU_TREE = {
    'accounting': {
        'title': 'Accounting Main Menu',
        'items': [
            ('acct_pay', 'Accounts Payable', ''),
            ('acct_mgr', 'Accounting Manager', {
                'title': 'Accounting Manager',
                'items': [
                    ('ap', 'Accounts Payable', ''),
                    ('rcv', 'Accounts Receivable', ''),
                    ('credit', 'Credit Department', ''),
                    ('pay', 'Payroll Department', ''),
                    ('fin_reports', 'Financial Reports', {
                        'title': 'Financial Reports',
                        'items': [
                            ('inc_stmt', 'Income Statement',
                             ''),
                            ('bal_sheet', 'Balance Sheet',
                             ''),
                            ('cash_flow', 'Cash Flow', ''),
                            ('cust_rpts', 'Custom Reports',
                             ''),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('budg_plan', 'Budget Planning', ''),
                            ('budg_act', 'Budget vs. Actual',
                             ''),
                            ('budg_amend', 'Budget Amendments',
                             ''),
                            ('budg_rpts', 'Budget Reports', ''),
                        ],
                    }),
                    ('audit_mgmt', 'Audit Management', {
                        'title': 'Audit Management',
                        'items': [
                            ('audit_sched', 'Audit Schedule', ''),
                            ('findings', 'Audit Findings', ''),
                            ('corr_act', 'Corrective Actions',
                             ''),
                            ('audit_rpts', 'Audit Reports', ''),
                        ],
                    }),
                ],
            }),
            ('acct_rcv', 'Accounts Receivable', ''),
            ('credit', 'Credit Department', ''),
            ('payroll', 'Payroll Department', ''),
            ('gen_ledger', 'General Ledger', ''),
            ('multi_entity', 'Multi-Entity', {
                'title': 'Multi-Entity',
                'items': [
                    ('companies', 'Companies', ''),
                    ('intercompany', 'Intercompany Transactions',
                     ''),
                    ('consol_fin', 'Consolidated Financials',
                     ''),
                ],
            }),
            ('budget_mgmt', 'Budget Management', {
                'title': 'Budget Management',
                'items': [
                    ('budg_plan', 'Budget Planning', ''),
                    ('budg_act', 'Budget vs. Actual', ''),
                    ('budg_amend', 'Budget Amendments', ''),
                    ('budg_rpts', 'Budget Reports', ''),
                ],
            }),
            ('fin_reports', 'Financial Reports', {
                'title': 'Financial Reports',
                'items': [
                    ('inc_stmt', 'Income Statement', ''),
                    ('bal_sheet', 'Balance Sheet', ''),
                    ('cash_flow', 'Cash Flow', ''),
                    ('cust_rpts', 'Custom Reports', ''),
                ],
            }),
            ('tax_mgmt', 'Tax Management', {
                'title': 'Tax Management',
                'items': [
                    ('tax_cal', 'Tax Calendar', ''),
                    ('tax_filing', 'Tax Filing', ''),
                    ('tax_pay', 'Tax Payments', ''),
                    ('tax_rpts', 'Tax Reports', ''),
                ],
            }),
            ('exp_reports', 'Expense Reports', {
                'title': 'Expense Reports',
                'items': [
                    ('sub_exp', 'Submit Expense', ''),
                    ('pend_appr', 'Pending Approval', ''),
                    ('appr_exp', 'Approved Expenses', ''),
                    ('exp_sum', 'Expense Summary', ''),
                ],
            }),
            ('bank_recon', 'Bank Reconciliation', {
                'title': 'Bank Reconciliation',
                'items': [
                    ('recon_acct', 'Reconcile Account', ''),
                    ('pend_items', 'Pending Items', ''),
                    ('recon_hist', 'Reconciliation History',
                     ''),
                    ('bank_rpts', 'Bank Reports', ''),
                ],
            }),
        ],
    },
    'customer_service': {
        'title': 'Customer Service Main Menu',
        'items': [
            ('cs_mgr', 'CS Manager Menu', {
                'title': 'CS Manager Menu',
                'items': [
                    ('cs_menu', 'Customer Service Menu', _CS_MENU),
                    ('ticket_rpts', 'Ticket Reports', {
                        'title': 'Ticket Reports',
                        'items': [
                            ('daily_tick', 'Daily Ticket Report',
                             ''),
                            ('week_sum', 'Weekly Summary', ''),
                            ('res_analy', 'Resolution Analysis',
                             ''),
                            ('sla_rpts', 'SLA Reports', ''),
                        ],
                    }),
                    ('staff_mgmt', 'Staff Management', {
                        'title': 'Staff Management',
                        'items': [
                            ('staff_sched', 'Staff Schedule',
                             ''),
                            ('perf_met', 'Performance Metrics',
                             ''),
                            ('staff_train', 'Staff Training',
                             ''),
                            ('staff_rpts', 'Staff Reports',
                             ''),
                        ],
                    }),
                    ('cust_sat', 'Customer Satisfaction', {
                        'title': 'Customer Satisfaction',
                        'items': [
                            ('csat_res', 'CSAT Survey Results',
                             ''),
                            ('nps_rpts', 'NPS Reports', ''),
                            ('sat_trends', 'Satisfaction Trends',
                             ''),
                            ('impr_plans', 'Improvement Plans',
                             ''),
                        ],
                    }),
                    ('escalations', 'Escalations', {
                        'title': 'Escalations',
                        'items': [
                            ('act_esc', 'Active Escalations',
                             ''),
                            ('esc_hist', 'Escalation History',
                             ''),
                            ('esc_rpts', 'Escalation Reports',
                             ''),
                            ('res_track', 'Resolution Tracking',
                             ''),
                        ],
                    }),
                ],
            }),
            ('cs_menu', 'Customer Service Menu', _CS_MENU),
        ],
    },
    'engineering': {
        'title': 'Engineering Main Menu',
        'items': [
            ('eng_mgr', 'Engineering Manager', {
                'title': 'Engineering Manager',
                'items': [
                    ('engineers', 'Engineers', ''),
                    ('proj_appr', 'Project Approvals', {
                        'title': 'Project Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals', ''),
                            ('appr_proj', 'Approved Projects', ''),
                            ('rej_proj', 'Rejected Projects', ''),
                            ('appr_hist', 'Approval History', ''),
                        ],
                    }),
                    ('resource', 'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc', 'Resource Allocation', ''),
                            ('cap_plan', 'Capacity Planning', ''),
                            ('res_rpts', 'Resource Reports', ''),
                            ('avail_cal', 'Availability Calendar',
                             ''),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('eng_budg', 'Engineering Budget',
                             ''),
                            ('budg_act', 'Budget vs. Actual',
                             ''),
                            ('cost_rpts', 'Cost Reports', ''),
                            ('budg_req', 'Budget Requests', ''),
                        ],
                    }),
                    ('eng_reports', 'Engineering Reports', {
                        'title': 'Engineering Reports',
                        'items': [
                            ('proj_stat', 'Project Status', ''),
                            ('res_util', 'Resource Utilization', ''),
                            ('kpi_dash', 'KPI Dashboard', ''),
                            ('month_rpts', 'Monthly Reports', ''),
                        ],
                    }),
                ],
            }),
            ('engineers', 'Engineers', ''),
            ('proj_mgmt', 'Project Management', {
                'title': 'Project Management',
                'items': [
                    ('act_proj', 'Active Projects', ''),
                    ('new_proj', 'New Project', ''),
                    ('proj_time', 'Project Timeline', ''),
                    ('proj_rpts', 'Project Reports', ''),
                ],
            }),
            ('design_docs', 'Design Documents', {
                'title': 'Design Documents',
                'items': [
                    ('doc_lib', 'Document Library', ''),
                    ('new_doc', 'New Document', ''),
                    ('doc_review', 'Document Review', ''),
                    ('archive', 'Archive', ''),
                ],
            }),
            ('bom', 'Bill of Materials', {
                'title': 'Bill of Materials',
                'items': [
                    ('bom_list', 'BOM List', ''),
                    ('new_bom', 'Create BOM', ''),
                    ('bom_rev', 'BOM Revision', ''),
                    ('bom_rpts', 'BOM Reports', ''),
                ],
            }),
            ('chg_orders', 'Change Orders', {
                'title': 'Change Orders',
                'items': [
                    ('new_co', 'New Change Order', ''),
                    ('pend_appr', 'Pending Approval', ''),
                    ('appr_chg', 'Approved Changes', ''),
                    ('chg_hist', 'Change History', ''),
                ],
            }),
            ('test_val', 'Test & Validation', {
                'title': 'Test & Validation',
                'items': [
                    ('test_plans', 'Test Plans', ''),
                    ('test_res', 'Test Results', ''),
                    ('val_rpts', 'Validation Reports', ''),
                    ('issue_track', 'Issue Tracking', ''),
                ],
            }),
            ('eng_reports', 'Engineering Reports', {
                'title': 'Engineering Reports',
                'items': [
                    ('proj_stat', 'Project Status', ''),
                    ('design_rev', 'Design Review', ''),
                    ('res_rpt', 'Resource Report', ''),
                    ('cust_rpts', 'Custom Reports', ''),
                ],
            }),
            ('standards', 'Standards & Compliance', {
                'title': 'Standards & Compliance',
                'items': [
                    ('std_lib', 'Standards Library', ''),
                    ('comp_chk', 'Compliance Checklist', ''),
                    ('audit_res', 'Audit Results', ''),
                    ('reg_upd', 'Regulatory Updates', ''),
                ],
            }),
        ],
    },
    'information_tech': {
        'title': 'Information Technology Main Menu',
        'items': [
            ('it_mgr', 'IT Manager', {
                'title': 'IT Manager',
                'items': [
                    ('it_tech', 'IT Technician', _IT_TECH),
                    ('budget', 'Budget & Procurement', {
                        'title': 'Budget & Procurement',
                        'items': [
                            ('it_budg', 'IT Budget', ''),
                            ('hw_proc', 'Hardware Procurement',
                             ''),
                            ('sw_lic', 'Software Licensing', ''),
                            ('proc_rpts', 'Procurement Reports',
                             ''),
                        ],
                    }),
                    ('vendor_con', 'Vendor Contracts', {
                        'title': 'Vendor Contracts',
                        'items': [
                            ('act_cont', 'Active Contracts', ''),
                            ('cont_renew', 'Contract Renewals', ''),
                            ('vend_perf', 'Vendor Performance', ''),
                            ('cont_arch', 'Contract Archive', ''),
                        ],
                    }),
                    ('it_projects', 'IT Projects', {
                        'title': 'IT Projects',
                        'items': [
                            ('act_proj', 'Active Projects', ''),
                            ('proj_pipe', 'Project Pipeline', ''),
                            ('proj_rpts', 'Project Reports', ''),
                            ('res_alloc', 'Resource Allocation', ''),
                        ],
                    }),
                    ('security', 'Security Management', {
                        'title': 'Security Management',
                        'items': [
                            ('sec_dash', 'Security Dashboard', ''),
                            ('inc_rpts', 'Incident Reports', ''),
                            ('vuln_mgmt', 'Vulnerability Management',
                             ''),
                            ('comp_rpts', 'Compliance Reports', ''),
                        ],
                    }),
                ],
            }),
            ('it_tech', 'IT Technician', _IT_TECH),
        ],
    },
    'maintenance': {
        'title': 'Maintenance Main Menu',
        'items': [
            ('maint_mgr', 'Maintenance Manager', {
                'title': 'Maintenance Manager',
                'items': [
                    ('maint', 'Maintenance', _MAINT_MENU),
                    ('wo_approvals', 'Work Order Approvals', {
                        'title': 'Work Order Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals',
                             ''),
                            ('appr_wo', 'Approved Work Orders',
                             ''),
                            ('rej_wo', 'Rejected', ''),
                            ('appr_hist', 'Approval History',
                             ''),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('maint_budg', 'Maintenance Budget',
                             ''),
                            ('budg_act', 'Budget vs. Actual',
                             ''),
                            ('cost_analy', 'Cost Analysis', ''),
                            ('budg_req', 'Budget Requests', ''),
                        ],
                    }),
                    ('maint_rpts', 'Maintenance Reports', {
                        'title': 'Maintenance Reports',
                        'items': [
                            ('daily_rpt', 'Daily Report', ''),
                            ('month_sum', 'Monthly Summary',
                             ''),
                            ('equip_rpts', 'Equipment Reports',
                             ''),
                            ('cost_rpts', 'Cost Reports', ''),
                        ],
                    }),
                ],
            }),
            ('maint', 'Maintenance', _MAINT_MENU),
            ('predictive_maint', 'Predictive Maintenance', ''),
        ],
    },
    'marketing': {
        'title': 'Marketing Main Menu',
        'items': [
            ('mkt_mgr', 'Marketing Manager Menu', {
                'title': 'Marketing Manager Menu',
                'items': [
                    ('mkt_menu', 'Marketing Menu', _MKT_MENU),
                    ('mkt_budget', 'Marketing Budget', {
                        'title': 'Marketing Budget',
                        'items': [
                            ('budg_over', 'Budget Overview', ''),
                            ('budg_camp', 'Budget by Campaign',
                             ''),
                            ('budg_act', 'Budget vs. Actual',
                             ''),
                            ('budg_req', 'Budget Requests', ''),
                        ],
                    }),
                    ('camp_appr', 'Campaign Approvals', {
                        'title': 'Campaign Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals',
                             ''),
                            ('appr_camp', 'Approved Campaigns',
                             ''),
                            ('camp_arch', 'Campaign Archive',
                             ''),
                            ('appr_hist', 'Approval History',
                             ''),
                        ],
                    }),
                    ('mkt_reports', 'Marketing Reports', {
                        'title': 'Marketing Reports',
                        'items': [
                            ('camp_perf', 'Campaign Performance',
                             ''),
                            ('roi_rpts', 'ROI Reports',
                             ''),
                            ('month_sum', 'Monthly Summary',
                             ''),
                            ('kpi_dash', 'KPI Dashboard',
                             ''),
                        ],
                    }),
                ],
            }),
            ('mkt_menu', 'Marketing Menu', _MKT_MENU),
        ],
    },
    'personnel': {
        'title': 'Personnel Main Menu',
        'items': [
            ('pers_mgr', 'Personnel Manager Menu', {
                'title': 'Personnel Manager Menu',
                'items': [
                    ('pers_menu', 'Personnel Menu', _PERS_MENU),
                    ('hiring', 'Hiring & Recruitment', {
                        'title': 'Hiring & Recruitment',
                        'items': [
                            ('open_pos', 'Open Positions',
                             ''),
                            ('appl_track', 'Applicant Tracking',
                             ''),
                            ('int_sched', 'Interview Schedule',
                             ''),
                            ('offer_mgmt', 'Offer Management',
                             ''),
                        ],
                    }),
                    ('term', 'Terminations', {
                        'title': 'Terminations',
                        'items': [
                            ('term_proc', 'Termination Process',
                             ''),
                            ('exit_int', 'Exit Interviews',
                             ''),
                            ('final_pay', 'Final Pay Processing',
                             ''),
                            ('offboard', 'Offboarding Checklist',
                             ''),
                        ],
                    }),
                    ('salary', 'Salary Management', {
                        'title': 'Salary Management',
                        'items': [
                            ('sal_review', 'Salary Review',
                             ''),
                            ('sal_adj', 'Salary Adjustments',
                             ''),
                            ('comp_rpts', 'Compensation Reports',
                             ''),
                            ('pay_grades', 'Pay Grades',
                             ''),
                        ],
                    }),
                    ('hr_reports', 'HR Reports', {
                        'title': 'HR Reports',
                        'items': [
                            ('hd_rpt', 'Headcount Report',
                             ''),
                            ('turn_rpt', 'Turnover Report',
                             ''),
                            ('comp_rpts', 'Compliance Reports',
                             ''),
                            ('month_sum', 'Monthly Summary',
                             ''),
                        ],
                    }),
                ],
            }),
            ('pers_menu', 'Personnel Menu', _PERS_MENU),
        ],
    },
    'production': {
        'title': 'Production Main Menu',
        'items': [
            ('prod_mgr', 'Production Manager', {
                'title': 'Production Manager',
                'items': [
                    ('prod', 'Production', _PROD_MENU),
                    ('shipping', 'Shipping', _SHIP_MENU),
                    ('prod_reports', 'Production Reports', {
                        'title': 'Production Reports',
                        'items': [
                            ('daily_prod', 'Daily Production',
                             ''),
                            ('week_sum', 'Weekly Summary', ''),
                            ('eff_rpts', 'Efficiency Reports',
                             ''),
                            ('kpi_dash', 'KPI Dashboard', ''),
                        ],
                    }),
                    ('resource', 'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc', 'Resource Allocation',
                             ''),
                            ('cap_plan', 'Capacity Planning',
                             ''),
                            ('res_rpts', 'Resource Reports',
                             ''),
                            ('wf_plan', 'Workforce Planning',
                             ''),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('prod_budg', 'Production Budget',
                             ''),
                            ('cost_analy', 'Cost Analysis', ''),
                            ('budg_act', 'Budget vs. Actual',
                             ''),
                            ('budg_rpts', 'Budget Reports', ''),
                        ],
                    }),
                ],
            }),
            ('prod', 'Production', _PROD_MENU),
            ('shipping', 'Shipping', _SHIP_MENU),
            ('shop_floor', 'Shop Floor', {
                'title': 'Shop Floor',
                'items': [
                    ('sf_entry', 'Production/Downtime Entry',
                     ''),
                    ('sf_shift_plan', 'Shift Plan', ''),
                    ('sf_dashboard', 'Live OEE Dashboard',
                     ''),
                    ('sf_tv', 'Shop Floor TV Display', ''),
                ],
            }),
        ],
    },
    'purchasing': {
        'title': 'Purchasing Main Menu',
        'items': [
            ('purch_mgr', 'Purchasing Manager Menu', {
                'title': 'Purchasing Manager Menu',
                'items': [
                    ('purch', 'Purchasing Menu', _PURCH_MENU),
                    ('po_approvals', 'PO Approvals', {
                        'title': 'PO Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals',
                             ''),
                            ('appr_pos', 'Approved POs',
                             ''),
                            ('rej_pos', 'Rejected POs',
                             ''),
                            ('appr_hist', 'Approval History',
                             ''),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('purch_budg', 'Purchasing Budget',
                             ''),
                            ('budg_act', 'Budget vs. Actual',
                             ''),
                            ('spend_analy', 'Spending Analysis',
                             ''),
                            ('budg_rpts', 'Budget Reports', ''),
                        ],
                    }),
                    ('vendor_mgmt', 'Vendor Management', {
                        'title': 'Vendor Management',
                        'items': [
                            ('vend_list', 'Vendor List',
                             ''),
                            ('vend_eval', 'Vendor Evaluation',
                             ''),
                            ('vend_perf', 'Vendor Performance',
                             ''),
                            ('appr_vend', 'Approved Vendors',
                             ''),
                        ],
                    }),
                    ('purch_rpts', 'Purchasing Reports', {
                        'title': 'Purchasing Reports',
                        'items': [
                            ('spend_rpt', 'Spending Report',
                             ''),
                            ('vend_rpt', 'Vendor Report',
                             ''),
                            ('cat_analy', 'Category Analysis',
                             ''),
                            ('month_sum', 'Monthly Summary',
                             ''),
                        ],
                    }),
                    ('contracts', 'Contract Management', {
                        'title': 'Contract Management',
                        'items': [
                            ('act_cont', 'Active Contracts',
                             ''),
                            ('pend_renew', 'Pending Renewals',
                             ''),
                            ('cont_arch', 'Contract Archive',
                             ''),
                            ('cont_rpts', 'Contract Reports',
                             ''),
                        ],
                    }),
                    ('consultants', 'Consultant Management', {
                        'title': 'Consultant Management',
                        'items': [
                            ('cons_list', 'Consultants', ''),
                            ('cons_eng', 'Engagements', ''),
                            ('cons_inv', 'Invoices', ''),
                            ('cons_rpt', 'Spend Report', ''),
                        ],
                    }),
                ],
            }),
            ('purch', 'Purchasing Menu', _PURCH_MENU),
        ],
    },
    'quality_assurance': {
        'title': 'Quality Assurance Main Menu',
        'items': [
            ('qa_mgr', 'QA Manager Menu', {
                'title': 'QA Manager Menu',
                'items': [
                    ('qa_menu', 'Quality Assurance Menu', _QA_MENU),
                    ('audit_mgmt', 'Audit Management', {
                        'title': 'Audit Management',
                        'items': [
                            ('audit_sched', 'Audit Schedule',
                             ''),
                            ('act_audits', 'Active Audits', ''),
                            ('findings', 'Audit Findings', ''),
                            ('corr_act', 'Corrective Actions',
                             ''),
                        ],
                    }),
                    ('compliance', 'Compliance', {
                        'title': 'Compliance',
                        'items': [
                            ('comp_dash', 'Compliance Dashboard',
                             ''),
                            ('reg_req', 'Regulatory Requirements',
                             ''),
                            ('comp_rpts', 'Compliance Reports',
                             ''),
                            ('non_comp', 'Non-Compliance Issues',
                             ''),
                        ],
                    }),
                    ('corr_action', 'Corrective Actions', {
                        'title': 'Corrective Actions',
                        'items': [
                            ('open_cars', 'Open CARs', ''),
                            ('inprog_cars', 'In Progress', ''),
                            ('closed_cars', 'Closed CARs', ''),
                            ('car_rpts', 'CAR Reports', ''),
                        ],
                    }),
                    ('qa_reports', 'QA Reports', {
                        'title': 'QA Reports',
                        'items': [
                            ('daily_qa', 'Daily QA Report', ''),
                            ('week_sum', 'Weekly Summary', ''),
                            ('month_rpt', 'Monthly Report', ''),
                            ('kpi_dash', 'KPI Dashboard', ''),
                        ],
                    }),
                    ('supp_qual', 'Supplier Quality', {
                        'title': 'Supplier Quality',
                        'items': [
                            ('supp_score', 'Supplier Scorecards',
                             ''),
                            ('inc_insp', 'Incoming Inspection',
                             ''),
                            ('sampling_plans', 'Sampling Plans',
                             ''),
                            ('supp_audit', 'Supplier Audits',
                             ''),
                            ('supp_rpts', 'Supplier Reports',
                             ''),
                        ],
                    }),
                    ('cust_comp', 'Customer Complaints', {
                        'title': 'Customer Complaints',
                        'items': [
                            ('new_comp', 'New Complaint', ''),
                            ('open_comp', 'Open Complaints', ''),
                            ('res_track', 'Resolution Tracking',
                             ''),
                            ('comp_rpts', 'Complaint Reports',
                             ''),
                        ],
                    }),
                    ('doc_control', 'Document Control', {
                        'title': 'Document Control',
                        'items': [
                            ('doc_lib', 'Document Library', ''),
                            ('new_doc', 'New Document', ''),
                            ('doc_review', 'Document Review',
                             ''),
                            ('rev_hist', 'Revision History', ''),
                        ],
                    }),
                ],
            }),
            ('qa_menu', 'Quality Assurance Menu', _QA_MENU),
        ],
    },
    'sales': {
        'title': 'Sales Main Menu',
        'items': [
            ('sales_mgr', 'Sales Manager Menu', {
                'title': 'Sales Manager Menu',
                'items': [
                    ('sales', 'Sales Menu', _SALES_MENU),
                    ('sales_targets', 'Sales Targets', {
                        'title': 'Sales Targets',
                        'items': [
                            ('set_tgt', 'Set Targets', ''),
                            ('tgt_act', 'Target vs. Actual',
                             ''),
                            ('tgt_rep', 'Target by Rep', ''),
                            ('tgt_rpts', 'Target Reports',
                             ''),
                        ],
                    }),
                    ('territory', 'Territory Management', {
                        'title': 'Territory Management',
                        'items': [
                            ('terr_map', 'Territory Map', ''),
                            ('terr_assign', 'Territory Assignments',
                             ''),
                            ('terr_perf', 'Territory Performance',
                             ''),
                            ('terr_rpts', 'Territory Reports',
                             ''),
                        ],
                    }),
                    ('commission', 'Commission Tracking', {
                        'title': 'Commission Tracking',
                        'items': [
                            ('comm_calc', 'Commission Calculator',
                             ''),
                            ('comm_rpts', 'Commission Reports',
                             ''),
                            ('pay_hist', 'Payment History',
                             ''),
                            ('comm_plans', 'Commission Plans',
                             ''),
                        ],
                    }),
                    ('staff_perf', 'Staff Performance', {
                        'title': 'Staff Performance',
                        'items': [
                            ('perf_dash', 'Performance Dashboard',
                             ''),
                            ('rep_rank', 'Rep Rankings', ''),
                            ('perf_revs', 'Performance Reviews',
                             ''),
                            ('coaching', 'Coaching Notes',
                             ''),
                        ],
                    }),
                ],
            }),
            ('sales', 'Sales Menu', _SALES_MENU),
            ('demand_forecast', 'AI Demand Forecast', ''),
        ],
    },
    'budget_management': {
        'title': 'Budget Management',
        'items': [
            ('budget_mgr', 'Budget Manager', {
                'title': 'Budget Manager',
                'items': [
                    ('bud_overview', 'Budgets', ''),
                    ('bud_detail_mgr', 'Budget Detail', ''),
                    ('bva_mgr', 'Budget vs. Actual', ''),
                    ('variance_mgr', 'Variance Report', ''),
                    ('dept_summary', 'Department Summaries',
                     ''),
                    ('approval_wf', 'Approval Workflow', ''),
                ],
            }),
            ('budgets', 'Budgets', ''),
            ('bud_detail', 'Budget Detail', ''),
            ('bva', 'Budget vs. Actual', ''),
            ('variance', 'Variance Report', ''),
        ],
    },
    'finance': {
        'title': 'Finance Main Menu',
        'items': [
            ('fin_mgr', 'Finance Manager', {
                'title': 'Finance Manager',
                'items': [
                    ('fin_plan', 'Financial Planning', ''),
                    ('fin_forecast', 'Budget & Forecasting',
                     ''),
                    ('treasury_mgmt', 'Treasury Management',
                     ''),
                    ('invest_mgmt', 'Investment Management',
                     ''),
                    ('fin_rpts_mgr', 'Financial Reports',
                     ''),
                ],
            }),
            ('fin_analysis', 'Financial Analysis', ''),
            ('fin_reporting', 'Financial Reporting', ''),
            ('treasury_ops', 'Treasury Operations', ''),
            ('capital_mgmt', 'Capital Management', ''),
            ('tax_planning', 'Tax Planning', ''),
        ],
    },
    'legal': {
        'title': 'Legal Main Menu',
        'items': [
            ('legal_mgr', 'Legal Manager', {
                'title': 'Legal Manager',
                'items': [
                    ('contracts_mgmt', 'Contract Management',
                     ''),
                    ('litigation_mgmt', 'Litigation Management',
                     ''),
                    ('compliance_mgmt', 'Compliance Management',
                     ''),
                    ('corp_gov', 'Corporate Governance', ''),
                ],
            }),
            ('contracts', 'Contracts', ''),
            ('compliance', 'Compliance', ''),
            ('litigation', 'Litigation', ''),
            ('ip_mgmt', 'Intellectual Property', ''),
            ('emp_law', 'Employment Law', ''),
        ],
    },
    'risk_management': {
        'title': 'Risk Management Main Menu',
        'items': [
            ('risk_mgr', 'Risk Manager', {
                'title': 'Risk Manager',
                'items': [
                    ('risk_register_mgr', 'Risk Register', ''),
                    ('kri', 'Key Risk Indicators', ''),
                    ('biz_continuity', 'Business Continuity',
                     ''),
                    ('audit_compliance', 'Audit & Compliance',
                     ''),
                ],
            }),
            ('risk_assess', 'Risk Assessment', ''),
            ('risk_register', 'Risk Register', ''),
            ('insurance', 'Insurance Management', ''),
            ('biz_cont', 'Business Continuity', ''),
            ('comp_audit', 'Compliance & Audit', ''),
        ],
    },
    'reports': {
        'title': 'Reports',
        'items': [
            ('rpt_dashboard', 'Dashboard', ''),
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
    ('accounting', 'Accounting'),
    ('customer_service', 'Customer Service'),
    ('engineering', 'Engineering'),
    ('information_tech', 'Information Tech'),
    ('maintenance', 'Maintenance'),
    ('marketing', 'Marketing'),
    ('personnel', 'Personnel'),
    ('production', 'Production'),
    ('inventory', 'Inventory'),
    ('purchasing', 'Purchasing'),
    ('quality_assurance', 'Quality Assurance'),
    ('sales', 'Sales'),
    ('budget_management', 'Budget Management'),
    ('finance', 'Finance'),
    ('legal', 'Legal'),
    ('risk_management', 'Risk Management'),
    ('reports', 'Reports'),
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
