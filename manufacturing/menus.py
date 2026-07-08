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
                ('punch_in', 'Record Clock In', 'time_clock/time_clock_menu.py'),
                ('punch_out', 'Record Clock Out', 'time_clock/time_clock_menu.py'),
                ('cur_status', 'Current Status', 'time_clock/time_clock_menu.py'),
            ],
        }),
        ('view_hours', 'View Hours', {
            'title': 'View Hours',
            'items': [
                ('today_hrs', "Today's Hours", 'time_clock/time_clock_menu.py'),
                ('week_hrs', 'Weekly Hours', 'time_clock/time_clock_menu.py'),
                ('month_hrs', 'Monthly Hours', 'time_clock/time_clock_menu.py'),
                ('period_hrs', 'Pay Period Hours', 'time_clock/time_clock_menu.py'),
            ],
        }),
        ('time_off', 'Time Off Requests', {
            'title': 'Time Off Requests',
            'items': [
                ('submit_req', 'Submit Request', 'time_clock/time_clock_menu.py'),
                ('pend_req', 'Pending Requests', 'time_clock/time_clock_menu.py'),
                ('appr_req', 'Approved Requests', 'time_clock/time_clock_menu.py'),
                ('req_hist', 'Request History', 'time_clock/time_clock_menu.py'),
            ],
        }),
        ('schedules', 'Schedules', {
            'title': 'Schedules',
            'items': [
                ('my_sched', 'My Schedule', 'time_clock/time_clock_menu.py'),
                ('upcoming', 'Upcoming Shifts', 'time_clock/time_clock_menu.py'),
                ('sched_cal', 'Schedule Calendar', 'time_clock/time_clock_menu.py'),
                ('swap_req', 'Swap Requests', 'time_clock/time_clock_menu.py'),
            ],
        }),
        ('ot_reports', 'Overtime Reports', {
            'title': 'Overtime Reports',
            'items': [
                ('cur_ot', 'Current Period OT', 'time_clock/time_clock_menu.py'),
                ('hist_ot', 'Historical OT', 'time_clock/time_clock_menu.py'),
                ('ot_by_emp', 'OT by Employee', 'time_clock/time_clock_menu.py'),
                ('ot_appr', 'OT Approval', 'time_clock/time_clock_menu.py'),
            ],
        }),
        ('attend_reports', 'Attendance Reports', {
            'title': 'Attendance Reports',
            'items': [
                ('daily_att', 'Daily Attendance', 'time_clock/time_clock_menu.py'),
                ('month_sum', 'Monthly Summary', 'time_clock/time_clock_menu.py'),
                ('tard_rpt', 'Tardiness Report', 'time_clock/time_clock_menu.py'),
                ('abs_rpt', 'Absence Report', 'time_clock/time_clock_menu.py'),
            ],
        }),
        ('shift_mgmt', 'Shift Management', {
            'title': 'Shift Management',
            'items': [
                ('view_shfts', 'View Shifts', 'time_clock/time_clock_menu.py'),
                ('assign_emp', 'Assign Employees', 'time_clock/time_clock_menu.py'),
                ('shft_tmpl', 'Shift Templates', 'time_clock/time_clock_menu.py'),
                ('swap_mgmt', 'Swap Management', 'time_clock/time_clock_menu.py'),
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
                ('create_wo', 'Create Work Order', 'production/work_orders.py'),
                ('open_wo', 'Open Work Orders', 'production/work_orders.py'),
                ('inprog_wo', 'In Progress', 'production/work_orders.py'),
                ('comp_wo', 'Completed', 'production/work_orders.py'),
            ],
        }),
        ('maint_schedule', 'Maintenance Schedule', {
            'title': 'Maintenance Schedule',
            'items': [
                ('daily_sched', 'Daily Schedule', 'maintenance/Maint_Maint_menu.py'),
                ('week_sched', 'Weekly Schedule', 'maintenance/Maint_Maint_menu.py'),
                ('month_sched', 'Monthly Schedule', 'maintenance/Maint_Maint_menu.py'),
                ('annual_plan', 'Annual Plan', 'maintenance/Maint_Maint_menu.py'),
            ],
        }),
        ('equip_maint', 'Equipment Maintenance', {
            'title': 'Equipment Maintenance',
            'items': [
                ('equip_list', 'Equipment List', 'maintenance/Maint_Maint_menu.py'),
                ('maint_hist', 'Maintenance History', 'maintenance/Maint_Maint_menu.py'),
                ('svc_records', 'Service Records', 'maintenance/Maint_Maint_menu.py'),
                ('equip_stat', 'Equipment Status', 'maintenance/Maint_Maint_menu.py'),
            ],
        }),
        ('parts_inv', 'Parts Inventory', {
            'title': 'Parts Inventory',
            'items': [
                ('view_inv', 'View Inventory', 'production/inventory.py'),
                ('parts_req', 'Parts Request', 'production/inventory.py'),
                ('reorder', 'Reorder List', 'production/inventory.py'),
                ('parts_hist', 'Parts History', 'production/inventory.py'),
            ],
        }),
        ('maint_reports', 'Maintenance Reports', {
            'title': 'Maintenance Reports',
            'items': [
                ('daily_rpt', 'Daily Report', 'maintenance/Maint_Maint_menu.py'),
                ('week_rpt', 'Weekly Report', 'maintenance/Maint_Maint_menu.py'),
                ('cost_analy', 'Cost Analysis', 'maintenance/Maint_Maint_menu.py'),
                ('down_rpt', 'Downtime Report', 'maintenance/Maint_Maint_menu.py'),
            ],
        }),
        ('safety_insp', 'Safety Inspections', {
            'title': 'Safety Inspections',
            'items': [
                ('sched_insp', 'Schedule Inspection', 'maintenance/Maint_Maint_menu.py'),
                ('insp_chk', 'Inspection Checklist', 'maintenance/Maint_Maint_menu.py'),
                ('insp_res', 'Inspection Results', 'maintenance/Maint_Maint_menu.py'),
                ('corr_act', 'Corrective Actions', 'maintenance/Maint_Maint_menu.py'),
            ],
        }),
        ('prev_maint', 'Preventive Maintenance', {
            'title': 'Preventive Maintenance',
            'items': [
                ('pm_sched', 'PM Schedule', 'maintenance/Maint_Maint_menu.py'),
                ('pm_chk', 'PM Checklists', 'maintenance/Maint_Maint_menu.py'),
                ('pm_hist', 'PM History', 'maintenance/Maint_Maint_menu.py'),
                ('pm_rpts', 'PM Reports', 'maintenance/Maint_Maint_menu.py'),
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
                ('act_camp', 'Active Campaigns', 'marketing/marketing_menu.py'),
                ('new_camp', 'Create Campaign', 'marketing/marketing_menu.py'),
                ('camp_cal', 'Campaign Calendar', 'marketing/marketing_menu.py'),
                ('camp_res', 'Campaign Results', 'marketing/marketing_menu.py'),
            ],
        }),
        ('mkt_research', 'Market Research', {
            'title': 'Market Research',
            'items': [
                ('res_proj', 'Research Projects', 'marketing/marketing_menu.py'),
                ('comp_analy', 'Competitor Analysis', 'marketing/marketing_menu.py'),
                ('surv_mgmt', 'Survey Management', 'marketing/marketing_menu.py'),
                ('mkt_trends', 'Market Trends', 'marketing/marketing_menu.py'),
            ],
        }),
        ('advertising', 'Advertising', {
            'title': 'Advertising',
            'items': [
                ('ad_mgmt', 'Ad Management', 'marketing/marketing_menu.py'),
                ('ad_budget', 'Ad Budget', 'marketing/marketing_menu.py'),
                ('ad_perf', 'Ad Performance', 'marketing/marketing_menu.py'),
                ('ad_cal', 'Ad Calendar', 'marketing/marketing_menu.py'),
            ],
        }),
        ('analytics', 'Analytics', {
            'title': 'Analytics',
            'items': [
                ('web_analy', 'Website Analytics', 'marketing/marketing_menu.py'),
                ('camp_analy', 'Campaign Analytics', 'marketing/marketing_menu.py'),
                ('sales_analy', 'Sales Analytics', 'marketing/marketing_menu.py'),
                ('cust_rpts', 'Custom Reports', 'marketing/marketing_menu.py'),
            ],
        }),
        ('content_mgmt', 'Content Management', {
            'title': 'Content Management',
            'items': [
                ('cont_cal', 'Content Calendar', 'marketing/marketing_menu.py'),
                ('blog', 'Blog Posts', 'marketing/marketing_menu.py'),
                ('mkt_mat', 'Marketing Materials', 'marketing/marketing_menu.py'),
                ('cont_arch', 'Content Archive', 'marketing/marketing_menu.py'),
            ],
        }),
        ('social_media', 'Social Media', {
            'title': 'Social Media',
            'items': [
                ('post_mgmt', 'Post Management', 'marketing/marketing_menu.py'),
                ('social_cal', 'Social Calendar', 'marketing/marketing_menu.py'),
                ('eng_rpts', 'Engagement Reports', 'marketing/marketing_menu.py'),
                ('acct_mgmt', 'Account Management', 'marketing/marketing_menu.py'),
            ],
        }),
        ('email_mkt', 'Email Marketing', {
            'title': 'Email Marketing',
            'items': [
                ('email_camp', 'Email Campaigns', 'marketing/marketing_menu.py'),
                ('sub_lists', 'Subscriber Lists', 'marketing/marketing_menu.py'),
                ('email_tmpl', 'Email Templates', 'marketing/marketing_menu.py'),
                ('email_analy', 'Email Analytics', 'marketing/marketing_menu.py'),
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
                ('new_order', 'New Order', 'sales/sales_orders.py'),
                ('open_orders', 'Open Orders', 'sales/sales_orders.py'),
                ('order_hist', 'Order History', 'sales/sales_orders.py'),
                ('order_stat', 'Order Status', 'sales/sales_orders.py'),
            ],
        }),
        ('cust_accounts', 'Customer Accounts', {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list', 'Account List', 'customers/customers.py'),
                ('new_acct', 'New Account', 'customers/customers.py'),
                ('acct_det', 'Account Details', 'customers/customers.py'),
                ('acct_hist', 'Account History', 'customers/customers.py'),
            ],
        }),
        ('sales_reports', 'Sales Reports', {
            'title': 'Sales Reports',
            'items': [
                ('daily_sales', 'Daily Sales', 'sales/Sales_menu.py'),
                ('month_sales', 'Monthly Sales', 'sales/Sales_menu.py'),
                ('annual_rpt', 'Annual Report', 'sales/Sales_menu.py'),
                ('by_rep', 'Sales by Rep', 'sales/Sales_menu.py'),
            ],
        }),
        ('quotes', 'Quotes', {
            'title': 'Quotes',
            'items': [
                ('new_quote', 'Create Quote', 'sales/Sales_menu.py'),
                ('act_quotes', 'Active Quotes', 'sales/Sales_menu.py'),
                ('quote_hist', 'Quote History', 'sales/Sales_menu.py'),
                ('conv_order', 'Convert to Order', 'sales/Sales_menu.py'),
            ],
        }),
        ('leads', 'Leads & Opportunities', {
            'title': 'Leads & Opportunities',
            'items': [
                ('new_lead', 'New Lead', 'sales/Sales_menu.py'),
                ('act_leads', 'Active Leads', 'sales/Sales_menu.py'),
                ('opp_pipe', 'Opportunities Pipeline', 'sales/Sales_menu.py'),
                ('lead_rpts', 'Lead Reports', 'sales/Sales_menu.py'),
            ],
        }),
        ('contracts', 'Contracts', {
            'title': 'Contracts',
            'items': [
                ('act_cont', 'Active Contracts', 'sales/Sales_menu.py'),
                ('new_cont', 'Create Contract', 'sales/Sales_menu.py'),
                ('cont_renew', 'Contract Renewals', 'sales/Sales_menu.py'),
                ('cont_arch', 'Contract Archive', 'sales/Sales_menu.py'),
            ],
        }),
        ('forecasting', 'Sales Forecasting', {
            'title': 'Sales Forecasting',
            'items': [
                ('cur_fore', 'Current Forecast', 'sales/Sales_menu.py'),
                ('fore_rep', 'Forecast by Rep', 'sales/Sales_menu.py'),
                ('fore_prod', 'Forecast by Product', 'sales/Sales_menu.py'),
                ('fore_rpts', 'Forecast Reports', 'sales/Sales_menu.py'),
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
                ('create_wo', 'Create Work Order', 'production/work_orders.py'),
                ('open_wo', 'Open Work Orders', 'production/work_orders.py'),
                ('inprog_wo', 'In Progress', 'production/work_orders.py'),
                ('comp_wo', 'Completed', 'production/work_orders.py'),
            ],
        }),
        ('mrp', 'MRP Planning', {
            'title': 'Material Requirements Planning',
            'items': [
                ('mrp_home', 'MRP Home', 'production/mrp.py'),
                ('run_mrp', 'Run MRP Plan', 'production/mrp.py'),
                ('mrp_demand', 'View Demand', 'production/mrp.py'),
                ('mrp_rpts', 'MRP Reports', 'production/mrp.py'),
            ],
        }),
        ('prod_schedule', 'Production Schedule', {
            'title': 'Production Schedule',
            'items': [
                ('daily_sched', 'Daily Schedule', 'production/prod_prod_menu.py'),
                ('week_sched', 'Weekly Schedule', 'production/prod_prod_menu.py'),
                ('month_sched', 'Monthly Schedule', 'production/prod_prod_menu.py'),
                ('sched_cal', 'Schedule Calendar', 'production/prod_prod_menu.py'),
                ('gantt_sched', 'Gantt Chart', 'production/prod_prod_menu.py'),
            ],
        }),
        ('inventory', 'Inventory', {
            'title': 'Inventory',
            'items': [
                ('raw_mat', 'Raw Materials', 'production/inventory.py'),
                ('fin_goods', 'Finished Goods', 'production/inventory.py'),
                ('wip_inv', 'WIP Inventory', 'production/inventory.py'),
                ('inv_rpts', 'Inventory Reports', 'production/inventory.py'),
            ],
        }),
        ('equip_status', 'Equipment Status', {
            'title': 'Equipment Status',
            'items': [
                ('equip_list', 'Equipment List', 'production/prod_prod_menu.py'),
                ('stat_dash', 'Status Dashboard', 'production/prod_prod_menu.py'),
                ('down_log', 'Downtime Log', 'production/prod_prod_menu.py'),
                ('maint_req', 'Maintenance Requests', 'production/prod_prod_menu.py'),
            ],
        }),
        ('quality_ctrl', 'Quality Control', {
            'title': 'Quality Control',
            'items': [
                ('insp_res', 'Inspection Results', 'production/prod_prod_menu.py'),
                ('non_conf', 'Non-Conformances', 'production/prod_prod_menu.py'),
                ('qc_rpts', 'QC Reports', 'production/prod_prod_menu.py'),
                ('rej_analy', 'Reject Analysis', 'production/prod_prod_menu.py'),
            ],
        }),
        ('prod_reports', 'Production Reports', {
            'title': 'Production Reports',
            'items': [
                ('daily_prod', 'Daily Production', 'production/prod_prod_menu.py'),
                ('week_sum', 'Weekly Summary', 'production/prod_prod_menu.py'),
                ('eff_rpt', 'Efficiency Report', 'production/prod_prod_menu.py'),
                ('scrap_rpt', 'Scrap Report', 'production/prod_prod_menu.py'),
            ],
        }),
        ('labor_tracking', 'Labor Tracking', {
            'title': 'Labor Tracking',
            'items': [
                ('cur_labor', 'Current Labor', 'production/prod_prod_menu.py'),
                ('labor_shft', 'Labor by Shift', 'production/prod_prod_menu.py'),
                ('labor_job', 'Labor by Job', 'production/prod_prod_menu.py'),
                ('labor_rpts', 'Labor Reports', 'production/prod_prod_menu.py'),
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
                ('new_ship', 'New Shipment', 'production/prod_ship_dept.py'),
                ('pend_ship', 'Pending Shipments', 'production/prod_ship_dept.py'),
                ('shipped', 'Shipped Orders', 'production/prod_ship_dept.py'),
                ('deliv_conf', 'Delivery Confirmation', 'production/prod_ship_dept.py'),
            ],
        }),
        ('ship_schedule', 'Shipping Schedule', {
            'title': 'Shipping Schedule',
            'items': [
                ('today_sched', "Today's Schedule", 'production/prod_ship_dept.py'),
                ('week_sched', 'Weekly Schedule', 'production/prod_ship_dept.py'),
                ('sched_cal', 'Schedule Calendar', 'production/prod_ship_dept.py'),
                ('rush_orders', 'Rush Orders', 'production/prod_ship_dept.py'),
            ],
        }),
        ('receiving', 'Receiving', {
            'title': 'Receiving',
            'items': [
                ('inbound', 'Inbound Shipments', 'production/prod_ship_dept.py'),
                ('recv_items', 'Receive Items', 'production/prod_ship_dept.py'),
                ('recv_rpts', 'Receiving Reports', 'production/prod_ship_dept.py'),
                ('disc_rpts', 'Discrepancy Reports', 'production/prod_ship_dept.py'),
            ],
        }),
        ('carrier_mgmt', 'Carrier Management', {
            'title': 'Carrier Management',
            'items': [
                ('carr_list', 'Carrier List', 'production/prod_ship_dept.py'),
                ('carr_rates', 'Carrier Rates', 'production/prod_ship_dept.py'),
                ('perf_rpts', 'Performance Reports', 'production/prod_ship_dept.py'),
                ('carr_cont', 'Carrier Contracts', 'production/prod_ship_dept.py'),
            ],
        }),
        ('tracking', 'Tracking', {
            'title': 'Tracking',
            'items': [
                ('track_ship', 'Track Shipment', 'production/prod_ship_dept.py'),
                ('track_dash', 'Tracking Dashboard', 'production/prod_ship_dept.py'),
                ('deliv_stat', 'Delivery Status', 'production/prod_ship_dept.py'),
                ('exc_rpts', 'Exception Reports', 'production/prod_ship_dept.py'),
            ],
        }),
        ('ship_reports', 'Shipping Reports', {
            'title': 'Shipping Reports',
            'items': [
                ('daily_rpt', 'Daily Report', 'production/prod_ship_dept.py'),
                ('week_sum', 'Weekly Summary', 'production/prod_ship_dept.py'),
                ('cost_analy', 'Cost Analysis', 'production/prod_ship_dept.py'),
                ('perf_rpt', 'Performance Report', 'production/prod_ship_dept.py'),
            ],
        }),
        ('returns_proc', 'Returns Processing', {
            'title': 'Returns Processing',
            'items': [
                ('new_return', 'New Return', 'production/prod_ship_dept.py'),
                ('pend_ret', 'Pending Returns', 'production/prod_ship_dept.py'),
                ('ret_hist', 'Return History', 'production/prod_ship_dept.py'),
                ('ret_rpts', 'Return Reports', 'production/prod_ship_dept.py'),
            ],
        }),
        ('wms', 'Warehouse Management', {
            'title': 'Warehouse Management',
            'items': [
                ('bin_master', 'Bin Master', 'production/prod_ship_dept.py'),
                ('putaway_rules', 'Put-Away Rules', 'production/prod_ship_dept.py'),
                ('pick_lists', 'Pick Lists', 'production/prod_ship_dept.py'),
                ('pack_station', 'Pack Station', 'production/prod_ship_dept.py'),
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
                ('new_req', 'New Request', 'quality/QA_Lab_menu.py'),
                ('pend_req', 'Pending Requests', 'quality/QA_Lab_menu.py'),
                ('inprog_req', 'In Progress', 'quality/QA_Lab_menu.py'),
                ('comp_tests', 'Completed Tests', 'quality/QA_Lab_menu.py'),
            ],
        }),
        ('lab_results', 'Lab Results', {
            'title': 'Lab Results',
            'items': [
                ('recent_res', 'Recent Results', 'quality/QA_Lab_menu.py'),
                ('search_res', 'Search Results', 'quality/QA_Lab_menu.py'),
                ('failed', 'Failed Tests', 'quality/QA_Lab_menu.py'),
                ('res_rpts', 'Result Reports', 'quality/QA_Lab_menu.py'),
            ],
        }),
        ('insp_reports', 'Inspection Reports', {
            'title': 'Inspection Reports',
            'items': [
                ('create_rpt', 'Create Report', 'quality/QA_Lab_menu.py'),
                ('pend_rpts', 'Pending Reports', 'quality/QA_Lab_menu.py'),
                ('rpt_arch', 'Report Archive', 'quality/QA_Lab_menu.py'),
                ('rpt_sum', 'Report Summary', 'quality/QA_Lab_menu.py'),
            ],
        }),
        ('non_conformance', 'Non-Conformance', {
            'title': 'Non-Conformance',
            'items': [
                ('new_ncr', 'New NCR', 'quality/QA_Lab_menu.py'),
                ('open_ncrs', 'Open NCRs', 'quality/QA_Lab_menu.py'),
                ('ncr_hist', 'NCR History', 'quality/QA_Lab_menu.py'),
                ('ncr_rpts', 'NCR Reports', 'quality/QA_Lab_menu.py'),
            ],
        }),
        ('calibration', 'Calibration', {
            'title': 'Calibration',
            'items': [
                ('cal_sched', 'Calibration Schedule', 'quality/QA_Lab_menu.py'),
                ('cal_records', 'Calibration Records', 'quality/QA_Lab_menu.py'),
                ('overdue', 'Overdue Items', 'quality/QA_Lab_menu.py'),
                ('cal_rpts', 'Calibration Reports', 'quality/QA_Lab_menu.py'),
            ],
        }),
        ('sample_mgmt', 'Sample Management', {
            'title': 'Sample Management',
            'items': [
                ('recv_sample', 'Receive Sample', 'quality/QA_Lab_menu.py'),
                ('samp_track', 'Sample Tracking', 'quality/QA_Lab_menu.py'),
                ('samp_disp', 'Sample Disposal', 'quality/QA_Lab_menu.py'),
                ('samp_rpts', 'Sample Reports', 'quality/QA_Lab_menu.py'),
            ],
        }),
        ('lab_reports', 'Lab Reports', {
            'title': 'Lab Reports',
            'items': [
                ('daily_rpts', 'Daily Reports', 'quality/QA_Lab_menu.py'),
                ('week_sum', 'Weekly Summary', 'quality/QA_Lab_menu.py'),
                ('month_rpt', 'Monthly Report', 'quality/QA_Lab_menu.py'),
                ('cust_rpts', 'Custom Reports', 'quality/QA_Lab_menu.py'),
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
        ('pers_crm', 'Personnel CRM', 'personnel/personnel_crm.py'),
        ('reg_form', 'Registration Form', 'registration_form.py'),
        ('upd_pass', 'Update Password', 'payroll/update_users.py'),
        ('disp_dept', 'Display Department', 'personnel/display_people_department.py'),
        ('dept_entry', 'Dept Entry', 'personnel/dept_entry.py'),
        ('dept_sub', 'Dept Sub Entry', 'personnel/dept_sub_entry.py'),
        ('time_clock', 'Time Clock', _TIME_CLOCK_MENU),
        ('emp_records', 'Employee Records', {
            'title': 'Employee Records',
            'items': [
                ('view_recs', 'View Records', 'personnel/employees.py'),
                ('new_emp', 'New Employee', 'personnel/employees.py'),
                ('upd_rec', 'Update Record', 'personnel/employees.py'),
                ('emp_hist', 'Employment History', 'personnel/employees.py'),
            ],
        }),
        ('benefits', 'Benefits', {
            'title': 'Benefits',
            'items': [
                ('ben_enroll', 'Benefits Enrollment', 'personnel/personnel_crm.py'),
                ('ben_sum', 'Benefits Summary', 'personnel/personnel_crm.py'),
                ('cobra', 'COBRA Management', 'personnel/personnel_crm.py'),
                ('ben_rpts', 'Benefits Reports', 'personnel/personnel_crm.py'),
            ],
        }),
        ('perf_review', 'Performance Reviews', {
            'title': 'Performance Reviews',
            'items': [
                ('sched_rev', 'Schedule Review', 'personnel/personnel_crm.py'),
                ('pend_revs', 'Pending Reviews', 'personnel/personnel_crm.py'),
                ('rev_hist', 'Review History', 'personnel/personnel_crm.py'),
                ('perf_rpts', 'Performance Reports', 'personnel/personnel_crm.py'),
            ],
        }),
        ('disc_records', 'Disciplinary Records', {
            'title': 'Disciplinary Records',
            'items': [
                ('new_rec', 'New Record', 'personnel/personnel_crm.py'),
                ('view_recs', 'View Records', 'personnel/personnel_crm.py'),
                ('rec_hist', 'Record History', 'personnel/personnel_crm.py'),
                ('disc_rpts', 'Disciplinary Reports', 'personnel/personnel_crm.py'),
            ],
        }),
        ('training', 'Training & Development', {
            'title': 'Training & Development',
            'items': [
                ('train_cal', 'Training Calendar', 'personnel/personnel_crm.py'),
                ('train_recs', 'Training Records', 'personnel/personnel_crm.py'),
                ('course_mgmt', 'Course Management', 'personnel/personnel_crm.py'),
                ('cert_track', 'Certification Tracking', 'personnel/personnel_crm.py'),
            ],
        }),
        ('onboarding', 'Onboarding', {
            'title': 'Onboarding',
            'items': [
                ('hire_chk', 'New Hire Checklist', 'personnel/personnel_crm.py'),
                ('onb_stat', 'Onboarding Status', 'personnel/personnel_crm.py'),
                ('doc_coll', 'Document Collection', 'personnel/personnel_crm.py'),
                ('onb_rpts', 'Onboarding Reports', 'personnel/personnel_crm.py'),
            ],
        }),
    ],
}

_CS_MENU = {
    'title': 'Customer Service Menu',
    'items': [
        ('cust_entry', 'Customer Entry Screen', 'customers/customer_entry.py'),
        ('open_tickets', 'Open Tickets', {
            'title': 'Open Tickets',
            'items': [
                ('all_tickets', 'View All Tickets', 'customer_service/cs_calls.py'),
                ('my_tickets', 'My Tickets', 'customer_service/cs_calls.py'),
                ('hi_pri', 'High Priority', 'customer_service/cs_calls.py'),
                ('tick_search', 'Ticket Search', 'customer_service/cs_calls.py'),
            ],
        }),
        ('cust_accounts', 'Customer Accounts', {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list', 'Account List', 'customers/customers.py'),
                ('new_acct', 'New Account', 'customers/customers.py'),
                ('acct_det', 'Account Details', 'customers/customers.py'),
                ('acct_hist', 'Account History', 'customers/customers.py'),
            ],
        }),
        ('returns', 'Returns & Refunds', {
            'title': 'Returns & Refunds',
            'items': [
                ('new_return', 'New Return', 'customer_service/cs_calls.py'),
                ('pend_ret', 'Pending Returns', 'customer_service/cs_calls.py'),
                ('refund_proc', 'Refund Processing', 'customer_service/cs_calls.py'),
                ('ret_rpts', 'Returns Reports', 'customer_service/cs_calls.py'),
            ],
        }),
        ('knowledge_base', 'Knowledge Base', {
            'title': 'Knowledge Base',
            'items': [
                ('browse', 'Browse Articles', 'customer_service/cs_calls.py'),
                ('create_art', 'Create Article', 'customer_service/cs_calls.py'),
                ('art_mgmt', 'Article Management', 'customer_service/cs_calls.py'),
                ('kb_search', 'Search Knowledge Base', 'customer_service/cs_calls.py'),
            ],
        }),
        ('svc_reports', 'Service Reports', {
            'title': 'Service Reports',
            'items': [
                ('daily_rpt', 'Daily Report', 'customer_service/cs_reports.py'),
                ('week_sum', 'Weekly Summary', 'customer_service/cs_reports.py'),
                ('res_rpts', 'Resolution Reports', 'customer_service/cs_reports.py'),
                ('csat_rpts', 'Customer Satisfaction', 'customer_service/cs_reports.py'),
            ],
        }),
        ('surveys', 'Surveys & Feedback', {
            'title': 'Surveys & Feedback',
            'items': [
                ('act_surv', 'Active Surveys', 'customer_service/cs_satisfaction.py'),
                ('new_surv', 'Create Survey', 'customer_service/cs_satisfaction.py'),
                ('surv_res', 'Survey Results', 'customer_service/cs_satisfaction.py'),
                ('feed_rpts', 'Feedback Reports', 'customer_service/cs_satisfaction.py'),
            ],
        }),
    ],
}

