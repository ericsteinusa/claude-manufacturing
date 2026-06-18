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
                ('punch_in', 'Record Clock In', 'time_clock_menu.py'),
                ('punch_out', 'Record Clock Out', 'time_clock_menu.py'),
                ('cur_status', 'Current Status', 'time_clock_menu.py'),
            ],
        }),
        ('view_hours', 'View Hours', {
            'title': 'View Hours',
            'items': [
                ('today_hrs', "Today's Hours", 'time_clock_menu.py'),
                ('week_hrs', 'Weekly Hours', 'time_clock_menu.py'),
                ('month_hrs', 'Monthly Hours', 'time_clock_menu.py'),
                ('period_hrs', 'Pay Period Hours', 'time_clock_menu.py'),
            ],
        }),
        ('time_off', 'Time Off Requests', {
            'title': 'Time Off Requests',
            'items': [
                ('submit_req', 'Submit Request', 'time_clock_menu.py'),
                ('pend_req', 'Pending Requests', 'time_clock_menu.py'),
                ('appr_req', 'Approved Requests', 'time_clock_menu.py'),
                ('req_hist', 'Request History', 'time_clock_menu.py'),
            ],
        }),
        ('schedules', 'Schedules', {
            'title': 'Schedules',
            'items': [
                ('my_sched', 'My Schedule', 'time_clock_menu.py'),
                ('upcoming', 'Upcoming Shifts', 'time_clock_menu.py'),
                ('sched_cal', 'Schedule Calendar', 'time_clock_menu.py'),
                ('swap_req', 'Swap Requests', 'time_clock_menu.py'),
            ],
        }),
        ('ot_reports', 'Overtime Reports', {
            'title': 'Overtime Reports',
            'items': [
                ('cur_ot', 'Current Period OT', 'time_clock_menu.py'),
                ('hist_ot', 'Historical OT', 'time_clock_menu.py'),
                ('ot_by_emp', 'OT by Employee', 'time_clock_menu.py'),
                ('ot_appr', 'OT Approval', 'time_clock_menu.py'),
            ],
        }),
        ('attend_reports', 'Attendance Reports', {
            'title': 'Attendance Reports',
            'items': [
                ('daily_att', 'Daily Attendance', 'time_clock_menu.py'),
                ('month_sum', 'Monthly Summary', 'time_clock_menu.py'),
                ('tard_rpt', 'Tardiness Report', 'time_clock_menu.py'),
                ('abs_rpt', 'Absence Report', 'time_clock_menu.py'),
            ],
        }),
        ('shift_mgmt', 'Shift Management', {
            'title': 'Shift Management',
            'items': [
                ('view_shfts', 'View Shifts', 'time_clock_menu.py'),
                ('assign_emp', 'Assign Employees', 'time_clock_menu.py'),
                ('shft_tmpl', 'Shift Templates', 'time_clock_menu.py'),
                ('swap_mgmt', 'Swap Management', 'time_clock_menu.py'),
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
                ('create_wo', 'Create Work Order', 'work_orders.py'),
                ('open_wo', 'Open Work Orders', 'work_orders.py'),
                ('inprog_wo', 'In Progress', 'work_orders.py'),
                ('comp_wo', 'Completed', 'work_orders.py'),
            ],
        }),
        ('maint_schedule', 'Maintenance Schedule', {
            'title': 'Maintenance Schedule',
            'items': [
                ('daily_sched', 'Daily Schedule', 'Maint_Maint_menu.py'),
                ('week_sched', 'Weekly Schedule', 'Maint_Maint_menu.py'),
                ('month_sched', 'Monthly Schedule', 'Maint_Maint_menu.py'),
                ('annual_plan', 'Annual Plan', 'Maint_Maint_menu.py'),
            ],
        }),
        ('equip_maint', 'Equipment Maintenance', {
            'title': 'Equipment Maintenance',
            'items': [
                ('equip_list', 'Equipment List', 'Maint_Maint_menu.py'),
                ('maint_hist', 'Maintenance History', 'Maint_Maint_menu.py'),
                ('svc_records', 'Service Records', 'Maint_Maint_menu.py'),
                ('equip_stat', 'Equipment Status', 'Maint_Maint_menu.py'),
            ],
        }),
        ('parts_inv', 'Parts Inventory', {
            'title': 'Parts Inventory',
            'items': [
                ('view_inv', 'View Inventory', 'inventory.py'),
                ('parts_req', 'Parts Request', 'inventory.py'),
                ('reorder', 'Reorder List', 'inventory.py'),
                ('parts_hist', 'Parts History', 'inventory.py'),
            ],
        }),
        ('maint_reports', 'Maintenance Reports', {
            'title': 'Maintenance Reports',
            'items': [
                ('daily_rpt', 'Daily Report', 'Maint_Maint_menu.py'),
                ('week_rpt', 'Weekly Report', 'Maint_Maint_menu.py'),
                ('cost_analy', 'Cost Analysis', 'Maint_Maint_menu.py'),
                ('down_rpt', 'Downtime Report', 'Maint_Maint_menu.py'),
            ],
        }),
        ('safety_insp', 'Safety Inspections', {
            'title': 'Safety Inspections',
            'items': [
                ('sched_insp', 'Schedule Inspection', 'Maint_Maint_menu.py'),
                ('insp_chk', 'Inspection Checklist', 'Maint_Maint_menu.py'),
                ('insp_res', 'Inspection Results', 'Maint_Maint_menu.py'),
                ('corr_act', 'Corrective Actions', 'Maint_Maint_menu.py'),
            ],
        }),
        ('prev_maint', 'Preventive Maintenance', {
            'title': 'Preventive Maintenance',
            'items': [
                ('pm_sched', 'PM Schedule', 'Maint_Maint_menu.py'),
                ('pm_chk', 'PM Checklists', 'Maint_Maint_menu.py'),
                ('pm_hist', 'PM History', 'Maint_Maint_menu.py'),
                ('pm_rpts', 'PM Reports', 'Maint_Maint_menu.py'),
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
                ('act_camp', 'Active Campaigns', 'marketing_menu.py'),
                ('new_camp', 'Create Campaign', 'marketing_menu.py'),
                ('camp_cal', 'Campaign Calendar', 'marketing_menu.py'),
                ('camp_res', 'Campaign Results', 'marketing_menu.py'),
            ],
        }),
        ('mkt_research', 'Market Research', {
            'title': 'Market Research',
            'items': [
                ('res_proj', 'Research Projects', 'marketing_menu.py'),
                ('comp_analy', 'Competitor Analysis', 'marketing_menu.py'),
                ('surv_mgmt', 'Survey Management', 'marketing_menu.py'),
                ('mkt_trends', 'Market Trends', 'marketing_menu.py'),
            ],
        }),
        ('advertising', 'Advertising', {
            'title': 'Advertising',
            'items': [
                ('ad_mgmt', 'Ad Management', 'marketing_menu.py'),
                ('ad_budget', 'Ad Budget', 'marketing_menu.py'),
                ('ad_perf', 'Ad Performance', 'marketing_menu.py'),
                ('ad_cal', 'Ad Calendar', 'marketing_menu.py'),
            ],
        }),
        ('analytics', 'Analytics', {
            'title': 'Analytics',
            'items': [
                ('web_analy', 'Website Analytics', 'marketing_menu.py'),
                ('camp_analy', 'Campaign Analytics', 'marketing_menu.py'),
                ('sales_analy', 'Sales Analytics', 'marketing_menu.py'),
                ('cust_rpts', 'Custom Reports', 'marketing_menu.py'),
            ],
        }),
        ('content_mgmt', 'Content Management', {
            'title': 'Content Management',
            'items': [
                ('cont_cal', 'Content Calendar', 'marketing_menu.py'),
                ('blog', 'Blog Posts', 'marketing_menu.py'),
                ('mkt_mat', 'Marketing Materials', 'marketing_menu.py'),
                ('cont_arch', 'Content Archive', 'marketing_menu.py'),
            ],
        }),
        ('social_media', 'Social Media', {
            'title': 'Social Media',
            'items': [
                ('post_mgmt', 'Post Management', 'marketing_menu.py'),
                ('social_cal', 'Social Calendar', 'marketing_menu.py'),
                ('eng_rpts', 'Engagement Reports', 'marketing_menu.py'),
                ('acct_mgmt', 'Account Management', 'marketing_menu.py'),
            ],
        }),
        ('email_mkt', 'Email Marketing', {
            'title': 'Email Marketing',
            'items': [
                ('email_camp', 'Email Campaigns', 'marketing_menu.py'),
                ('sub_lists', 'Subscriber Lists', 'marketing_menu.py'),
                ('email_tmpl', 'Email Templates', 'marketing_menu.py'),
                ('email_analy', 'Email Analytics', 'marketing_menu.py'),
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
                ('new_order', 'New Order', 'sales_orders.py'),
                ('open_orders', 'Open Orders', 'sales_orders.py'),
                ('order_hist', 'Order History', 'sales_orders.py'),
                ('order_stat', 'Order Status', 'sales_orders.py'),
            ],
        }),
        ('cust_accounts', 'Customer Accounts', {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list', 'Account List', 'customers.py'),
                ('new_acct', 'New Account', 'customers.py'),
                ('acct_det', 'Account Details', 'customers.py'),
                ('acct_hist', 'Account History', 'customers.py'),
            ],
        }),
        ('sales_reports', 'Sales Reports', {
            'title': 'Sales Reports',
            'items': [
                ('daily_sales', 'Daily Sales', 'Sales_menu.py'),
                ('month_sales', 'Monthly Sales', 'Sales_menu.py'),
                ('annual_rpt', 'Annual Report', 'Sales_menu.py'),
                ('by_rep', 'Sales by Rep', 'Sales_menu.py'),
            ],
        }),
        ('quotes', 'Quotes', {
            'title': 'Quotes',
            'items': [
                ('new_quote', 'Create Quote', 'Sales_menu.py'),
                ('act_quotes', 'Active Quotes', 'Sales_menu.py'),
                ('quote_hist', 'Quote History', 'Sales_menu.py'),
                ('conv_order', 'Convert to Order', 'Sales_menu.py'),
            ],
        }),
        ('leads', 'Leads & Opportunities', {
            'title': 'Leads & Opportunities',
            'items': [
                ('new_lead', 'New Lead', 'Sales_menu.py'),
                ('act_leads', 'Active Leads', 'Sales_menu.py'),
                ('opp_pipe', 'Opportunities Pipeline', 'Sales_menu.py'),
                ('lead_rpts', 'Lead Reports', 'Sales_menu.py'),
            ],
        }),
        ('contracts', 'Contracts', {
            'title': 'Contracts',
            'items': [
                ('act_cont', 'Active Contracts', 'Sales_menu.py'),
                ('new_cont', 'Create Contract', 'Sales_menu.py'),
                ('cont_renew', 'Contract Renewals', 'Sales_menu.py'),
                ('cont_arch', 'Contract Archive', 'Sales_menu.py'),
            ],
        }),
        ('forecasting', 'Sales Forecasting', {
            'title': 'Sales Forecasting',
            'items': [
                ('cur_fore', 'Current Forecast', 'Sales_menu.py'),
                ('fore_rep', 'Forecast by Rep', 'Sales_menu.py'),
                ('fore_prod', 'Forecast by Product', 'Sales_menu.py'),
                ('fore_rpts', 'Forecast Reports', 'Sales_menu.py'),
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
                ('create_wo', 'Create Work Order', 'work_orders.py'),
                ('open_wo', 'Open Work Orders', 'work_orders.py'),
                ('inprog_wo', 'In Progress', 'work_orders.py'),
                ('comp_wo', 'Completed', 'work_orders.py'),
            ],
        }),
        ('prod_schedule', 'Production Schedule', {
            'title': 'Production Schedule',
            'items': [
                ('daily_sched', 'Daily Schedule', 'prod_prod_menu.py'),
                ('week_sched', 'Weekly Schedule', 'prod_prod_menu.py'),
                ('month_sched', 'Monthly Schedule', 'prod_prod_menu.py'),
                ('sched_cal', 'Schedule Calendar', 'prod_prod_menu.py'),
            ],
        }),
        ('inventory', 'Inventory', {
            'title': 'Inventory',
            'items': [
                ('raw_mat', 'Raw Materials', 'inventory.py'),
                ('fin_goods', 'Finished Goods', 'inventory.py'),
                ('wip_inv', 'WIP Inventory', 'inventory.py'),
                ('inv_rpts', 'Inventory Reports', 'inventory.py'),
            ],
        }),
        ('equip_status', 'Equipment Status', {
            'title': 'Equipment Status',
            'items': [
                ('equip_list', 'Equipment List', 'prod_prod_menu.py'),
                ('stat_dash', 'Status Dashboard', 'prod_prod_menu.py'),
                ('down_log', 'Downtime Log', 'prod_prod_menu.py'),
                ('maint_req', 'Maintenance Requests', 'prod_prod_menu.py'),
            ],
        }),
        ('quality_ctrl', 'Quality Control', {
            'title': 'Quality Control',
            'items': [
                ('insp_res', 'Inspection Results', 'prod_prod_menu.py'),
                ('non_conf', 'Non-Conformances', 'prod_prod_menu.py'),
                ('qc_rpts', 'QC Reports', 'prod_prod_menu.py'),
                ('rej_analy', 'Reject Analysis', 'prod_prod_menu.py'),
            ],
        }),
        ('prod_reports', 'Production Reports', {
            'title': 'Production Reports',
            'items': [
                ('daily_prod', 'Daily Production', 'prod_prod_menu.py'),
                ('week_sum', 'Weekly Summary', 'prod_prod_menu.py'),
                ('eff_rpt', 'Efficiency Report', 'prod_prod_menu.py'),
                ('scrap_rpt', 'Scrap Report', 'prod_prod_menu.py'),
            ],
        }),
        ('labor_tracking', 'Labor Tracking', {
            'title': 'Labor Tracking',
            'items': [
                ('cur_labor', 'Current Labor', 'prod_prod_menu.py'),
                ('labor_shft', 'Labor by Shift', 'prod_prod_menu.py'),
                ('labor_job', 'Labor by Job', 'prod_prod_menu.py'),
                ('labor_rpts', 'Labor Reports', 'prod_prod_menu.py'),
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
                ('new_ship', 'New Shipment', 'prod_ship_dept.py'),
                ('pend_ship', 'Pending Shipments', 'prod_ship_dept.py'),
                ('shipped', 'Shipped Orders', 'prod_ship_dept.py'),
                ('deliv_conf', 'Delivery Confirmation', 'prod_ship_dept.py'),
            ],
        }),
        ('ship_schedule', 'Shipping Schedule', {
            'title': 'Shipping Schedule',
            'items': [
                ('today_sched', "Today's Schedule", 'prod_ship_dept.py'),
                ('week_sched', 'Weekly Schedule', 'prod_ship_dept.py'),
                ('sched_cal', 'Schedule Calendar', 'prod_ship_dept.py'),
                ('rush_orders', 'Rush Orders', 'prod_ship_dept.py'),
            ],
        }),
        ('receiving', 'Receiving', {
            'title': 'Receiving',
            'items': [
                ('inbound', 'Inbound Shipments', 'prod_ship_dept.py'),
                ('recv_items', 'Receive Items', 'prod_ship_dept.py'),
                ('recv_rpts', 'Receiving Reports', 'prod_ship_dept.py'),
                ('disc_rpts', 'Discrepancy Reports', 'prod_ship_dept.py'),
            ],
        }),
        ('carrier_mgmt', 'Carrier Management', {
            'title': 'Carrier Management',
            'items': [
                ('carr_list', 'Carrier List', 'prod_ship_dept.py'),
                ('carr_rates', 'Carrier Rates', 'prod_ship_dept.py'),
                ('perf_rpts', 'Performance Reports', 'prod_ship_dept.py'),
                ('carr_cont', 'Carrier Contracts', 'prod_ship_dept.py'),
            ],
        }),
        ('tracking', 'Tracking', {
            'title': 'Tracking',
            'items': [
                ('track_ship', 'Track Shipment', 'prod_ship_dept.py'),
                ('track_dash', 'Tracking Dashboard', 'prod_ship_dept.py'),
                ('deliv_stat', 'Delivery Status', 'prod_ship_dept.py'),
                ('exc_rpts', 'Exception Reports', 'prod_ship_dept.py'),
            ],
        }),
        ('ship_reports', 'Shipping Reports', {
            'title': 'Shipping Reports',
            'items': [
                ('daily_rpt', 'Daily Report', 'prod_ship_dept.py'),
                ('week_sum', 'Weekly Summary', 'prod_ship_dept.py'),
                ('cost_analy', 'Cost Analysis', 'prod_ship_dept.py'),
                ('perf_rpt', 'Performance Report', 'prod_ship_dept.py'),
            ],
        }),
        ('returns_proc', 'Returns Processing', {
            'title': 'Returns Processing',
            'items': [
                ('new_return', 'New Return', 'prod_ship_dept.py'),
                ('pend_ret', 'Pending Returns', 'prod_ship_dept.py'),
                ('ret_hist', 'Return History', 'prod_ship_dept.py'),
                ('ret_rpts', 'Return Reports', 'prod_ship_dept.py'),
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
                ('new_req', 'New Request', 'QA_Lab_menu.py'),
                ('pend_req', 'Pending Requests', 'QA_Lab_menu.py'),
                ('inprog_req', 'In Progress', 'QA_Lab_menu.py'),
                ('comp_tests', 'Completed Tests', 'QA_Lab_menu.py'),
            ],
        }),
        ('lab_results', 'Lab Results', {
            'title': 'Lab Results',
            'items': [
                ('recent_res', 'Recent Results', 'QA_Lab_menu.py'),
                ('search_res', 'Search Results', 'QA_Lab_menu.py'),
                ('failed', 'Failed Tests', 'QA_Lab_menu.py'),
                ('res_rpts', 'Result Reports', 'QA_Lab_menu.py'),
            ],
        }),
        ('insp_reports', 'Inspection Reports', {
            'title': 'Inspection Reports',
            'items': [
                ('create_rpt', 'Create Report', 'QA_Lab_menu.py'),
                ('pend_rpts', 'Pending Reports', 'QA_Lab_menu.py'),
                ('rpt_arch', 'Report Archive', 'QA_Lab_menu.py'),
                ('rpt_sum', 'Report Summary', 'QA_Lab_menu.py'),
            ],
        }),
        ('non_conformance', 'Non-Conformance', {
            'title': 'Non-Conformance',
            'items': [
                ('new_ncr', 'New NCR', 'QA_Lab_menu.py'),
                ('open_ncrs', 'Open NCRs', 'QA_Lab_menu.py'),
                ('ncr_hist', 'NCR History', 'QA_Lab_menu.py'),
                ('ncr_rpts', 'NCR Reports', 'QA_Lab_menu.py'),
            ],
        }),
        ('calibration', 'Calibration', {
            'title': 'Calibration',
            'items': [
                ('cal_sched', 'Calibration Schedule', 'QA_Lab_menu.py'),
                ('cal_records', 'Calibration Records', 'QA_Lab_menu.py'),
                ('overdue', 'Overdue Items', 'QA_Lab_menu.py'),
                ('cal_rpts', 'Calibration Reports', 'QA_Lab_menu.py'),
            ],
        }),
        ('sample_mgmt', 'Sample Management', {
            'title': 'Sample Management',
            'items': [
                ('recv_sample', 'Receive Sample', 'QA_Lab_menu.py'),
                ('samp_track', 'Sample Tracking', 'QA_Lab_menu.py'),
                ('samp_disp', 'Sample Disposal', 'QA_Lab_menu.py'),
                ('samp_rpts', 'Sample Reports', 'QA_Lab_menu.py'),
            ],
        }),
        ('lab_reports', 'Lab Reports', {
            'title': 'Lab Reports',
            'items': [
                ('daily_rpts', 'Daily Reports', 'QA_Lab_menu.py'),
                ('week_sum', 'Weekly Summary', 'QA_Lab_menu.py'),
                ('month_rpt', 'Monthly Report', 'QA_Lab_menu.py'),
                ('cust_rpts', 'Custom Reports', 'QA_Lab_menu.py'),
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
        ('pers_crm', 'Personnel CRM', 'personnel_crm.py'),
        ('reg_form', 'Registration Form', 'registration_form.py'),
        ('upd_pass', 'Update Password', 'update_users.py'),
        ('disp_dept', 'Display Department', 'display_people_department.py'),
        ('dept_entry', 'Dept Entry', 'dept_entry.py'),
        ('dept_sub', 'Dept Sub Entry', 'dept_sub_entry.py'),
        ('time_clock', 'Time Clock', _TIME_CLOCK_MENU),
        ('emp_records', 'Employee Records', {
            'title': 'Employee Records',
            'items': [
                ('view_recs', 'View Records', 'employees.py'),
                ('new_emp', 'New Employee', 'employees.py'),
                ('upd_rec', 'Update Record', 'employees.py'),
                ('emp_hist', 'Employment History', 'employees.py'),
            ],
        }),
        ('benefits', 'Benefits', {
            'title': 'Benefits',
            'items': [
                ('ben_enroll', 'Benefits Enrollment', 'personnel_crm.py'),
                ('ben_sum', 'Benefits Summary', 'personnel_crm.py'),
                ('cobra', 'COBRA Management', 'personnel_crm.py'),
                ('ben_rpts', 'Benefits Reports', 'personnel_crm.py'),
            ],
        }),
        ('perf_review', 'Performance Reviews', {
            'title': 'Performance Reviews',
            'items': [
                ('sched_rev', 'Schedule Review', 'personnel_crm.py'),
                ('pend_revs', 'Pending Reviews', 'personnel_crm.py'),
                ('rev_hist', 'Review History', 'personnel_crm.py'),
                ('perf_rpts', 'Performance Reports', 'personnel_crm.py'),
            ],
        }),
        ('disc_records', 'Disciplinary Records', {
            'title': 'Disciplinary Records',
            'items': [
                ('new_rec', 'New Record', 'personnel_crm.py'),
                ('view_recs', 'View Records', 'personnel_crm.py'),
                ('rec_hist', 'Record History', 'personnel_crm.py'),
                ('disc_rpts', 'Disciplinary Reports', 'personnel_crm.py'),
            ],
        }),
        ('training', 'Training & Development', {
            'title': 'Training & Development',
            'items': [
                ('train_cal', 'Training Calendar', 'personnel_crm.py'),
                ('train_recs', 'Training Records', 'personnel_crm.py'),
                ('course_mgmt', 'Course Management', 'personnel_crm.py'),
                ('cert_track', 'Certification Tracking', 'personnel_crm.py'),
            ],
        }),
        ('onboarding', 'Onboarding', {
            'title': 'Onboarding',
            'items': [
                ('hire_chk', 'New Hire Checklist', 'personnel_crm.py'),
                ('onb_stat', 'Onboarding Status', 'personnel_crm.py'),
                ('doc_coll', 'Document Collection', 'personnel_crm.py'),
                ('onb_rpts', 'Onboarding Reports', 'personnel_crm.py'),
            ],
        }),
    ],
}

_CS_MENU = {
    'title': 'Customer Service Menu',
    'items': [
        ('cs_calls', 'Customer Service Calls', 'cs_calls.py'),
        ('cust_entry', 'Customer Entry Screen', 'customer_entry.py'),
        ('open_tickets', 'Open Tickets', {
            'title': 'Open Tickets',
            'items': [
                ('all_tickets', 'View All Tickets', 'cs_calls.py'),
                ('my_tickets', 'My Tickets', 'cs_calls.py'),
                ('hi_pri', 'High Priority', 'cs_calls.py'),
                ('tick_search', 'Ticket Search', 'cs_calls.py'),
            ],
        }),
        ('cust_accounts', 'Customer Accounts', {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list', 'Account List', 'customers.py'),
                ('new_acct', 'New Account', 'customers.py'),
                ('acct_det', 'Account Details', 'customers.py'),
                ('acct_hist', 'Account History', 'customers.py'),
            ],
        }),
        ('returns', 'Returns & Refunds', {
            'title': 'Returns & Refunds',
            'items': [
                ('new_return', 'New Return', 'cs_calls.py'),
                ('pend_ret', 'Pending Returns', 'cs_calls.py'),
                ('refund_proc', 'Refund Processing', 'cs_calls.py'),
                ('ret_rpts', 'Returns Reports', 'cs_calls.py'),
            ],
        }),
        ('knowledge_base', 'Knowledge Base', {
            'title': 'Knowledge Base',
            'items': [
                ('browse', 'Browse Articles', 'cs_calls.py'),
                ('create_art', 'Create Article', 'cs_calls.py'),
                ('art_mgmt', 'Article Management', 'cs_calls.py'),
                ('kb_search', 'Search Knowledge Base', 'cs_calls.py'),
            ],
        }),
        ('svc_reports', 'Service Reports', {
            'title': 'Service Reports',
            'items': [
                ('daily_rpt', 'Daily Report', 'cs_calls.py'),
                ('week_sum', 'Weekly Summary', 'cs_calls.py'),
                ('res_rpts', 'Resolution Reports', 'cs_calls.py'),
                ('csat_rpts', 'Customer Satisfaction', 'cs_calls.py'),
            ],
        }),
        ('surveys', 'Surveys & Feedback', {
            'title': 'Surveys & Feedback',
            'items': [
                ('act_surv', 'Active Surveys', 'cs_calls.py'),
                ('new_surv', 'Create Survey', 'cs_calls.py'),
                ('surv_res', 'Survey Results', 'cs_calls.py'),
                ('feed_rpts', 'Feedback Reports', 'cs_calls.py'),
            ],
        }),
    ],
}