_IT_TECH = {
    'title': 'IT Technician',
    'items': [
        ('it_tasks', 'IT Tasks', 'it/IT_Tasks.py'),
        ('help_desk', 'Help Desk Tickets', {
            'title': 'Help Desk Tickets',
            'items': [
                ('new_ticket', 'New Ticket', 'it/it_calls.py'),
                ('open_tick', 'Open Tickets', 'it/it_calls.py'),
                ('my_tickets', 'My Assigned Tickets', 'it/it_calls.py'),
                ('tick_hist', 'Ticket History', 'it/it_calls.py'),
            ],
        }),
        ('asset_mgmt', 'Asset Management', {
            'title': 'Asset Management',
            'items': [
                ('asset_inv', 'Asset Inventory', 'it/it_calls.py'),
                ('new_asset', 'New Asset', 'it/it_calls.py'),
                ('asset_hist', 'Asset History', 'it/it_calls.py'),
                ('disposition', 'Disposition', 'it/it_calls.py'),
            ],
        }),
        ('net_status', 'Network Status', {
            'title': 'Network Status',
            'items': [
                ('net_dash', 'Network Dashboard', 'it/IT_technician.py'),
                ('bw_monitor', 'Bandwidth Monitor', 'it/IT_technician.py'),
                ('net_map', 'Network Map', 'it/IT_technician.py'),
                ('inc_log', 'Incident Log', 'it/IT_technician.py'),
            ],
        }),
        ('sw_install', 'Software Installations', {
            'title': 'Software Installations',
            'items': [
                ('pend_inst', 'Pending Installs', 'it/IT_technician.py'),
                ('sw_inv', 'Software Inventory', 'it/IT_technician.py'),
                ('lic_mgmt', 'License Management', 'it/IT_technician.py'),
                ('inst_hist', 'Installation History', 'it/IT_technician.py'),
            ],
        }),
        ('hw_repairs', 'Hardware Repairs', {
            'title': 'Hardware Repairs',
            'items': [
                ('new_repair', 'New Repair Request', 'it/IT_technician.py'),
                ('inprog', 'In Progress', 'it/IT_technician.py'),
                ('comp_rep', 'Completed Repairs', 'it/IT_technician.py'),
                ('rep_hist', 'Repair History', 'it/IT_technician.py'),
            ],
        }),
        ('user_accts', 'User Account Management', {
            'title': 'User Account Management',
            'items': [
                ('create_acct', 'Create Account', 'it/IT_technician.py'),
                ('reset_pw', 'Reset Password', 'it/IT_technician.py'),
                ('acct_stat', 'Account Status', 'it/IT_technician.py'),
                ('acct_audit', 'Account Audit', 'it/IT_technician.py'),
            ],
        }),
    ],
}

_PURCH_MENU = {
    'title': 'Purchasing Menu',
    'items': [
        ('prod_entry', 'Product Entry', 'production/product_entry_screen.py'),
        ('sup_entry', 'Supplier Entry', 'customers/Supplier_entry.py'),
        ('purch_orders', 'Purchase Orders', {
            'title': 'Purchase Orders',
            'items': [
                ('new_po', 'New PO', 'purchasing/purchase_orders.py'),
                ('open_pos', 'Open POs', 'purchasing/purchase_orders.py'),
                ('po_status', 'PO Status', 'purchasing/purchase_orders.py'),
                ('po_hist', 'PO History', 'purchasing/purchase_orders.py'),
            ],
        }),
        ('vendor_mgmt', 'Vendor Management', {
            'title': 'Vendor Management',
            'items': [
                ('vend_list', 'Vendor List', 'customers/suppliers.py'),
                ('new_vend', 'New Vendor', 'customers/suppliers.py'),
                ('vend_perf', 'Vendor Performance', 'customers/suppliers.py'),
                ('vend_cont', 'Vendor Contracts', 'customers/suppliers.py'),
            ],
        }),
        ('purch_reports', 'Purchase Reports', {
            'title': 'Purchase Reports',
            'items': [
                ('spend_sum', 'Spending Summary', 'purchasing/Purchasing_menu.py'),
                ('po_rpts', 'PO Reports', 'purchasing/Purchasing_menu.py'),
                ('budg_act', 'Budget vs. Actual', 'purchasing/Purchasing_menu.py'),
                ('cat_rpts', 'Category Reports', 'purchasing/Purchasing_menu.py'),
            ],
        }),
        ('receiving', 'Receiving', {
            'title': 'Receiving',
            'items': [
                ('pend_recv', 'Pending Receipts', 'production/receiving_dept.py'),
                ('recv_items', 'Receive Items', 'production/receiving_dept.py'),
                ('disc_rpts', 'Discrepancy Reports', 'production/receiving_dept.py'),
                ('recv_hist', 'Receiving History', 'production/receiving_dept.py'),
            ],
        }),
        ('contracts', 'Contract Management', {
            'title': 'Contract Management',
            'items': [
                ('act_cont', 'Active Contracts', 'purchasing/Purchasing_menu.py'),
                ('new_cont', 'New Contract', 'purchasing/Purchasing_menu.py'),
                ('cont_renew', 'Contract Renewals', 'purchasing/Purchasing_menu.py'),
                ('cont_arch', 'Contract Archive', 'purchasing/Purchasing_menu.py'),
            ],
        }),
        ('requisitions', 'Requisitions', {
            'title': 'Requisitions',
            'items': [
                ('new_req', 'New Requisition', 'purchase_requisitions.py'),
                ('pend_appr', 'Pending Approval', 'purchasing/Purchasing_Mgr_menu.py'),
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
            ('acct_pay', 'Accounts Payable', 'accounting/Accounts_payable.py'),
            ('acct_mgr', 'Accounting Manager', {
                'title': 'Accounting Manager',
                'items': [
                    ('ap', 'Accounts Payable', 'accounting/Accounts_payable.py'),
                    ('rcv', 'Accounts Receivable', 'accounting/Accounts_receivable.py'),
                    ('credit', 'Credit Department', 'customers/Credit_dept.py'),
                    ('pay', 'Payroll Department', 'payroll/Payroll_dept.py'),
                    ('fin_reports', 'Financial Reports', {
                        'title': 'Financial Reports',
                        'items': [
                            ('inc_stmt', 'Income Statement',
                             'accounting/General_ledger.py'),
                            ('bal_sheet', 'Balance Sheet',
                             'accounting/General_ledger.py'),
                            ('cash_flow', 'Cash Flow', 'accounting/General_ledger.py'),
                            ('cust_rpts', 'Custom Reports',
                             'accounting/General_ledger.py'),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('budg_plan', 'Budget Planning', 'finance/Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'finance/Budget_mgmt.py'),
                            ('budg_amend', 'Budget Amendments',
                             'finance/Budget_mgmt.py'),
                            ('budg_rpts', 'Budget Reports', 'finance/Budget_mgmt.py'),
                        ],
                    }),
                    ('audit_mgmt', 'Audit Management', {
                        'title': 'Audit Management',
                        'items': [
                            ('audit_sched', 'Audit Schedule', 'finance/Audit_mgmt.py'),
                            ('findings', 'Audit Findings', 'finance/Audit_mgmt.py'),
                            ('corr_act', 'Corrective Actions',
                             'finance/Audit_mgmt.py'),
                            ('audit_rpts', 'Audit Reports', 'finance/Audit_mgmt.py'),
                        ],
                    }),
                ],
            }),
            ('acct_rcv', 'Accounts Receivable', 'accounting/Accounts_receivable.py'),
            ('credit', 'Credit Department', 'customers/Credit_dept.py'),
            ('payroll', 'Payroll Department', 'payroll/Payroll_dept.py'),
            ('gen_ledger', 'General Ledger', 'accounting/General_ledger.py'),
            ('multi_entity', 'Multi-Entity', {
                'title': 'Multi-Entity',
                'items': [
                    ('companies', 'Companies', 'accounting/General_ledger.py'),
                    ('intercompany', 'Intercompany Transactions',
                     'accounting/General_ledger.py'),
                    ('consol_fin', 'Consolidated Financials',
                     'accounting/General_ledger.py'),
                ],
            }),
            ('budget_mgmt', 'Budget Management', {
                'title': 'Budget Management',
                'items': [
                    ('budg_plan', 'Budget Planning', 'finance/Budget_mgmt.py'),
                    ('budg_act', 'Budget vs. Actual', 'finance/Budget_mgmt.py'),
                    ('budg_amend', 'Budget Amendments', 'finance/Budget_mgmt.py'),
                    ('budg_rpts', 'Budget Reports', 'finance/Budget_mgmt.py'),
                ],
            }),
            ('fin_reports', 'Financial Reports', {
                'title': 'Financial Reports',
                'items': [
                    ('inc_stmt', 'Income Statement', 'accounting/General_ledger.py'),
                    ('bal_sheet', 'Balance Sheet', 'accounting/General_ledger.py'),
                    ('cash_flow', 'Cash Flow', 'accounting/General_ledger.py'),
                    ('cust_rpts', 'Custom Reports', 'accounting/General_ledger.py'),
                ],
            }),
            ('tax_mgmt', 'Tax Management', {
                'title': 'Tax Management',
                'items': [
                    ('tax_cal', 'Tax Calendar', 'finance/Tax_mgmt.py'),
                    ('tax_filing', 'Tax Filing', 'finance/Tax_mgmt.py'),
                    ('tax_pay', 'Tax Payments', 'finance/Tax_mgmt.py'),
                    ('tax_rpts', 'Tax Reports', 'finance/Tax_mgmt.py'),
                ],
            }),
            ('exp_reports', 'Expense Reports', {
                'title': 'Expense Reports',
                'items': [
                    ('sub_exp', 'Submit Expense', 'accounting/Accounts_payable.py'),
                    ('pend_appr', 'Pending Approval', 'accounting/Accounts_payable.py'),
                    ('appr_exp', 'Approved Expenses', 'accounting/Accounts_payable.py'),
                    ('exp_sum', 'Expense Summary', 'accounting/Accounts_payable.py'),
                ],
            }),
            ('bank_recon', 'Bank Reconciliation', {
                'title': 'Bank Reconciliation',
                'items': [
                    ('recon_acct', 'Reconcile Account', 'accounting/General_ledger.py'),
                    ('pend_items', 'Pending Items', 'accounting/General_ledger.py'),
                    ('recon_hist', 'Reconciliation History',
                     'accounting/General_ledger.py'),
                    ('bank_rpts', 'Bank Reports', 'accounting/General_ledger.py'),
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
                             'customer_service/cs_reports.py'),
                            ('week_sum', 'Weekly Summary', 'customer_service/cs_reports.py'),
                            ('res_analy', 'Resolution Analysis',
                             'customer_service/cs_reports.py'),
                            ('sla_rpts', 'SLA Reports', 'customer_service/cs_reports.py'),
                        ],
                    }),
                    ('staff_mgmt', 'Staff Management', {
                        'title': 'Staff Management',
                        'items': [
                            ('staff_sched', 'Staff Schedule',
                             'customer_service/cs_staff_mgmt.py'),
                            ('perf_met', 'Performance Metrics',
                             'customer_service/cs_staff_mgmt.py'),
                            ('staff_train', 'Staff Training',
                             'customer_service/cs_staff_mgmt.py'),
                            ('staff_rpts', 'Staff Reports',
                             'customer_service/cs_staff_mgmt.py'),
                        ],
                    }),
                    ('cust_sat', 'Customer Satisfaction', {
                        'title': 'Customer Satisfaction',
                        'items': [
                            ('csat_res', 'CSAT Survey Results',
                             'customer_service/cs_satisfaction.py'),
                            ('nps_rpts', 'NPS Reports', 'customer_service/cs_satisfaction.py'),
                            ('sat_trends', 'Satisfaction Trends',
                             'customer_service/cs_satisfaction.py'),
                            ('impr_plans', 'Improvement Plans',
                             'customer_service/cs_satisfaction.py'),
                        ],
                    }),
                    ('escalations', 'Escalations', {
                        'title': 'Escalations',
                        'items': [
                            ('act_esc', 'Active Escalations',
                             'customer_service/cs_escalations.py'),
                            ('esc_hist', 'Escalation History',
                             'customer_service/cs_escalations.py'),
                            ('esc_rpts', 'Escalation Reports',
                             'customer_service/cs_escalations.py'),
                            ('res_track', 'Resolution Tracking',
                             'customer_service/cs_escalations.py'),
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
                    ('engineers', 'Engineers', 'engineering/engineer.py'),
                    ('proj_appr', 'Project Approvals', {
                        'title': 'Project Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals', 'engineering/eng_mgr.py'),
                            ('appr_proj', 'Approved Projects', 'engineering/eng_mgr.py'),
                            ('rej_proj', 'Rejected Projects', 'engineering/eng_mgr.py'),
                            ('appr_hist', 'Approval History', 'engineering/eng_mgr.py'),
                        ],
                    }),
                    ('resource', 'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc', 'Resource Allocation', 'engineering/eng_mgr.py'),
                            ('cap_plan', 'Capacity Planning', 'engineering/eng_mgr.py'),
                            ('res_rpts', 'Resource Reports', 'engineering/eng_mgr.py'),
                            ('avail_cal', 'Availability Calendar',
                             'engineering/eng_mgr.py'),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('eng_budg', 'Engineering Budget',
                             'finance/Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'finance/Budget_mgmt.py'),
                            ('cost_rpts', 'Cost Reports', 'finance/Budget_mgmt.py'),
                            ('budg_req', 'Budget Requests', 'finance/Budget_mgmt.py'),
                        ],
                    }),
                    ('eng_reports', 'Engineering Reports', {
                        'title': 'Engineering Reports',
                        'items': [
                            ('proj_stat', 'Project Status', 'engineering/eng_mgr.py'),
                            ('res_util', 'Resource Utilization', 'engineering/eng_mgr.py'),
                            ('kpi_dash', 'KPI Dashboard', 'engineering/eng_mgr.py'),
                            ('month_rpts', 'Monthly Reports', 'engineering/eng_mgr.py'),
                        ],
                    }),
                ],
            }),
            ('engineers', 'Engineers', 'engineering/engineer.py'),
            ('proj_mgmt', 'Project Management', {
                'title': 'Project Management',
                'items': [
                    ('act_proj', 'Active Projects', 'engineering/engineer.py'),
                    ('new_proj', 'New Project', 'engineering/engineer.py'),
                    ('proj_time', 'Project Timeline', 'engineering/engineer.py'),
                    ('proj_rpts', 'Project Reports', 'engineering/engineer.py'),
                ],
            }),
            ('design_docs', 'Design Documents', {
                'title': 'Design Documents',
                'items': [
                    ('doc_lib', 'Document Library', 'engineering/engineer.py'),
                    ('new_doc', 'New Document', 'engineering/engineer.py'),
                    ('doc_review', 'Document Review', 'engineering/engineer.py'),
                    ('archive', 'Archive', 'engineering/engineer.py'),
                ],
            }),
            ('bom', 'Bill of Materials', {
                'title': 'Bill of Materials',
                'items': [
                    ('bom_list', 'BOM List', 'engineering/engineer.py'),
                    ('new_bom', 'Create BOM', 'engineering/engineer.py'),
                    ('bom_rev', 'BOM Revision', 'engineering/engineer.py'),
                    ('bom_rpts', 'BOM Reports', 'engineering/engineer.py'),
                ],
            }),
            ('chg_orders', 'Change Orders', {
                'title': 'Change Orders',
                'items': [
                    ('new_co', 'New Change Order', 'engineering/engineer.py'),
                    ('pend_appr', 'Pending Approval', 'engineering/engineer.py'),
                    ('appr_chg', 'Approved Changes', 'engineering/engineer.py'),
                    ('chg_hist', 'Change History', 'engineering/engineer.py'),
                ],
            }),
            ('test_val', 'Test & Validation', {
                'title': 'Test & Validation',
                'items': [
                    ('test_plans', 'Test Plans', 'engineering/engineer.py'),
                    ('test_res', 'Test Results', 'engineering/engineer.py'),
                    ('val_rpts', 'Validation Reports', 'engineering/engineer.py'),
                    ('issue_track', 'Issue Tracking', 'engineering/engineer.py'),
                ],
            }),
            ('eng_reports', 'Engineering Reports', {
                'title': 'Engineering Reports',
                'items': [
                    ('proj_stat', 'Project Status', 'engineering/engineer.py'),
                    ('design_rev', 'Design Review', 'engineering/engineer.py'),
                    ('res_rpt', 'Resource Report', 'engineering/engineer.py'),
                    ('cust_rpts', 'Custom Reports', 'engineering/engineer.py'),
                ],
            }),
            ('standards', 'Standards & Compliance', {
                'title': 'Standards & Compliance',
                'items': [
                    ('std_lib', 'Standards Library', 'engineering/engineer.py'),
                    ('comp_chk', 'Compliance Checklist', 'engineering/engineer.py'),
                    ('audit_res', 'Audit Results', 'engineering/engineer.py'),
                    ('reg_upd', 'Regulatory Updates', 'engineering/engineer.py'),
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
                            ('it_budg', 'IT Budget', 'finance/Budget_mgmt.py'),
                            ('hw_proc', 'Hardware Procurement',
                             'finance/Budget_mgmt.py'),
                            ('sw_lic', 'Software Licensing', 'finance/Budget_mgmt.py'),
                            ('proc_rpts', 'Procurement Reports',
                             'finance/Budget_mgmt.py'),
                        ],
                    }),
                    ('vendor_con', 'Vendor Contracts', {
                        'title': 'Vendor Contracts',
                        'items': [
                            ('act_cont', 'Active Contracts', 'it/IT_mgr.py'),
                            ('cont_renew', 'Contract Renewals', 'it/IT_mgr.py'),
                            ('vend_perf', 'Vendor Performance', 'it/IT_mgr.py'),
                            ('cont_arch', 'Contract Archive', 'it/IT_mgr.py'),
                        ],
                    }),
                    ('it_projects', 'IT Projects', {
                        'title': 'IT Projects',
                        'items': [
                            ('act_proj', 'Active Projects', 'it/IT_mgr.py'),
                            ('proj_pipe', 'Project Pipeline', 'it/IT_mgr.py'),
                            ('proj_rpts', 'Project Reports', 'it/IT_mgr.py'),
                            ('res_alloc', 'Resource Allocation', 'it/IT_mgr.py'),
                        ],
                    }),
                    ('security', 'Security Management', {
                        'title': 'Security Management',
                        'items': [
                            ('sec_dash', 'Security Dashboard', 'it/IT_mgr.py'),
                            ('inc_rpts', 'Incident Reports', 'it/IT_mgr.py'),
                            ('vuln_mgmt', 'Vulnerability Management',
                             'it/IT_mgr.py'),
                            ('comp_rpts', 'Compliance Reports', 'it/IT_mgr.py'),
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
                             'maintenance/Maint_mgr_menu.py'),
                            ('appr_wo', 'Approved Work Orders',
                             'maintenance/Maint_mgr_menu.py'),
                            ('rej_wo', 'Rejected', 'maintenance/Maint_mgr_menu.py'),
                            ('appr_hist', 'Approval History',
                             'maintenance/Maint_mgr_menu.py'),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('maint_budg', 'Maintenance Budget',
                             'finance/Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'finance/Budget_mgmt.py'),
                            ('cost_analy', 'Cost Analysis', 'finance/Budget_mgmt.py'),
                            ('budg_req', 'Budget Requests', 'finance/Budget_mgmt.py'),
                        ],
                    }),
                    ('maint_rpts', 'Maintenance Reports', {
                        'title': 'Maintenance Reports',
                        'items': [
                            ('daily_rpt', 'Daily Report', 'maintenance/Maint_mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'maintenance/Maint_mgr_menu.py'),
                            ('equip_rpts', 'Equipment Reports',
                             'maintenance/Maint_mgr_menu.py'),
                            ('cost_rpts', 'Cost Reports', 'maintenance/Maint_mgr_menu.py'),
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
                            ('budg_over', 'Budget Overview', 'finance/Budget_mgmt.py'),
                            ('budg_camp', 'Budget by Campaign',
                             'finance/Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'finance/Budget_mgmt.py'),
                            ('budg_req', 'Budget Requests', 'finance/Budget_mgmt.py'),
                        ],
                    }),
                    ('camp_appr', 'Campaign Approvals', {
                        'title': 'Campaign Approvals',
                        'items': [
                            ('pend_appr', 'Pending Approvals',
                             'marketing/marketing_mgr_menu.py'),
                            ('appr_camp', 'Approved Campaigns',
                             'marketing/marketing_mgr_menu.py'),
                            ('camp_arch', 'Campaign Archive',
                             'marketing/marketing_mgr_menu.py'),
                            ('appr_hist', 'Approval History',
                             'marketing/marketing_mgr_menu.py'),
                        ],
                    }),
                    ('mkt_reports', 'Marketing Reports', {
                        'title': 'Marketing Reports',
                        'items': [
                            ('camp_perf', 'Campaign Performance',
                             'marketing/marketing_mgr_menu.py'),
                            ('roi_rpts', 'ROI Reports',
                             'marketing/marketing_mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'marketing/marketing_mgr_menu.py'),
                            ('kpi_dash', 'KPI Dashboard',
                             'marketing/marketing_mgr_menu.py'),
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
                             'personnel/personnel_mgr_menu.py'),
                            ('appl_track', 'Applicant Tracking',
                             'personnel/personnel_mgr_menu.py'),
                            ('int_sched', 'Interview Schedule',
                             'personnel/personnel_mgr_menu.py'),
                            ('offer_mgmt', 'Offer Management',
                             'personnel/personnel_mgr_menu.py'),
                        ],
                    }),
                    ('term', 'Terminations', {
                        'title': 'Terminations',
                        'items': [
                            ('term_proc', 'Termination Process',
                             'personnel/personnel_mgr_menu.py'),
                            ('exit_int', 'Exit Interviews',
                             'personnel/personnel_mgr_menu.py'),
                            ('final_pay', 'Final Pay Processing',
                             'personnel/personnel_mgr_menu.py'),
                            ('offboard', 'Offboarding Checklist',
                             'personnel/personnel_mgr_menu.py'),
                        ],
                    }),
                    ('salary', 'Salary Management', {
                        'title': 'Salary Management',
                        'items': [
                            ('sal_review', 'Salary Review',
                             'personnel/personnel_mgr_menu.py'),
                            ('sal_adj', 'Salary Adjustments',
                             'personnel/personnel_mgr_menu.py'),
                            ('comp_rpts', 'Compensation Reports',
                             'personnel/personnel_mgr_menu.py'),
                            ('pay_grades', 'Pay Grades',
                             'personnel/personnel_mgr_menu.py'),
                        ],
                    }),
                    ('hr_reports', 'HR Reports', {
                        'title': 'HR Reports',
                        'items': [
                            ('hd_rpt', 'Headcount Report',
                             'personnel/personnel_mgr_menu.py'),
                            ('turn_rpt', 'Turnover Report',
                             'personnel/personnel_mgr_menu.py'),
                            ('comp_rpts', 'Compliance Reports',
                             'personnel/personnel_mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'personnel/personnel_mgr_menu.py'),
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
                             'production/prod_mgr_Menu.py'),
                            ('week_sum', 'Weekly Summary', 'production/prod_mgr_Menu.py'),
                            ('eff_rpts', 'Efficiency Reports',
                             'production/prod_mgr_Menu.py'),
                            ('kpi_dash', 'KPI Dashboard', 'production/prod_mgr_Menu.py'),
                        ],
                    }),
                    ('resource', 'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc', 'Resource Allocation',
                             'production/prod_mgr_Menu.py'),
                            ('cap_plan', 'Capacity Planning',
                             'production/prod_mgr_Menu.py'),
                            ('res_rpts', 'Resource Reports',
                             'production/prod_mgr_Menu.py'),
                            ('wf_plan', 'Workforce Planning',
                             'production/prod_mgr_Menu.py'),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('prod_budg', 'Production Budget',
                             'finance/Budget_mgmt.py'),
                            ('cost_analy', 'Cost Analysis', 'finance/Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'finance/Budget_mgmt.py'),
                            ('budg_rpts', 'Budget Reports', 'finance/Budget_mgmt.py'),
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
                     'production/prod_mgr_Menu.py'),
                    ('sf_shift_plan', 'Shift Plan', 'production/prod_mgr_Menu.py'),
                    ('sf_dashboard', 'Live OEE Dashboard',
                     'production/prod_mgr_Menu.py'),
                    ('sf_tv', 'Shop Floor TV Display', 'production/prod_mgr_Menu.py'),
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
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('appr_pos', 'Approved POs',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('rej_pos', 'Rejected POs',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('appr_hist', 'Approval History',
                             'purchasing/Purchasing_Mgr_menu.py'),
                        ],
                    }),
                    ('budget', 'Budget Management', {
                        'title': 'Budget Management',
                        'items': [
                            ('purch_budg', 'Purchasing Budget',
                             'finance/Budget_mgmt.py'),
                            ('budg_act', 'Budget vs. Actual',
                             'finance/Budget_mgmt.py'),
                            ('spend_analy', 'Spending Analysis',
                             'finance/Budget_mgmt.py'),
                            ('budg_rpts', 'Budget Reports', 'finance/Budget_mgmt.py'),
                        ],
                    }),
                    ('vendor_mgmt', 'Vendor Management', {
                        'title': 'Vendor Management',
                        'items': [
                            ('vend_list', 'Vendor List',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('vend_eval', 'Vendor Evaluation',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('vend_perf', 'Vendor Performance',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('appr_vend', 'Approved Vendors',
                             'purchasing/Purchasing_Mgr_menu.py'),
                        ],
                    }),
                    ('purch_rpts', 'Purchasing Reports', {
                        'title': 'Purchasing Reports',
                        'items': [
                            ('spend_rpt', 'Spending Report',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('vend_rpt', 'Vendor Report',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('cat_analy', 'Category Analysis',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('month_sum', 'Monthly Summary',
                             'purchasing/Purchasing_Mgr_menu.py'),
                        ],
                    }),
                    ('contracts', 'Contract Management', {
                        'title': 'Contract Management',
                        'items': [
                            ('act_cont', 'Active Contracts',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('pend_renew', 'Pending Renewals',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('cont_arch', 'Contract Archive',
                             'purchasing/Purchasing_Mgr_menu.py'),
                            ('cont_rpts', 'Contract Reports',
                             'purchasing/Purchasing_Mgr_menu.py'),
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
                             'quality/QA_Mgr_menu.py'),
                            ('act_audits', 'Active Audits', 'quality/QA_Mgr_menu.py'),
                            ('findings', 'Audit Findings', 'quality/QA_Mgr_menu.py'),
                            ('corr_act', 'Corrective Actions',
                             'quality/QA_Mgr_menu.py'),
                        ],
                    }),
                    ('compliance', 'Compliance', {
                        'title': 'Compliance',
                        'items': [
                            ('comp_dash', 'Compliance Dashboard',
                             'quality/QA_Mgr_menu.py'),
                            ('reg_req', 'Regulatory Requirements',
                             'quality/QA_Mgr_menu.py'),
                            ('comp_rpts', 'Compliance Reports',
                             'quality/QA_Mgr_menu.py'),
                            ('non_comp', 'Non-Compliance Issues',
                             'quality/QA_Mgr_menu.py'),
                        ],
                    }),
                    ('corr_action', 'Corrective Actions', {
                        'title': 'Corrective Actions',
                        'items': [
                            ('open_cars', 'Open CARs', 'quality/QA_Mgr_menu.py'),
                            ('inprog_cars', 'In Progress', 'quality/QA_Mgr_menu.py'),
                            ('closed_cars', 'Closed CARs', 'quality/QA_Mgr_menu.py'),
                            ('car_rpts', 'CAR Reports', 'quality/QA_Mgr_menu.py'),
                        ],
                    }),
                    ('qa_reports', 'QA Reports', {
                        'title': 'QA Reports',
                        'items': [
                            ('daily_qa', 'Daily QA Report', 'quality/QA_Mgr_menu.py'),
                            ('week_sum', 'Weekly Summary', 'quality/QA_Mgr_menu.py'),
                            ('month_rpt', 'Monthly Report', 'quality/QA_Mgr_menu.py'),
                            ('kpi_dash', 'KPI Dashboard', 'quality/QA_Mgr_menu.py'),
                        ],
                    }),
                    ('supp_qual', 'Supplier Quality', {
                        'title': 'Supplier Quality',
                        'items': [
                            ('supp_score', 'Supplier Scorecards',
                             'quality/QA_Mgr_menu.py'),
                            ('inc_insp', 'Incoming Inspection',
                             'quality/QA_Mgr_menu.py'),
                            ('sampling_plans', 'Sampling Plans',
                             'quality/QA_Mgr_menu.py'),
                            ('supp_audit', 'Supplier Audits',
                             'quality/QA_Mgr_menu.py'),
                            ('supp_rpts', 'Supplier Reports',
                             'quality/QA_Mgr_menu.py'),
                        ],
                    }),
                    ('cust_comp', 'Customer Complaints', {
                        'title': 'Customer Complaints',
                        'items': [
                            ('new_comp', 'New Complaint', 'quality/QA_Mgr_menu.py'),
                            ('open_comp', 'Open Complaints', 'quality/QA_Mgr_menu.py'),
                            ('res_track', 'Resolution Tracking',
                             'quality/QA_Mgr_menu.py'),
                            ('comp_rpts', 'Complaint Reports',
                             'quality/QA_Mgr_menu.py'),
                        ],
                    }),
                    ('doc_control', 'Document Control', {
                        'title': 'Document Control',
                        'items': [
                            ('doc_lib', 'Document Library', 'quality/QA_Mgr_menu.py'),
                            ('new_doc', 'New Document', 'quality/QA_Mgr_menu.py'),
                            ('doc_review', 'Document Review',
                             'quality/QA_Mgr_menu.py'),
                            ('rev_hist', 'Revision History', 'quality/QA_Mgr_menu.py'),
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
                            ('set_tgt', 'Set Targets', 'sales/Sales_mgr_menu.py'),
                            ('tgt_act', 'Target vs. Actual',
                             'sales/Sales_mgr_menu.py'),
                            ('tgt_rep', 'Target by Rep', 'sales/Sales_mgr_menu.py'),
                            ('tgt_rpts', 'Target Reports',
                             'sales/Sales_mgr_menu.py'),
                        ],
                    }),
                    ('territory', 'Territory Management', {
                        'title': 'Territory Management',
                        'items': [
                            ('terr_map', 'Territory Map', 'sales/Sales_mgr_menu.py'),
                            ('terr_assign', 'Territory Assignments',
                             'sales/Sales_mgr_menu.py'),
                            ('terr_perf', 'Territory Performance',
                             'sales/Sales_mgr_menu.py'),
                            ('terr_rpts', 'Territory Reports',
                             'sales/Sales_mgr_menu.py'),
                        ],
                    }),
                    ('commission', 'Commission Tracking', {
                        'title': 'Commission Tracking',
                        'items': [
                            ('comm_calc', 'Commission Calculator',
                             'sales/Sales_mgr_menu.py'),
                            ('comm_rpts', 'Commission Reports',
                             'sales/Sales_mgr_menu.py'),
                            ('pay_hist', 'Payment History',
                             'sales/Sales_mgr_menu.py'),
                            ('comm_plans', 'Commission Plans',
                             'sales/Sales_mgr_menu.py'),
                        ],
                    }),
                    ('staff_perf', 'Staff Performance', {
                        'title': 'Staff Performance',
                        'items': [
                            ('perf_dash', 'Performance Dashboard',
                             'sales/Sales_mgr_menu.py'),
                            ('rep_rank', 'Rep Rankings', 'sales/Sales_mgr_menu.py'),
                            ('perf_revs', 'Performance Reviews',
                             'sales/Sales_mgr_menu.py'),
                            ('coaching', 'Coaching Notes',
                             'sales/Sales_mgr_menu.py'),
                        ],
                    }),
                ],
            }),
            ('sales', 'Sales Menu', _SALES_MENU),
            ('demand_forecast', 'AI Demand Forecast', 'sales/Sales_mgr_menu.py'),
        ],
    },
    'budget_management': {
        'title': 'Budget Management',
        'items': [
            ('budget_mgr', 'Budget Manager', {
                'title': 'Budget Manager',
                'items': [
                    ('bud_overview', 'Budgets', 'finance/Budget_mgr_menu.py'),
                    ('bud_detail_mgr', 'Budget Detail', 'finance/Budget_mgr_menu.py'),
                    ('bva_mgr', 'Budget vs. Actual', 'finance/Budget_mgr_menu.py'),
                    ('variance_mgr', 'Variance Report', 'finance/Budget_mgr_menu.py'),
                    ('dept_summary', 'Department Summaries',
                     'finance/Budget_mgr_menu.py'),
                    ('approval_wf', 'Approval Workflow', 'finance/Budget_mgr_menu.py'),
                ],
            }),
            ('budgets', 'Budgets', 'finance/Budget_mgmt.py'),
            ('bud_detail', 'Budget Detail', 'finance/Budget_mgmt.py'),
            ('bva', 'Budget vs. Actual', 'finance/Budget_mgmt.py'),
            ('variance', 'Variance Report', 'finance/Budget_mgmt.py'),
        ],
    },
    'finance': {
        'title': 'Finance Main Menu',
        'items': [
            ('fin_mgr', 'Finance Manager', {
                'title': 'Finance Manager',
                'items': [
                    ('fin_plan', 'Financial Planning', 'finance/Finance_mgr_menu.py'),
                    ('fin_forecast', 'Budget & Forecasting',
                     'finance/Finance_mgr_menu.py'),
                    ('treasury_mgmt', 'Treasury Management',
                     'finance/Finance_mgr_menu.py'),
                    ('invest_mgmt', 'Investment Management',
                     'finance/Finance_mgr_menu.py'),
                    ('fin_rpts_mgr', 'Financial Reports',
                     'finance/Finance_mgr_menu.py'),
                ],
            }),
            ('fin_analysis', 'Financial Analysis', 'finance/Finance_Main_menu.py'),
            ('fin_reporting', 'Financial Reporting', 'finance/Finance_Main_menu.py'),
            ('treasury_ops', 'Treasury Operations', 'finance/Finance_Main_menu.py'),
            ('capital_mgmt', 'Capital Management', 'finance/Finance_Main_menu.py'),
            ('tax_planning', 'Tax Planning', 'finance/Finance_Main_menu.py'),
        ],
    },
    'legal': {
        'title': 'Legal Main Menu',
        'items': [
            ('legal_mgr', 'Legal Manager', {
                'title': 'Legal Manager',
                'items': [
                    ('contracts_mgmt', 'Contract Management',
                     'legal/Legal_mgr_menu.py'),
                    ('litigation_mgmt', 'Litigation Management',
                     'legal/Legal_mgr_menu.py'),
                    ('compliance_mgmt', 'Compliance Management',
                     'legal/Legal_mgr_menu.py'),
                    ('corp_gov', 'Corporate Governance', 'legal/Legal_mgr_menu.py'),
                ],
            }),
            ('contracts', 'Contracts', 'legal/Legal_Main_menu.py'),
            ('compliance', 'Compliance', 'legal/Legal_Main_menu.py'),
            ('litigation', 'Litigation', 'legal/Legal_Main_menu.py'),
            ('ip_mgmt', 'Intellectual Property', 'legal/Legal_Main_menu.py'),
            ('emp_law', 'Employment Law', 'legal/Legal_Main_menu.py'),
        ],
    },
    'risk_management': {
        'title': 'Risk Management Main Menu',
        'items': [
            ('risk_mgr', 'Risk Manager', {
                'title': 'Risk Manager',
                'items': [
                    ('risk_register_mgr', 'Risk Register', 'legal/Risk_mgr_menu.py'),
                    ('kri', 'Key Risk Indicators', 'legal/Risk_mgr_menu.py'),
                    ('biz_continuity', 'Business Continuity',
                     'legal/Risk_mgr_menu.py'),
                    ('audit_compliance', 'Audit & Compliance',
                     'legal/Risk_mgr_menu.py'),
                ],
            }),
            ('risk_assess', 'Risk Assessment', 'legal/Risk_mgmt_Main_menu.py'),
            ('risk_register', 'Risk Register', 'legal/Risk_mgmt_Main_menu.py'),
            ('insurance', 'Insurance Management', 'legal/Risk_mgmt_Main_menu.py'),
            ('biz_cont', 'Business Continuity', 'legal/Risk_mgmt_Main_menu.py'),
            ('comp_audit', 'Compliance & Audit', 'legal/Risk_mgmt_Main_menu.py'),
        ],
    },
    'reports': {
        'title': 'Reports',
        'items': [
            ('rpt_dashboard', 'Dashboard', 'reports/Reports_Main_menu.py'),
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