_IT_TECH = {
    'title': 'IT Technician',
    'items': [
        ('it_calls', 'IT Support Calls', 'it_calls.py'),
        ('it_tasks', 'IT Tasks', 'IT_Tasks.py'),
        ('help_desk', 'Help Desk Tickets', {
            'title': 'Help Desk Tickets',
            'items': [
                ('new_ticket', 'New Ticket', 'IT_Tasks.py'),
                ('open_tick', 'Open Tickets', 'IT_Tasks.py'),
                ('my_tickets', 'My Assigned Tickets', 'IT_Tasks.py'),
                ('tick_hist', 'Ticket History', 'IT_Tasks.py'),
            ],
        }),
        ('asset_mgmt', 'Asset Management', {
            'title': 'Asset Management',
            'items': [
                ('asset_inv', 'Asset Inventory', 'IT_Tasks.py'),
                ('new_asset', 'New Asset', 'IT_Tasks.py'),
                ('asset_hist', 'Asset History', 'IT_Tasks.py'),
                ('disposition', 'Disposition', 'IT_Tasks.py'),
            ],
        }),
        ('net_status', 'Network Status', {
            'title': 'Network Status',
            'items': [
                ('net_dash', 'Network Dashboard', 'IT_Tasks.py'),
                ('bw_monitor', 'Bandwidth Monitor', 'IT_Tasks.py'),
                ('net_map', 'Network Map', 'IT_Tasks.py'),
                ('inc_log', 'Incident Log', 'IT_Tasks.py'),
            ],
        }),
        ('sw_install', 'Software Installations', {
            'title': 'Software Installations',
            'items': [
                ('pend_inst', 'Pending Installs', 'IT_Tasks.py'),
                ('sw_inv', 'Software Inventory', 'IT_Tasks.py'),
                ('lic_mgmt', 'License Management', 'IT_Tasks.py'),
                ('inst_hist', 'Installation History', 'IT_Tasks.py'),
            ],
        }),
        ('hw_repairs', 'Hardware Repairs', {
            'title': 'Hardware Repairs',
            'items': [
                ('new_repair', 'New Repair Request', 'IT_Tasks.py'),
                ('inprog', 'In Progress', 'IT_Tasks.py'),
                ('comp_rep', 'Completed Repairs', 'IT_Tasks.py'),
                ('rep_hist', 'Repair History', 'IT_Tasks.py'),
            ],
        }),
        ('user_accts', 'User Account Management', {
            'title': 'User Account Management',
            'items': [
                ('create_acct', 'Create Account', 'IT_Tasks.py'),
                ('reset_pw', 'Reset Password', 'IT_Tasks.py'),
                ('acct_stat', 'Account Status', 'IT_Tasks.py'),
                ('acct_audit', 'Account Audit', 'IT_Tasks.py'),
            ],
        }),
    ],
}

_PURCH_MENU = {
    'title': 'Purchasing Menu',
    'items': [
        ('prod_entry', 'Product Entry', 'product_entry_screen.py'),
        ('sup_entry', 'Supplier Entry', 'Supplier_entry.py'),
        ('purch_orders', 'Purchase Orders', {
            'title': 'Purchase Orders',
            'items': [
                ('new_po', 'New PO', 'purchase_orders.py'),
                ('open_pos', 'Open POs', 'purchase_orders.py'),
                ('po_status', 'PO Status', 'purchase_orders.py'),
                ('po_hist', 'PO History', 'purchase_orders.py'),
            ],
        }),
        ('vendor_mgmt', 'Vendor Management', {
            'title': 'Vendor Management',
            'items': [
                ('vend_list', 'Vendor List', 'suppliers.py'),
                ('new_vend', 'New Vendor', 'suppliers.py'),
                ('vend_perf', 'Vendor Performance', 'suppliers.py'),
                ('vend_cont', 'Vendor Contracts', 'suppliers.py'),
            ],
        }),
        ('purch_reports', 'Purchase Reports', {
            'title': 'Purchase Reports',
            'items': [
                ('spend_sum', 'Spending Summary', 'Purchasing_menu.py'),
                ('po_rpts', 'PO Reports', 'Purchasing_menu.py'),
                ('budg_act', 'Budget vs. Actual', 'Purchasing_menu.py'),
                ('cat_rpts', 'Category Reports', 'Purchasing_menu.py'),
            ],
        }),
        ('receiving', 'Receiving', {
            'title': 'Receiving',
            'items': [
                ('pend_recv', 'Pending Receipts', 'receiving_dept.py'),
                ('recv_items', 'Receive Items', 'receiving_dept.py'),
                ('disc_rpts', 'Discrepancy Reports', 'receiving_dept.py'),
                ('recv_hist', 'Receiving History', 'receiving_dept.py'),
            ],
        }),
        ('contracts', 'Contract Management', {
            'title': 'Contract Management',
            'items': [
                ('act_cont', 'Active Contracts', 'Purchasing_menu.py'),
                ('new_cont', 'New Contract', 'Purchasing_menu.py'),
                ('cont_renew', 'Contract Renewals', 'Purchasing_menu.py'),
                ('cont_arch', 'Contract Archive', 'Purchasing_menu.py'),
            ],
        }),
        ('requisitions', 'Requisitions', {
            'title': 'Requisitions',
            'items': [
                ('new_req', 'New Requisition', 'purchase_requisitions.py'),
                ('pend_appr', 'Pending Approval', 'Purchasing_Mgr_menu.py'),
                ('appr_reqs', 'Approved Requisitions',
                 'purchase_requisitions.py'),
                ('req_hist', 'Requisition History',
                 'purchase_requisitions.py'),
            ],
        }),
    ],
}

MENU_TREE = {
    'accounting': {
        'title': 'Accounting Main Menu',
        'items': [
            ('acct_pay', 'Accounts Payable', 'Accounts_payable.py'),
            ('acct_mgr', 'Accounting Manager', {
                'title': 'Accounting Manager',
                'items': [
                    ('ap', 'Accounts Payable', 'Accounts_payable.py'),
                    ('rcv', 'Accounts Receivable', 'Accounts_receivable.py'),
                    ('credit', 'Credit Department', 'Credit_dept.py'),
                    ('pay', 'Payroll Department', 'Payroll_dept.py'),
                    ('fin_reports', 'Financial Reports', {
                        'title': 'Financial Reports',
                        'items': [
                            ('inc_stmt', 'Income Statement',
                             'General_ledger.py'),
                            ('bal_sheet', 'Balance Sheet',
                             'General_ledger.py'),
                            ('cash_flow', 'Cash Flow', 'General_ledger.py'),
                            ('cust_rpts', 'Custom Reports',
                             'General_ledger.py'),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('budg_plan', 'Budget Planning', 'Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'Budget_mgmt.py'),
                            ('budg_amend', 'Budget Amendments',
                             'Budget_mgmt.py'),
                            ('budg_rpts', 'Budget Reports', 'Budget_mgmt.py'),
                        ],
                    }),
                    ('audit_mgmt', 'Audit Management', {
                        'title': 'Audit Management',
                        'items': [
                            ('audit_sched', 'Audit Schedule', 'Audit_mgmt.py'),
                            ('findings', 'Audit Findings', 'Audit_mgmt.py'),
                            ('corr_act', 'Corrective Actions',
                             'Audit_mgmt.py'),
                            ('audit_rpts', 'Audit Reports', 'Audit_mgmt.py'),
                        ],
                    }),
                ],
            }),
            ('acct_rcv', 'Accounts Receivable', 'Accounts_receivable.py'),
            ('credit', 'Credit Department', 'Credit_dept.py'),
            ('payroll', 'Payroll Department', 'Payroll_dept.py'),
            ('gen_ledger', 'General Ledger', 'General_ledger.py'),
            ('budget_mgmt', 'Budget Management', {
                'title': 'Budget Management',
                'items': [
                    ('budg_plan', 'Budget Planning', 'Budget_mgmt.py'),
                    ('budg_act', 'Budget vs. Actual', 'Budget_mgmt.py'),
                    ('budg_amend', 'Budget Amendments', 'Budget_mgmt.py'),
                    ('budg_rpts', 'Budget Reports', 'Budget_mgmt.py'),
                ],
            }),
            ('fin_reports', 'Financial Reports', {
                'title': 'Financial Reports',
                'items': [
                    ('inc_stmt', 'Income Statement', 'General_ledger.py'),
                    ('bal_sheet', 'Balance Sheet', 'General_ledger.py'),
                    ('cash_flow', 'Cash Flow', 'General_ledger.py'),
                    ('cust_rpts', 'Custom Reports', 'General_ledger.py'),
                ],
            }),
            ('tax_mgmt', 'Tax Management', {
                'title': 'Tax Management',
                'items': [
                    ('tax_cal', 'Tax Calendar', 'Tax_mgmt.py'),
                    ('tax_filing', 'Tax Filing', 'Tax_mgmt.py'),
                    ('tax_pay', 'Tax Payments', 'Tax_mgmt.py'),
                    ('tax_rpts', 'Tax Reports', 'Tax_mgmt.py'),
                ],
            }),
            ('exp_reports', 'Expense Reports', {
                'title': 'Expense Reports',
                'items': [
                    ('sub_exp', 'Submit Expense', 'Accounts_payable.py'),
                    ('pend_appr', 'Pending Approval', 'Accounts_payable.py'),
                    ('appr_exp', 'Approved Expenses', 'Accounts_payable.py'),
                    ('exp_sum', 'Expense Summary', 'Accounts_payable.py'),
                ],
            }),
            ('bank_recon', 'Bank Reconciliation', {
                'title': 'Bank Reconciliation',
                'items': [
                    ('recon_acct', 'Reconcile Account', 'General_ledger.py'),
                    ('pend_items', 'Pending Items', 'General_ledger.py'),
                    ('recon_hist', 'Reconciliation History',
                     'General_ledger.py'),
                    ('bank_rpts', 'Bank Reports', 'General_ledger.py'),
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
                             'cs_reports.py'),
                            ('week_sum', 'Weekly Summary', 'cs_reports.py'),
                            ('res_analy', 'Resolution Analysis',
                             'cs_reports.py'),
                            ('sla_rpts', 'SLA Reports', 'cs_reports.py'),
                        ],
                    }),
                    ('staff_mgmt', 'Staff Management', {
                        'title': 'Staff Management',
                        'items': [
                            ('staff_sched', 'Staff Schedule',
                             'cs_staff_mgmt.py'),
                            ('perf_met', 'Performance Metrics',
                             'cs_staff_mgmt.py'),
                            ('staff_train', 'Staff Training',
                             'cs_staff_mgmt.py'),
                            ('staff_rpts', 'Staff Reports',
                             'cs_staff_mgmt.py'),
                        ],
                    }),
                    ('cust_sat', 'Customer Satisfaction', {
                        'title': 'Customer Satisfaction',
                        'items': [
                            ('csat_res', 'CSAT Survey Results',
                             'cs_satisfaction.py'),
                            ('nps_rpts', 'NPS Reports', 'cs_satisfaction.py'),
                            ('sat_trends', 'Satisfaction Trends',
                             'cs_satisfaction.py'),
                            ('impr_plans', 'Improvement Plans',
                             'cs_satisfaction.py'),
                        ],
                    }),
                    ('escalations', 'Escalations', {
                        'title': 'Escalations',
                        'items': [
                            ('act_esc', 'Active Escalations',
                             'cs_escalations.py'),
                            ('esc_hist', 'Escalation History',
                             'cs_escalations.py'),
                            ('esc_rpts', 'Escalation Reports',
                             'cs_escalations.py'),
                            ('res_track', 'Resolution Tracking',
                             'cs_escalations.py'),
                        ],
                    }),
                ],
            }),
            ('cs_menu', 'Customer Service Menu', _CS_MENU),
            ('cs_calls', 'Customer Service Calls', 'cs_calls.py'),
        ],
    },
    'engineering': {
        'title': 'Engineering Main Menu',
        'items': [
            ('eng_mgr', 'Engineering Manager', {
                'title': 'Engineering Manager',
                'items': [
                    ('engineers', 'Engineers', 'engineer.py'),
                    ('proj_appr', 'Project Approvals', {
                        'title': 'Project Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals', 'eng_mgr.py'),
                            ('appr_proj', 'Approved Projects', 'eng_mgr.py'),
                            ('rej_proj', 'Rejected Projects', 'eng_mgr.py'),
                            ('appr_hist', 'Approval History', 'eng_mgr.py'),
                        ],
                    }),
                    ('resource', 'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc', 'Resource Allocation', 'eng_mgr.py'),
                            ('cap_plan', 'Capacity Planning', 'eng_mgr.py'),
                            ('res_rpts', 'Resource Reports', 'eng_mgr.py'),
                            ('avail_cal', 'Availability Calendar',
                             'eng_mgr.py'),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('eng_budg', 'Engineering Budget',
                             'Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'Budget_mgmt.py'),
                            ('cost_rpts', 'Cost Reports', 'Budget_mgmt.py'),
                            ('budg_req', 'Budget Requests', 'Budget_mgmt.py'),
                        ],
                    }),
                    ('eng_reports', 'Engineering Reports', {
                        'title': 'Engineering Reports',
                        'items': [
                            ('proj_stat', 'Project Status', 'eng_mgr.py'),
                            ('res_util', 'Resource Utilization', 'eng_mgr.py'),
                            ('kpi_dash', 'KPI Dashboard', 'eng_mgr.py'),
                            ('month_rpts', 'Monthly Reports', 'eng_mgr.py'),
                        ],
                    }),
                ],
            }),
            ('engineers', 'Engineers', 'engineer.py'),
            ('proj_mgmt', 'Project Management', {
                'title': 'Project Management',
                'items': [
                    ('act_proj', 'Active Projects', 'engineer.py'),
                    ('new_proj', 'New Project', 'engineer.py'),
                    ('proj_time', 'Project Timeline', 'engineer.py'),
                    ('proj_rpts', 'Project Reports', 'engineer.py'),
                ],
            }),
            ('design_docs', 'Design Documents', {
                'title': 'Design Documents',
                'items': [
                    ('doc_lib', 'Document Library', 'engineer.py'),
                    ('new_doc', 'New Document', 'engineer.py'),
                    ('doc_review', 'Document Review', 'engineer.py'),
                    ('archive', 'Archive', 'engineer.py'),
                ],
            }),
            ('bom', 'Bill of Materials', {
                'title': 'Bill of Materials',
                'items': [
                    ('bom_list', 'BOM List', 'engineer.py'),
                    ('new_bom', 'Create BOM', 'engineer.py'),
                    ('bom_rev', 'BOM Revision', 'engineer.py'),
                    ('bom_rpts', 'BOM Reports', 'engineer.py'),
                ],
            }),
            ('chg_orders', 'Change Orders', {
                'title': 'Change Orders',
                'items': [
                    ('new_co', 'New Change Order', 'engineer.py'),
                    ('pend_appr', 'Pending Approval', 'engineer.py'),
                    ('appr_chg', 'Approved Changes', 'engineer.py'),
                    ('chg_hist', 'Change History', 'engineer.py'),
                ],
            }),
            ('test_val', 'Test & Validation', {
                'title': 'Test & Validation',
                'items': [
                    ('test_plans', 'Test Plans', 'engineer.py'),
                    ('test_res', 'Test Results', 'engineer.py'),
                    ('val_rpts', 'Validation Reports', 'engineer.py'),
                    ('issue_track', 'Issue Tracking', 'engineer.py'),
                ],
            }),
            ('eng_reports', 'Engineering Reports', {
                'title': 'Engineering Reports',
                'items': [
                    ('proj_stat', 'Project Status', 'engineer.py'),
                    ('design_rev', 'Design Review', 'engineer.py'),
                    ('res_rpt', 'Resource Report', 'engineer.py'),
                    ('cust_rpts', 'Custom Reports', 'engineer.py'),
                ],
            }),
            ('standards', 'Standards & Compliance', {
                'title': 'Standards & Compliance',
                'items': [
                    ('std_lib', 'Standards Library', 'engineer.py'),
                    ('comp_chk', 'Compliance Checklist', 'engineer.py'),
                    ('audit_res', 'Audit Results', 'engineer.py'),
                    ('reg_upd', 'Regulatory Updates', 'engineer.py'),
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
                            ('it_budg', 'IT Budget', 'Budget_mgmt.py'),
                            ('hw_proc', 'Hardware Procurement',
                             'Budget_mgmt.py'),
                            ('sw_lic', 'Software Licensing', 'Budget_mgmt.py'),
                            ('proc_rpts', 'Procurement Reports',
                             'Budget_mgmt.py'),
                        ],
                    }),
                    ('vendor_con', 'Vendor Contracts', {
                        'title': 'Vendor Contracts',
                        'items': [
                            ('act_cont', 'Active Contracts', 'IT_mgr.py'),
                            ('cont_renew', 'Contract Renewals', 'IT_mgr.py'),
                            ('vend_perf', 'Vendor Performance', 'IT_mgr.py'),
                            ('cont_arch', 'Contract Archive', 'IT_mgr.py'),
                        ],
                    }),
                    ('it_projects', 'IT Projects', {
                        'title': 'IT Projects',
                        'items': [
                            ('act_proj', 'Active Projects', 'IT_mgr.py'),
                            ('proj_pipe', 'Project Pipeline', 'IT_mgr.py'),
                            ('proj_rpts', 'Project Reports', 'IT_mgr.py'),
                            ('res_alloc', 'Resource Allocation', 'IT_mgr.py'),
                        ],
                    }),
                    ('security', 'Security Management', {
                        'title': 'Security Management',
                        'items': [
                            ('sec_dash', 'Security Dashboard', 'IT_mgr.py'),
                            ('inc_rpts', 'Incident Reports', 'IT_mgr.py'),
                            ('vuln_mgmt', 'Vulnerability Management',
                             'IT_mgr.py'),
                            ('comp_rpts', 'Compliance Reports', 'IT_mgr.py'),
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
                             'Maint_mgr_menu.py'),
                            ('appr_wo', 'Approved Work Orders',
                             'Maint_mgr_menu.py'),
                            ('rej_wo', 'Rejected', 'Maint_mgr_menu.py'),
                            ('appr_hist', 'Approval History',
                             'Maint_mgr_menu.py'),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('maint_budg', 'Maintenance Budget',
                             'Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'Budget_mgmt.py'),
                            ('cost_analy', 'Cost Analysis', 'Budget_mgmt.py'),
                            ('budg_req', 'Budget Requests', 'Budget_mgmt.py'),
                        ],
                    }),
                    ('maint_rpts', 'Maintenance Reports', {
                        'title': 'Maintenance Reports',
                        'items': [
                            ('daily_rpt', 'Daily Report', 'Maint_mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'Maint_mgr_menu.py'),
                            ('equip_rpts', 'Equipment Reports',
                             'Maint_mgr_menu.py'),
                            ('cost_rpts', 'Cost Reports', 'Maint_mgr_menu.py'),
                        ],
                    }),
                ],
            }),
            ('maint', 'Maintenance', _MAINT_MENU),
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
                            ('budg_over', 'Budget Overview', 'Budget_mgmt.py'),
                            ('budg_camp', 'Budget by Campaign',
                             'Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'Budget_mgmt.py'),
                            ('budg_req', 'Budget Requests', 'Budget_mgmt.py'),
                        ],
                    }),
                    ('camp_appr', 'Campaign Approvals', {
                        'title': 'Campaign Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals',
                             'marketing_mgr_menu.py'),
                            ('appr_camp', 'Approved Campaigns',
                             'marketing_mgr_menu.py'),
                            ('camp_arch', 'Campaign Archive',
                             'marketing_mgr_menu.py'),
                            ('appr_hist', 'Approval History',
                             'marketing_mgr_menu.py'),
                        ],
                    }),
                    ('mkt_reports', 'Marketing Reports', {
                        'title': 'Marketing Reports',
                        'items': [
                            ('camp_perf', 'Campaign Performance',
                             'marketing_mgr_menu.py'),
                            ('roi_rpts', 'ROI Reports',
                             'marketing_mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'marketing_mgr_menu.py'),
                            ('kpi_dash', 'KPI Dashboard',
                             'marketing_mgr_menu.py'),
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
                             'personnel_mgr_menu.py'),
                            ('appl_track', 'Applicant Tracking',
                             'personnel_mgr_menu.py'),
                            ('int_sched', 'Interview Schedule',
                             'personnel_mgr_menu.py'),
                            ('offer_mgmt', 'Offer Management',
                             'personnel_mgr_menu.py'),
                        ],
                    }),
                    ('term', 'Terminations', {
                        'title': 'Terminations',
                        'items': [
                            ('term_proc', 'Termination Process',
                             'personnel_mgr_menu.py'),
                            ('exit_int', 'Exit Interviews',
                             'personnel_mgr_menu.py'),
                            ('final_pay', 'Final Pay Processing',
                             'personnel_mgr_menu.py'),
                            ('offboard', 'Offboarding Checklist',
                             'personnel_mgr_menu.py'),
                        ],
                    }),
                    ('salary', 'Salary Management', {
                        'title': 'Salary Management',
                        'items': [
                            ('sal_review', 'Salary Review',
                             'personnel_mgr_menu.py'),
                            ('sal_adj', 'Salary Adjustments',
                             'personnel_mgr_menu.py'),
                            ('comp_rpts', 'Compensation Reports',
                             'personnel_mgr_menu.py'),
                            ('pay_grades', 'Pay Grades',
                             'personnel_mgr_menu.py'),
                        ],
                    }),
                    ('hr_reports', 'HR Reports', {
                        'title': 'HR Reports',
                        'items': [
                            ('hd_rpt', 'Headcount Report',
                             'personnel_mgr_menu.py'),
                            ('turn_rpt', 'Turnover Report',
                             'personnel_mgr_menu.py'),
                            ('comp_rpts', 'Compliance Reports',
                             'personnel_mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'personnel_mgr_menu.py'),
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
                             'prod_mgr_Menu.py'),
                            ('week_sum', 'Weekly Summary', 'prod_mgr_Menu.py'),
                            ('eff_rpts', 'Efficiency Reports',
                             'prod_mgr_Menu.py'),
                            ('kpi_dash', 'KPI Dashboard', 'prod_mgr_Menu.py'),
                        ],
                    }),
                    ('resource', 'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc', 'Resource Allocation',
                             'prod_mgr_Menu.py'),
                            ('cap_plan', 'Capacity Planning',
                             'prod_mgr_Menu.py'),
                            ('res_rpts', 'Resource Reports',
                             'prod_mgr_Menu.py'),
                            ('wf_plan', 'Workforce Planning',
                             'prod_mgr_Menu.py'),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('prod_budg', 'Production Budget',
                             'Budget_mgmt.py'),
                            ('cost_analy', 'Cost Analysis', 'Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'Budget_mgmt.py'),
                            ('budg_rpts', 'Budget Reports', 'Budget_mgmt.py'),
                        ],
                    }),
                ],
            }),
            ('prod', 'Production', _PROD_MENU),
            ('shipping', 'Shipping', _SHIP_MENU),
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
                             'Purchasing_Mgr_menu.py'),
                            ('appr_pos', 'Approved POs',
                             'Purchasing_Mgr_menu.py'),
                            ('rej_pos', 'Rejected POs',
                             'Purchasing_Mgr_menu.py'),
                            ('appr_hist', 'Approval History',
                             'Purchasing_Mgr_menu.py'),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('purch_budg', 'Purchasing Budget',
                             'Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'Budget_mgmt.py'),
                            ('spend_analy', 'Spending Analysis',
                             'Budget_mgmt.py'),
                            ('budg_rpts', 'Budget Reports', 'Budget_mgmt.py'),
                        ],
                    }),
                    ('vendor_mgmt', 'Vendor Management', {
                        'title': 'Vendor Management',
                        'items': [
                            ('vend_list', 'Vendor List',
                             'Purchasing_Mgr_menu.py'),
                            ('vend_eval', 'Vendor Evaluation',
                             'Purchasing_Mgr_menu.py'),
                            ('vend_perf', 'Vendor Performance',
                             'Purchasing_Mgr_menu.py'),
                            ('appr_vend', 'Approved Vendors',
                             'Purchasing_Mgr_menu.py'),
                        ],
                    }),
                    ('purch_rpts', 'Purchasing Reports', {
                        'title': 'Purchasing Reports',
                        'items': [
                            ('spend_rpt', 'Spending Report',
                             'Purchasing_Mgr_menu.py'),
                            ('vend_rpt', 'Vendor Report',
                             'Purchasing_Mgr_menu.py'),
                            ('cat_analy', 'Category Analysis',
                             'Purchasing_Mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'Purchasing_Mgr_menu.py'),
                        ],
                    }),
                    ('contracts', 'Contract Management', {
                        'title': 'Contract Management',
                        'items': [
                            ('act_cont', 'Active Contracts',
                             'Purchasing_Mgr_menu.py'),
                            ('pend_renew', 'Pending Renewals',
                             'Purchasing_Mgr_menu.py'),
                            ('cont_arch', 'Contract Archive',
                             'Purchasing_Mgr_menu.py'),
                            ('cont_rpts', 'Contract Reports',
                             'Purchasing_Mgr_menu.py'),
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
                             'QA_Mgr_menu.py'),
                            ('act_audits', 'Active Audits', 'QA_Mgr_menu.py'),
                            ('findings', 'Audit Findings', 'QA_Mgr_menu.py'),
                            ('corr_act', 'Corrective Actions',
                             'QA_Mgr_menu.py'),
                        ],
                    }),
                    ('compliance', 'Compliance', {
                        'title': 'Compliance',
                        'items': [
                            ('comp_dash', 'Compliance Dashboard',
                             'QA_Mgr_menu.py'),
                            ('reg_req', 'Regulatory Requirements',
                             'QA_Mgr_menu.py'),
                            ('comp_rpts', 'Compliance Reports',
                             'QA_Mgr_menu.py'),
                            ('non_comp', 'Non-Compliance Issues',
                             'QA_Mgr_menu.py'),
                        ],
                    }),
                    ('corr_action', 'Corrective Actions', {
                        'title': 'Corrective Actions',
                        'items': [
                            ('open_cars', 'Open CARs', 'QA_Mgr_menu.py'),
                            ('inprog_cars', 'In Progress', 'QA_Mgr_menu.py'),
                            ('closed_cars', 'Closed CARs', 'QA_Mgr_menu.py'),
                            ('car_rpts', 'CAR Reports', 'QA_Mgr_menu.py'),
                        ],
                    }),
                    ('qa_reports', 'QA Reports', {
                        'title': 'QA Reports',
                        'items': [
                            ('daily_qa', 'Daily QA Report', 'QA_Mgr_menu.py'),
                            ('week_sum', 'Weekly Summary', 'QA_Mgr_menu.py'),
                            ('month_rpt', 'Monthly Report', 'QA_Mgr_menu.py'),
                            ('kpi_dash', 'KPI Dashboard', 'QA_Mgr_menu.py'),
                        ],
                    }),
                    ('supp_qual', 'Supplier Quality', {
                        'title': 'Supplier Quality',
                        'items': [
                            ('supp_score', 'Supplier Scorecards',
                             'QA_Mgr_menu.py'),
                            ('inc_insp', 'Incoming Inspection',
                             'QA_Mgr_menu.py'),
                            ('supp_audit', 'Supplier Audits',
                             'QA_Mgr_menu.py'),
                            ('supp_rpts', 'Supplier Reports',
                             'QA_Mgr_menu.py'),
                        ],
                    }),
                    ('cust_comp', 'Customer Complaints', {
                        'title': 'Customer Complaints',
                        'items': [
                            ('new_comp', 'New Complaint', 'QA_Mgr_menu.py'),
                            ('open_comp', 'Open Complaints', 'QA_Mgr_menu.py'),
                            ('res_track', 'Resolution Tracking',
                             'QA_Mgr_menu.py'),
                            ('comp_rpts', 'Complaint Reports',
                             'QA_Mgr_menu.py'),
                        ],
                    }),
                    ('doc_control', 'Document Control', {
                        'title': 'Document Control',
                        'items': [
                            ('doc_lib', 'Document Library', 'QA_Mgr_menu.py'),
                            ('new_doc', 'New Document', 'QA_Mgr_menu.py'),
                            ('doc_review', 'Document Review',
                             'QA_Mgr_menu.py'),
                            ('rev_hist', 'Revision History', 'QA_Mgr_menu.py'),
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
                            ('set_tgt', 'Set Targets', 'Sales_mgr_menu.py'),
                            ('tgt_act', 'Target vs. Actual',
                             'Sales_mgr_menu.py'),
                            ('tgt_rep', 'Target by Rep', 'Sales_mgr_menu.py'),
                            ('tgt_rpts', 'Target Reports',
                             'Sales_mgr_menu.py'),
                        ],
                    }),
                    ('territory', 'Territory Management', {
                        'title': 'Territory Management',
                        'items': [
                            ('terr_map', 'Territory Map', 'Sales_mgr_menu.py'),
                            ('terr_assign', 'Territory Assignments',
                             'Sales_mgr_menu.py'),
                            ('terr_perf', 'Territory Performance',
                             'Sales_mgr_menu.py'),
                            ('terr_rpts', 'Territory Reports',
                             'Sales_mgr_menu.py'),
                        ],
                    }),
                    ('commission', 'Commission Tracking', {
                        'title': 'Commission Tracking',
                        'items': [
                            ('comm_calc', 'Commission Calculator',
                             'Sales_mgr_menu.py'),
                            ('comm_rpts', 'Commission Reports',
                             'Sales_mgr_menu.py'),
                            ('pay_hist', 'Payment History',
                             'Sales_mgr_menu.py'),
                            ('comm_plans', 'Commission Plans',
                             'Sales_mgr_menu.py'),
                        ],
                    }),
                    ('staff_perf', 'Staff Performance', {
                        'title': 'Staff Performance',
                        'items': [
                            ('perf_dash', 'Performance Dashboard',
                             'Sales_mgr_menu.py'),
                            ('rep_rank', 'Rep Rankings', 'Sales_mgr_menu.py'),
                            ('perf_revs', 'Performance Reviews',
                             'Sales_mgr_menu.py'),
                            ('coaching', 'Coaching Notes',
                             'Sales_mgr_menu.py'),
                        ],
                    }),
                ],
            }),
            ('sales', 'Sales Menu', _SALES_MENU),
        ],
    },
    'budget_management': {
        'title': 'Budget Management',
        'items': [
            ('budget_mgr', 'Budget Manager', {
                'title': 'Budget Manager',
                'items': [
                    ('bud_overview', 'Budgets', 'Budget_mgr_menu.py'),
                    ('bud_detail_mgr', 'Budget Detail', 'Budget_mgr_menu.py'),
                    ('bva_mgr', 'Budget vs. Actual', 'Budget_mgr_menu.py'),
                    ('variance_mgr', 'Variance Report', 'Budget_mgr_menu.py'),
                    ('dept_summary', 'Department Summaries',
                     'Budget_mgr_menu.py'),
                    ('approval_wf', 'Approval Workflow', 'Budget_mgr_menu.py'),
                ],
            }),
            ('budgets', 'Budgets', 'Budget_mgmt.py'),
            ('bud_detail', 'Budget Detail', 'Budget_mgmt.py'),
            ('bva', 'Budget vs. Actual', 'Budget_mgmt.py'),
            ('variance', 'Variance Report', 'Budget_mgmt.py'),
        ],
    },
    'finance': {
        'title': 'Finance Main Menu',
        'items': [
            ('fin_mgr', 'Finance Manager', {
                'title': 'Finance Manager',
                'items': [
                    ('fin_plan', 'Financial Planning', 'Finance_mgr_menu.py'),
                    ('fin_forecast', 'Budget & Forecasting',
                     'Finance_mgr_menu.py'),
                    ('treasury_mgmt', 'Treasury Management',
                     'Finance_mgr_menu.py'),
                    ('invest_mgmt', 'Investment Management',
                     'Finance_mgr_menu.py'),
                    ('fin_rpts_mgr', 'Financial Reports',
                     'Finance_mgr_menu.py'),
                ],
            }),
            ('fin_analysis', 'Financial Analysis', 'Finance_Main_menu.py'),
            ('fin_reporting', 'Financial Reporting', 'Finance_Main_menu.py'),
            ('treasury_ops', 'Treasury Operations', 'Finance_Main_menu.py'),
            ('capital_mgmt', 'Capital Management', 'Finance_Main_menu.py'),
            ('tax_planning', 'Tax Planning', 'Finance_Main_menu.py'),
        ],
    },
    'legal': {
        'title': 'Legal Main Menu',
        'items': [
            ('legal_mgr', 'Legal Manager', {
                'title': 'Legal Manager',
                'items': [
                    ('contracts_mgmt', 'Contract Management',
                     'Legal_mgr_menu.py'),
                    ('litigation_mgmt', 'Litigation Management',
                     'Legal_mgr_menu.py'),
                    ('compliance_mgmt', 'Compliance Management',
                     'Legal_mgr_menu.py'),
                    ('corp_gov', 'Corporate Governance', 'Legal_mgr_menu.py'),
                ],
            }),
            ('contracts', 'Contracts', 'Legal_Main_menu.py'),
            ('compliance', 'Compliance', 'Legal_Main_menu.py'),
            ('litigation', 'Litigation', 'Legal_Main_menu.py'),
            ('ip_mgmt', 'Intellectual Property', 'Legal_Main_menu.py'),
            ('emp_law', 'Employment Law', 'Legal_Main_menu.py'),
        ],
    },
    'risk_management': {
        'title': 'Risk Management Main Menu',
        'items': [
            ('risk_mgr', 'Risk Manager', {
                'title': 'Risk Manager',
                'items': [
                    ('risk_register_mgr', 'Risk Register', 'Risk_mgr_menu.py'),
                    ('kri', 'Key Risk Indicators', 'Risk_mgr_menu.py'),
                    ('biz_continuity', 'Business Continuity',
                     'Risk_mgr_menu.py'),
                    ('audit_compliance', 'Audit & Compliance',
                     'Risk_mgr_menu.py'),
                ],
            }),
            ('risk_assess', 'Risk Assessment', 'Risk_mgmt_Main_menu.py'),
            ('risk_register', 'Risk Register', 'Risk_mgmt_Main_menu.py'),
            ('insurance', 'Insurance Management', 'Risk_mgmt_Main_menu.py'),
            ('biz_cont', 'Business Continuity', 'Risk_mgmt_Main_menu.py'),
            ('comp_audit', 'Compliance & Audit', 'Risk_mgmt_Main_menu.py'),
        ],
    },
    'reports': {
        'title': 'Reports',
        'items': [
            ('rpt_dashboard', 'Dashboard', 'Reports_Main_menu.py'),
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
    ('purchasing', 'Purchasing'),
    ('quality_assurance', 'Quality Assurance'),
    ('sales', 'Sales'),
    ('budget_management', 'Budget Management'),
    ('finance', 'Finance'),
    ('legal', 'Legal'),
    ('risk_management', 'Risk Management'),
    ('reports', 'Reports'),
]

# Department main-menu scripts, keyed by dept_key. Used to scope a non-admin
# user to their own department after login (see login_app.SessionWindow). The
# company dashboard keeps its own parallel ordered list of the same scripts in
# Company_main_menu.DEPARTMENTS — keep the two in sync when adding a dept.
DEPT_MAIN_MENU = {
    'accounting':        'Accounting_Main_menu.py',
    'customer_service':  'cs_main_menu.py',
    'engineering':       'engineering_Main_menu.py',
    'finance':           'Finance_Main_menu.py',
    'information_tech':  'IT_Main_Menu.py',
    'legal':             'Legal_Main_menu.py',
    'maintenance':       'Maint_Main_menu.py',
    'marketing':         'Marketing_Main_menu.py',
    'personnel':         'Personnel_Main_menu.py',
    'production':        'Production_Main_menu.py',
    'purchasing':        'Purchasing_Main_menu.py',
    'quality_assurance': 'QA_Main_menu.py',
    'risk_management':   'Risk_mgmt_Main_menu.py',
    'sales':             'Sales_Main_menu.py',
    'warehouse':         'Warehouse_Main_menu.py',
    'budget_management': 'Budget_mgmt.py',
    'reports':           'Reports_Main_menu.py',
}


def main_menu_script_for_dept(dept_name):
    """Return the department main-menu script for a DB ``dept_name``, or None.

    Maps the department name to its menu key (:data:`DEPT_MENU_KEY`) and then
    to the main-menu script (:data:`DEPT_MAIN_MENU`). Returns ``None`` when
    the department is unknown or has no dedicated menu (e.g. ``Company`` or
    ``Labs``), so callers can fall back to the full company menu.
    """
    key = DEPT_MENU_KEY.get(dept_name or '')
    if key is None:
        return None
    return DEPT_MAIN_MENU.get(key)


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
