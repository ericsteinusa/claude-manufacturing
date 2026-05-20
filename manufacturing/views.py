import os
import sys
import subprocess
import sqlite3
from django.shortcuts import render, redirect


# Each item: (key, label, target)
# target is a script filename (str = leaf) or a dict (sub-menu node).

_TIME_CLOCK_MENU = {
    'title': 'Time Clock Menu',
    'items': [
        ('clock_in_out',   'Clock In/Out',        {
            'title': 'Clock In/Out',
            'items': [
                ('punch_in',   'Record Clock In',    {'title': 'Record Clock In',    'items': []}),
                ('punch_out',  'Record Clock Out',   {'title': 'Record Clock Out',   'items': []}),
                ('cur_status', 'Current Status',     {'title': 'Current Status',     'items': []}),
            ],
        }),
        ('view_hours',     'View Hours',           {
            'title': 'View Hours',
            'items': [
                ('today_hrs',  "Today's Hours",      {'title': "Today's Hours",      'items': []}),
                ('week_hrs',   'Weekly Hours',        {'title': 'Weekly Hours',       'items': []}),
                ('month_hrs',  'Monthly Hours',       {'title': 'Monthly Hours',      'items': []}),
                ('period_hrs', 'Pay Period Hours',    {'title': 'Pay Period Hours',   'items': []}),
            ],
        }),
        ('time_off',       'Time Off Requests',    {
            'title': 'Time Off Requests',
            'items': [
                ('submit_req', 'Submit Request',      {'title': 'Submit Request',     'items': []}),
                ('pend_req',   'Pending Requests',    {'title': 'Pending Requests',   'items': []}),
                ('appr_req',   'Approved Requests',   {'title': 'Approved Requests',  'items': []}),
                ('req_hist',   'Request History',     {'title': 'Request History',    'items': []}),
            ],
        }),
        ('schedules',      'Schedules',            {
            'title': 'Schedules',
            'items': [
                ('my_sched',   'My Schedule',         {'title': 'My Schedule',        'items': []}),
                ('upcoming',   'Upcoming Shifts',     {'title': 'Upcoming Shifts',    'items': []}),
                ('sched_cal',  'Schedule Calendar',   {'title': 'Schedule Calendar',  'items': []}),
                ('swap_req',   'Swap Requests',       {'title': 'Swap Requests',      'items': []}),
            ],
        }),
        ('ot_reports',     'Overtime Reports',     {
            'title': 'Overtime Reports',
            'items': [
                ('cur_ot',     'Current Period OT',   {'title': 'Current Period OT',  'items': []}),
                ('hist_ot',    'Historical OT',       {'title': 'Historical OT',      'items': []}),
                ('ot_by_emp',  'OT by Employee',      {'title': 'OT by Employee',     'items': []}),
                ('ot_appr',    'OT Approval',         {'title': 'OT Approval',        'items': []}),
            ],
        }),
        ('attend_reports', 'Attendance Reports',   {
            'title': 'Attendance Reports',
            'items': [
                ('daily_att',  'Daily Attendance',    {'title': 'Daily Attendance',   'items': []}),
                ('month_sum',  'Monthly Summary',     {'title': 'Monthly Summary',    'items': []}),
                ('tard_rpt',   'Tardiness Report',    {'title': 'Tardiness Report',   'items': []}),
                ('abs_rpt',    'Absence Report',      {'title': 'Absence Report',     'items': []}),
            ],
        }),
        ('shift_mgmt',     'Shift Management',     {
            'title': 'Shift Management',
            'items': [
                ('view_shfts', 'View Shifts',          {'title': 'View Shifts',        'items': []}),
                ('assign_emp', 'Assign Employees',     {'title': 'Assign Employees',   'items': []}),
                ('shft_tmpl',  'Shift Templates',      {'title': 'Shift Templates',    'items': []}),
                ('swap_mgmt',  'Swap Management',      {'title': 'Swap Management',    'items': []}),
            ],
        }),
    ],
}

_MAINT_MENU = {
    'title': 'Maintenance Menu',
    'items': [
        ('work_orders',    'Work Orders',           {
            'title': 'Work Orders',
            'items': [
                ('create_wo',  'Create Work Order',   {'title': 'Create Work Order',  'items': []}),
                ('open_wo',    'Open Work Orders',    {'title': 'Open Work Orders',   'items': []}),
                ('inprog_wo',  'In Progress',         {'title': 'In Progress',        'items': []}),
                ('comp_wo',    'Completed',           {'title': 'Completed',          'items': []}),
            ],
        }),
        ('maint_schedule', 'Maintenance Schedule',  {
            'title': 'Maintenance Schedule',
            'items': [
                ('daily_sched','Daily Schedule',      {'title': 'Daily Schedule',     'items': []}),
                ('week_sched', 'Weekly Schedule',     {'title': 'Weekly Schedule',    'items': []}),
                ('month_sched','Monthly Schedule',    {'title': 'Monthly Schedule',   'items': []}),
                ('annual_plan','Annual Plan',         {'title': 'Annual Plan',        'items': []}),
            ],
        }),
        ('equip_maint',    'Equipment Maintenance', {
            'title': 'Equipment Maintenance',
            'items': [
                ('equip_list', 'Equipment List',      {'title': 'Equipment List',     'items': []}),
                ('maint_hist', 'Maintenance History', {'title': 'Maintenance History','items': []}),
                ('svc_records','Service Records',     {'title': 'Service Records',    'items': []}),
                ('equip_stat', 'Equipment Status',    {'title': 'Equipment Status',   'items': []}),
            ],
        }),
        ('parts_inv',      'Parts Inventory',       {
            'title': 'Parts Inventory',
            'items': [
                ('view_inv',   'View Inventory',      {'title': 'View Inventory',     'items': []}),
                ('parts_req',  'Parts Request',       {'title': 'Parts Request',      'items': []}),
                ('reorder',    'Reorder List',        {'title': 'Reorder List',       'items': []}),
                ('parts_hist', 'Parts History',       {'title': 'Parts History',      'items': []}),
            ],
        }),
        ('maint_reports',  'Maintenance Reports',   {
            'title': 'Maintenance Reports',
            'items': [
                ('daily_rpt',  'Daily Report',        {'title': 'Daily Report',       'items': []}),
                ('week_rpt',   'Weekly Report',       {'title': 'Weekly Report',      'items': []}),
                ('cost_analy', 'Cost Analysis',       {'title': 'Cost Analysis',      'items': []}),
                ('down_rpt',   'Downtime Report',     {'title': 'Downtime Report',    'items': []}),
            ],
        }),
        ('safety_insp',    'Safety Inspections',    {
            'title': 'Safety Inspections',
            'items': [
                ('sched_insp', 'Schedule Inspection', {'title': 'Schedule Inspection','items': []}),
                ('insp_chk',   'Inspection Checklist',{'title': 'Inspection Checklist','items': []}),
                ('insp_res',   'Inspection Results',  {'title': 'Inspection Results', 'items': []}),
                ('corr_act',   'Corrective Actions',  {'title': 'Corrective Actions', 'items': []}),
            ],
        }),
        ('prev_maint',     'Preventive Maintenance', {
            'title': 'Preventive Maintenance',
            'items': [
                ('pm_sched',   'PM Schedule',         {'title': 'PM Schedule',        'items': []}),
                ('pm_chk',     'PM Checklists',       {'title': 'PM Checklists',      'items': []}),
                ('pm_hist',    'PM History',          {'title': 'PM History',         'items': []}),
                ('pm_rpts',    'PM Reports',          {'title': 'PM Reports',         'items': []}),
            ],
        }),
    ],
}

_MKT_MENU = {
    'title': 'Marketing Menu',
    'items': [
        ('campaigns',    'Campaigns',         {
            'title': 'Campaigns',
            'items': [
                ('act_camp',   'Active Campaigns',    {'title': 'Active Campaigns',   'items': []}),
                ('new_camp',   'Create Campaign',     {'title': 'Create Campaign',    'items': []}),
                ('camp_cal',   'Campaign Calendar',   {'title': 'Campaign Calendar',  'items': []}),
                ('camp_res',   'Campaign Results',    {'title': 'Campaign Results',   'items': []}),
            ],
        }),
        ('mkt_research', 'Market Research',   {
            'title': 'Market Research',
            'items': [
                ('res_proj',   'Research Projects',   {'title': 'Research Projects',  'items': []}),
                ('comp_analy', 'Competitor Analysis', {'title': 'Competitor Analysis','items': []}),
                ('surv_mgmt',  'Survey Management',   {'title': 'Survey Management',  'items': []}),
                ('mkt_trends', 'Market Trends',       {'title': 'Market Trends',      'items': []}),
            ],
        }),
        ('advertising',  'Advertising',       {
            'title': 'Advertising',
            'items': [
                ('ad_mgmt',    'Ad Management',       {'title': 'Ad Management',      'items': []}),
                ('ad_budget',  'Ad Budget',           {'title': 'Ad Budget',          'items': []}),
                ('ad_perf',    'Ad Performance',      {'title': 'Ad Performance',     'items': []}),
                ('ad_cal',     'Ad Calendar',         {'title': 'Ad Calendar',        'items': []}),
            ],
        }),
        ('analytics',    'Analytics',         {
            'title': 'Analytics',
            'items': [
                ('web_analy',  'Website Analytics',   {'title': 'Website Analytics',  'items': []}),
                ('camp_analy', 'Campaign Analytics',  {'title': 'Campaign Analytics', 'items': []}),
                ('sales_analy','Sales Analytics',     {'title': 'Sales Analytics',    'items': []}),
                ('cust_rpts',  'Custom Reports',      {'title': 'Custom Reports',     'items': []}),
            ],
        }),
        ('content_mgmt', 'Content Management', {
            'title': 'Content Management',
            'items': [
                ('cont_cal',   'Content Calendar',    {'title': 'Content Calendar',   'items': []}),
                ('blog',       'Blog Posts',          {'title': 'Blog Posts',         'items': []}),
                ('mkt_mat',    'Marketing Materials', {'title': 'Marketing Materials','items': []}),
                ('cont_arch',  'Content Archive',     {'title': 'Content Archive',    'items': []}),
            ],
        }),
        ('social_media', 'Social Media',      {
            'title': 'Social Media',
            'items': [
                ('post_mgmt',  'Post Management',     {'title': 'Post Management',    'items': []}),
                ('social_cal', 'Social Calendar',     {'title': 'Social Calendar',    'items': []}),
                ('eng_rpts',   'Engagement Reports',  {'title': 'Engagement Reports', 'items': []}),
                ('acct_mgmt',  'Account Management',  {'title': 'Account Management', 'items': []}),
            ],
        }),
        ('email_mkt',    'Email Marketing',   {
            'title': 'Email Marketing',
            'items': [
                ('email_camp', 'Email Campaigns',     {'title': 'Email Campaigns',    'items': []}),
                ('sub_lists',  'Subscriber Lists',    {'title': 'Subscriber Lists',   'items': []}),
                ('email_tmpl', 'Email Templates',     {'title': 'Email Templates',    'items': []}),
                ('email_analy','Email Analytics',     {'title': 'Email Analytics',    'items': []}),
            ],
        }),
    ],
}

_SALES_MENU = {
    'title': 'Sales Menu',
    'items': [
        ('sales_orders',  'Sales Orders',          {
            'title': 'Sales Orders',
            'items': [
                ('new_order',  'New Order',           {'title': 'New Order',          'items': []}),
                ('open_orders','Open Orders',         {'title': 'Open Orders',        'items': []}),
                ('order_hist', 'Order History',       {'title': 'Order History',      'items': []}),
                ('order_stat', 'Order Status',        {'title': 'Order Status',       'items': []}),
            ],
        }),
        ('cust_accounts', 'Customer Accounts',     {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list',  'Account List',        {'title': 'Account List',       'items': []}),
                ('new_acct',   'New Account',         {'title': 'New Account',        'items': []}),
                ('acct_det',   'Account Details',     {'title': 'Account Details',    'items': []}),
                ('acct_hist',  'Account History',     {'title': 'Account History',    'items': []}),
            ],
        }),
        ('sales_reports', 'Sales Reports',         {
            'title': 'Sales Reports',
            'items': [
                ('daily_sales','Daily Sales',         {'title': 'Daily Sales',        'items': []}),
                ('month_sales','Monthly Sales',       {'title': 'Monthly Sales',      'items': []}),
                ('annual_rpt', 'Annual Report',       {'title': 'Annual Report',      'items': []}),
                ('by_rep',     'Sales by Rep',        {'title': 'Sales by Rep',       'items': []}),
            ],
        }),
        ('quotes',        'Quotes',                {
            'title': 'Quotes',
            'items': [
                ('new_quote',  'Create Quote',        {'title': 'Create Quote',       'items': []}),
                ('act_quotes', 'Active Quotes',       {'title': 'Active Quotes',      'items': []}),
                ('quote_hist', 'Quote History',       {'title': 'Quote History',      'items': []}),
                ('conv_order', 'Convert to Order',    {'title': 'Convert to Order',   'items': []}),
            ],
        }),
        ('leads',         'Leads & Opportunities', {
            'title': 'Leads & Opportunities',
            'items': [
                ('new_lead',   'New Lead',            {'title': 'New Lead',           'items': []}),
                ('act_leads',  'Active Leads',        {'title': 'Active Leads',       'items': []}),
                ('opp_pipe',   'Opportunities Pipeline',{'title': 'Opportunities Pipeline','items': []}),
                ('lead_rpts',  'Lead Reports',        {'title': 'Lead Reports',       'items': []}),
            ],
        }),
        ('contracts',     'Contracts',             {
            'title': 'Contracts',
            'items': [
                ('act_cont',   'Active Contracts',    {'title': 'Active Contracts',   'items': []}),
                ('new_cont',   'Create Contract',     {'title': 'Create Contract',    'items': []}),
                ('cont_renew', 'Contract Renewals',   {'title': 'Contract Renewals',  'items': []}),
                ('cont_arch',  'Contract Archive',    {'title': 'Contract Archive',   'items': []}),
            ],
        }),
        ('forecasting',   'Sales Forecasting',     {
            'title': 'Sales Forecasting',
            'items': [
                ('cur_fore',   'Current Forecast',    {'title': 'Current Forecast',   'items': []}),
                ('fore_rep',   'Forecast by Rep',     {'title': 'Forecast by Rep',    'items': []}),
                ('fore_prod',  'Forecast by Product', {'title': 'Forecast by Product','items': []}),
                ('fore_rpts',  'Forecast Reports',    {'title': 'Forecast Reports',   'items': []}),
            ],
        }),
    ],
}

_PROD_MENU = {
    'title': 'Production Menu',
    'items': [
        ('work_orders',   'Work Orders',          {
            'title': 'Work Orders',
            'items': [
                ('create_wo',  'Create Work Order',   {'title': 'Create Work Order',  'items': []}),
                ('open_wo',    'Open Work Orders',    {'title': 'Open Work Orders',   'items': []}),
                ('inprog_wo',  'In Progress',         {'title': 'In Progress',        'items': []}),
                ('comp_wo',    'Completed',           {'title': 'Completed',          'items': []}),
            ],
        }),
        ('prod_schedule', 'Production Schedule',  {
            'title': 'Production Schedule',
            'items': [
                ('daily_sched','Daily Schedule',      {'title': 'Daily Schedule',     'items': []}),
                ('week_sched', 'Weekly Schedule',     {'title': 'Weekly Schedule',    'items': []}),
                ('month_sched','Monthly Schedule',    {'title': 'Monthly Schedule',   'items': []}),
                ('sched_cal',  'Schedule Calendar',   {'title': 'Schedule Calendar',  'items': []}),
            ],
        }),
        ('inventory',     'Inventory',            {
            'title': 'Inventory',
            'items': [
                ('raw_mat',    'Raw Materials',        {'title': 'Raw Materials',      'items': []}),
                ('fin_goods',  'Finished Goods',      {'title': 'Finished Goods',     'items': []}),
                ('wip_inv',    'WIP Inventory',       {'title': 'WIP Inventory',      'items': []}),
                ('inv_rpts',   'Inventory Reports',   {'title': 'Inventory Reports',  'items': []}),
            ],
        }),
        ('equip_status',  'Equipment Status',     {
            'title': 'Equipment Status',
            'items': [
                ('equip_list', 'Equipment List',      {'title': 'Equipment List',     'items': []}),
                ('stat_dash',  'Status Dashboard',    {'title': 'Status Dashboard',   'items': []}),
                ('down_log',   'Downtime Log',        {'title': 'Downtime Log',       'items': []}),
                ('maint_req',  'Maintenance Requests',{'title': 'Maintenance Requests','items': []}),
            ],
        }),
        ('quality_ctrl',  'Quality Control',      {
            'title': 'Quality Control',
            'items': [
                ('insp_res',   'Inspection Results',  {'title': 'Inspection Results', 'items': []}),
                ('non_conf',   'Non-Conformances',    {'title': 'Non-Conformances',   'items': []}),
                ('qc_rpts',    'QC Reports',          {'title': 'QC Reports',         'items': []}),
                ('rej_analy',  'Reject Analysis',     {'title': 'Reject Analysis',    'items': []}),
            ],
        }),
        ('prod_reports',  'Production Reports',   {
            'title': 'Production Reports',
            'items': [
                ('daily_prod', 'Daily Production',    {'title': 'Daily Production',   'items': []}),
                ('week_sum',   'Weekly Summary',      {'title': 'Weekly Summary',     'items': []}),
                ('eff_rpt',    'Efficiency Report',   {'title': 'Efficiency Report',  'items': []}),
                ('scrap_rpt',  'Scrap Report',        {'title': 'Scrap Report',       'items': []}),
            ],
        }),
        ('labor_tracking','Labor Tracking',       {
            'title': 'Labor Tracking',
            'items': [
                ('cur_labor',  'Current Labor',       {'title': 'Current Labor',      'items': []}),
                ('labor_shft', 'Labor by Shift',      {'title': 'Labor by Shift',     'items': []}),
                ('labor_job',  'Labor by Job',        {'title': 'Labor by Job',       'items': []}),
                ('labor_rpts', 'Labor Reports',       {'title': 'Labor Reports',      'items': []}),
            ],
        }),
    ],
}

_SHIP_MENU = {
    'title': 'Shipping Department',
    'items': [
        ('ship_orders',   'Shipment Orders',    {
            'title': 'Shipment Orders',
            'items': [
                ('new_ship',   'New Shipment',        {'title': 'New Shipment',       'items': []}),
                ('pend_ship',  'Pending Shipments',   {'title': 'Pending Shipments',  'items': []}),
                ('shipped',    'Shipped Orders',      {'title': 'Shipped Orders',     'items': []}),
                ('deliv_conf', 'Delivery Confirmation',{'title': 'Delivery Confirmation','items': []}),
            ],
        }),
        ('ship_schedule', 'Shipping Schedule',  {
            'title': 'Shipping Schedule',
            'items': [
                ('today_sched',"Today's Schedule",    {'title': "Today's Schedule",   'items': []}),
                ('week_sched', 'Weekly Schedule',     {'title': 'Weekly Schedule',    'items': []}),
                ('sched_cal',  'Schedule Calendar',   {'title': 'Schedule Calendar',  'items': []}),
                ('rush_orders','Rush Orders',         {'title': 'Rush Orders',        'items': []}),
            ],
        }),
        ('receiving',     'Receiving',          {
            'title': 'Receiving',
            'items': [
                ('inbound',    'Inbound Shipments',   {'title': 'Inbound Shipments',  'items': []}),
                ('recv_items', 'Receive Items',       {'title': 'Receive Items',      'items': []}),
                ('recv_rpts',  'Receiving Reports',   {'title': 'Receiving Reports',  'items': []}),
                ('disc_rpts',  'Discrepancy Reports', {'title': 'Discrepancy Reports','items': []}),
            ],
        }),
        ('carrier_mgmt',  'Carrier Management', {
            'title': 'Carrier Management',
            'items': [
                ('carr_list',  'Carrier List',        {'title': 'Carrier List',       'items': []}),
                ('carr_rates', 'Carrier Rates',       {'title': 'Carrier Rates',      'items': []}),
                ('perf_rpts',  'Performance Reports', {'title': 'Performance Reports','items': []}),
                ('carr_cont',  'Carrier Contracts',   {'title': 'Carrier Contracts',  'items': []}),
            ],
        }),
        ('tracking',      'Tracking',           {
            'title': 'Tracking',
            'items': [
                ('track_ship', 'Track Shipment',      {'title': 'Track Shipment',     'items': []}),
                ('track_dash', 'Tracking Dashboard',  {'title': 'Tracking Dashboard', 'items': []}),
                ('deliv_stat', 'Delivery Status',     {'title': 'Delivery Status',    'items': []}),
                ('exc_rpts',   'Exception Reports',   {'title': 'Exception Reports',  'items': []}),
            ],
        }),
        ('ship_reports',  'Shipping Reports',   {
            'title': 'Shipping Reports',
            'items': [
                ('daily_rpt',  'Daily Report',        {'title': 'Daily Report',       'items': []}),
                ('week_sum',   'Weekly Summary',      {'title': 'Weekly Summary',     'items': []}),
                ('cost_analy', 'Cost Analysis',       {'title': 'Cost Analysis',      'items': []}),
                ('perf_rpt',   'Performance Report',  {'title': 'Performance Report', 'items': []}),
            ],
        }),
        ('returns_proc',  'Returns Processing', {
            'title': 'Returns Processing',
            'items': [
                ('new_return', 'New Return',          {'title': 'New Return',         'items': []}),
                ('pend_ret',   'Pending Returns',     {'title': 'Pending Returns',    'items': []}),
                ('ret_hist',   'Return History',      {'title': 'Return History',     'items': []}),
                ('ret_rpts',   'Return Reports',      {'title': 'Return Reports',     'items': []}),
            ],
        }),
    ],
}

_QA_LAB_MENU = {
    'title': 'QA Laboratory Menu',
    'items': [
        ('test_requests',  'Test Requests',      {
            'title': 'Test Requests',
            'items': [
                ('new_req',    'New Request',         {'title': 'New Request',        'items': []}),
                ('pend_req',   'Pending Requests',    {'title': 'Pending Requests',   'items': []}),
                ('inprog_req', 'In Progress',         {'title': 'In Progress',        'items': []}),
                ('comp_tests', 'Completed Tests',     {'title': 'Completed Tests',    'items': []}),
            ],
        }),
        ('lab_results',    'Lab Results',        {
            'title': 'Lab Results',
            'items': [
                ('recent_res', 'Recent Results',      {'title': 'Recent Results',     'items': []}),
                ('search_res', 'Search Results',      {'title': 'Search Results',     'items': []}),
                ('failed',     'Failed Tests',        {'title': 'Failed Tests',       'items': []}),
                ('res_rpts',   'Result Reports',      {'title': 'Result Reports',     'items': []}),
            ],
        }),
        ('insp_reports',   'Inspection Reports', {
            'title': 'Inspection Reports',
            'items': [
                ('create_rpt', 'Create Report',       {'title': 'Create Report',      'items': []}),
                ('pend_rpts',  'Pending Reports',     {'title': 'Pending Reports',    'items': []}),
                ('rpt_arch',   'Report Archive',      {'title': 'Report Archive',     'items': []}),
                ('rpt_sum',    'Report Summary',      {'title': 'Report Summary',     'items': []}),
            ],
        }),
        ('non_conformance','Non-Conformance',    {
            'title': 'Non-Conformance',
            'items': [
                ('new_ncr',    'New NCR',             {'title': 'New NCR',            'items': []}),
                ('open_ncrs',  'Open NCRs',           {'title': 'Open NCRs',          'items': []}),
                ('ncr_hist',   'NCR History',         {'title': 'NCR History',        'items': []}),
                ('ncr_rpts',   'NCR Reports',         {'title': 'NCR Reports',        'items': []}),
            ],
        }),
        ('calibration',    'Calibration',        {
            'title': 'Calibration',
            'items': [
                ('cal_sched',  'Calibration Schedule',{'title': 'Calibration Schedule','items': []}),
                ('cal_records','Calibration Records', {'title': 'Calibration Records','items': []}),
                ('overdue',    'Overdue Items',       {'title': 'Overdue Items',      'items': []}),
                ('cal_rpts',   'Calibration Reports', {'title': 'Calibration Reports','items': []}),
            ],
        }),
        ('sample_mgmt',    'Sample Management',  {
            'title': 'Sample Management',
            'items': [
                ('recv_sample','Receive Sample',      {'title': 'Receive Sample',     'items': []}),
                ('samp_track', 'Sample Tracking',     {'title': 'Sample Tracking',    'items': []}),
                ('samp_disp',  'Sample Disposal',     {'title': 'Sample Disposal',    'items': []}),
                ('samp_rpts',  'Sample Reports',      {'title': 'Sample Reports',     'items': []}),
            ],
        }),
        ('lab_reports',    'Lab Reports',        {
            'title': 'Lab Reports',
            'items': [
                ('daily_rpts', 'Daily Reports',       {'title': 'Daily Reports',      'items': []}),
                ('week_sum',   'Weekly Summary',      {'title': 'Weekly Summary',     'items': []}),
                ('month_rpt',  'Monthly Report',      {'title': 'Monthly Report',     'items': []}),
                ('cust_rpts',  'Custom Reports',      {'title': 'Custom Reports',     'items': []}),
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
        ('pers_crm',    'Personnel CRM',          'personnel_crm.py'),
        ('reg_form',    'Registration Form',      'registration_form.py'),
        ('upd_pass',    'Update Password',        'update_users.py'),
        ('disp_dept',   'Display Department',     'display_people_department.py'),
        ('dept_entry',  'Dept Entry',             'dept_entry.py'),
        ('dept_sub',    'Dept Sub Entry',         'dept_sub_entry.py'),
        ('time_clock',  'Time Clock',             _TIME_CLOCK_MENU),
        ('emp_records', 'Employee Records',       {
            'title': 'Employee Records',
            'items': [
                ('view_recs',  'View Records',        {'title': 'View Records',       'items': []}),
                ('new_emp',    'New Employee',        {'title': 'New Employee',       'items': []}),
                ('upd_rec',    'Update Record',       {'title': 'Update Record',      'items': []}),
                ('emp_hist',   'Employment History',  {'title': 'Employment History', 'items': []}),
            ],
        }),
        ('benefits',    'Benefits',               {
            'title': 'Benefits',
            'items': [
                ('ben_enroll', 'Benefits Enrollment', {'title': 'Benefits Enrollment','items': []}),
                ('ben_sum',    'Benefits Summary',    {'title': 'Benefits Summary',   'items': []}),
                ('cobra',      'COBRA Management',    {'title': 'COBRA Management',   'items': []}),
                ('ben_rpts',   'Benefits Reports',    {'title': 'Benefits Reports',   'items': []}),
            ],
        }),
        ('perf_review', 'Performance Reviews',    {
            'title': 'Performance Reviews',
            'items': [
                ('sched_rev',  'Schedule Review',     {'title': 'Schedule Review',    'items': []}),
                ('pend_revs',  'Pending Reviews',     {'title': 'Pending Reviews',    'items': []}),
                ('rev_hist',   'Review History',      {'title': 'Review History',     'items': []}),
                ('perf_rpts',  'Performance Reports', {'title': 'Performance Reports','items': []}),
            ],
        }),
        ('disc_records','Disciplinary Records',   {
            'title': 'Disciplinary Records',
            'items': [
                ('new_rec',    'New Record',          {'title': 'New Record',         'items': []}),
                ('view_recs',  'View Records',        {'title': 'View Records',       'items': []}),
                ('rec_hist',   'Record History',      {'title': 'Record History',     'items': []}),
                ('disc_rpts',  'Disciplinary Reports',{'title': 'Disciplinary Reports','items': []}),
            ],
        }),
        ('training',    'Training & Development', {
            'title': 'Training & Development',
            'items': [
                ('train_cal',  'Training Calendar',   {'title': 'Training Calendar',  'items': []}),
                ('train_recs', 'Training Records',    {'title': 'Training Records',   'items': []}),
                ('course_mgmt','Course Management',   {'title': 'Course Management',  'items': []}),
                ('cert_track', 'Certification Tracking',{'title': 'Certification Tracking','items': []}),
            ],
        }),
        ('onboarding',  'Onboarding',             {
            'title': 'Onboarding',
            'items': [
                ('hire_chk',   'New Hire Checklist',  {'title': 'New Hire Checklist', 'items': []}),
                ('onb_stat',   'Onboarding Status',   {'title': 'Onboarding Status',  'items': []}),
                ('doc_coll',   'Document Collection', {'title': 'Document Collection','items': []}),
                ('onb_rpts',   'Onboarding Reports',  {'title': 'Onboarding Reports', 'items': []}),
            ],
        }),
    ],
}

_CS_MENU = {
    'title': 'Customer Service Menu',
    'items': [
        ('cs_calls',      'Customer Service Calls', 'cs_calls.py'),
        ('cust_entry',    'Customer Entry Screen',  'customer_entry.py'),
        ('open_tickets',  'Open Tickets',           {
            'title': 'Open Tickets',
            'items': [
                ('all_tickets','View All Tickets',    {'title': 'View All Tickets',   'items': []}),
                ('my_tickets', 'My Tickets',          {'title': 'My Tickets',         'items': []}),
                ('hi_pri',     'High Priority',       {'title': 'High Priority',      'items': []}),
                ('tick_search','Ticket Search',       {'title': 'Ticket Search',      'items': []}),
            ],
        }),
        ('cust_accounts', 'Customer Accounts',      {
            'title': 'Customer Accounts',
            'items': [
                ('acct_list',  'Account List',        {'title': 'Account List',       'items': []}),
                ('new_acct',   'New Account',         {'title': 'New Account',        'items': []}),
                ('acct_det',   'Account Details',     {'title': 'Account Details',    'items': []}),
                ('acct_hist',  'Account History',     {'title': 'Account History',    'items': []}),
            ],
        }),
        ('returns',       'Returns & Refunds',      {
            'title': 'Returns & Refunds',
            'items': [
                ('new_return', 'New Return',          {'title': 'New Return',         'items': []}),
                ('pend_ret',   'Pending Returns',     {'title': 'Pending Returns',    'items': []}),
                ('refund_proc','Refund Processing',   {'title': 'Refund Processing',  'items': []}),
                ('ret_rpts',   'Returns Reports',     {'title': 'Returns Reports',    'items': []}),
            ],
        }),
        ('knowledge_base','Knowledge Base',         {
            'title': 'Knowledge Base',
            'items': [
                ('browse',     'Browse Articles',     {'title': 'Browse Articles',    'items': []}),
                ('create_art', 'Create Article',      {'title': 'Create Article',     'items': []}),
                ('art_mgmt',   'Article Management',  {'title': 'Article Management', 'items': []}),
                ('kb_search',  'Search Knowledge Base',{'title': 'Search Knowledge Base','items': []}),
            ],
        }),
        ('svc_reports',   'Service Reports',        {
            'title': 'Service Reports',
            'items': [
                ('daily_rpt',  'Daily Report',        {'title': 'Daily Report',       'items': []}),
                ('week_sum',   'Weekly Summary',      {'title': 'Weekly Summary',     'items': []}),
                ('res_rpts',   'Resolution Reports',  {'title': 'Resolution Reports', 'items': []}),
                ('csat_rpts',  'Customer Satisfaction',{'title': 'Customer Satisfaction','items': []}),
            ],
        }),
        ('surveys',       'Surveys & Feedback',     {
            'title': 'Surveys & Feedback',
            'items': [
                ('act_surv',   'Active Surveys',      {'title': 'Active Surveys',     'items': []}),
                ('new_surv',   'Create Survey',       {'title': 'Create Survey',      'items': []}),
                ('surv_res',   'Survey Results',      {'title': 'Survey Results',     'items': []}),
                ('feed_rpts',  'Feedback Reports',    {'title': 'Feedback Reports',   'items': []}),
            ],
        }),
    ],
}

_IT_TECH = {
    'title': 'IT Technician',
    'items': [
        ('it_calls',    'IT Support Calls',       'it_calls.py'),
        ('it_tasks',    'IT Tasks',               'IT_Tasks.py'),
        ('help_desk',   'Help Desk Tickets',      {
            'title': 'Help Desk Tickets',
            'items': [
                ('new_ticket', 'New Ticket',          {'title': 'New Ticket',         'items': []}),
                ('open_tick',  'Open Tickets',        {'title': 'Open Tickets',       'items': []}),
                ('my_tickets', 'My Assigned Tickets', {'title': 'My Assigned Tickets','items': []}),
                ('tick_hist',  'Ticket History',      {'title': 'Ticket History',     'items': []}),
            ],
        }),
        ('asset_mgmt',  'Asset Management',       {
            'title': 'Asset Management',
            'items': [
                ('asset_inv',  'Asset Inventory',     {'title': 'Asset Inventory',    'items': []}),
                ('new_asset',  'New Asset',           {'title': 'New Asset',          'items': []}),
                ('asset_hist', 'Asset History',       {'title': 'Asset History',      'items': []}),
                ('disposition','Disposition',         {'title': 'Disposition',        'items': []}),
            ],
        }),
        ('net_status',  'Network Status',         {
            'title': 'Network Status',
            'items': [
                ('net_dash',   'Network Dashboard',   {'title': 'Network Dashboard',  'items': []}),
                ('bw_monitor', 'Bandwidth Monitor',   {'title': 'Bandwidth Monitor',  'items': []}),
                ('net_map',    'Network Map',         {'title': 'Network Map',        'items': []}),
                ('inc_log',    'Incident Log',        {'title': 'Incident Log',       'items': []}),
            ],
        }),
        ('sw_install',  'Software Installations', {
            'title': 'Software Installations',
            'items': [
                ('pend_inst',  'Pending Installs',    {'title': 'Pending Installs',   'items': []}),
                ('sw_inv',     'Software Inventory',  {'title': 'Software Inventory', 'items': []}),
                ('lic_mgmt',   'License Management',  {'title': 'License Management', 'items': []}),
                ('inst_hist',  'Installation History',{'title': 'Installation History','items': []}),
            ],
        }),
        ('hw_repairs',  'Hardware Repairs',       {
            'title': 'Hardware Repairs',
            'items': [
                ('new_repair', 'New Repair Request',  {'title': 'New Repair Request', 'items': []}),
                ('inprog',     'In Progress',         {'title': 'In Progress',        'items': []}),
                ('comp_rep',   'Completed Repairs',   {'title': 'Completed Repairs',  'items': []}),
                ('rep_hist',   'Repair History',      {'title': 'Repair History',     'items': []}),
            ],
        }),
        ('user_accts',  'User Account Management', {
            'title': 'User Account Management',
            'items': [
                ('create_acct','Create Account',      {'title': 'Create Account',     'items': []}),
                ('reset_pw',   'Reset Password',      {'title': 'Reset Password',     'items': []}),
                ('acct_stat',  'Account Status',      {'title': 'Account Status',     'items': []}),
                ('acct_audit', 'Account Audit',       {'title': 'Account Audit',      'items': []}),
            ],
        }),
    ],
}

_PURCH_MENU = {
    'title': 'Purchasing Menu',
    'items': [
        ('prod_entry',    'Product Entry',       'product_entry_screen.py'),
        ('sup_entry',     'Supplier Entry',      'Supplier_entry.py'),
        ('purch_orders',  'Purchase Orders',     {
            'title': 'Purchase Orders',
            'items': [
                ('new_po',     'New PO',             {'title': 'New PO',             'items': []}),
                ('open_pos',   'Open POs',           {'title': 'Open POs',           'items': []}),
                ('po_status',  'PO Status',          {'title': 'PO Status',          'items': []}),
                ('po_hist',    'PO History',         {'title': 'PO History',         'items': []}),
            ],
        }),
        ('vendor_mgmt',   'Vendor Management',   {
            'title': 'Vendor Management',
            'items': [
                ('vend_list',  'Vendor List',        {'title': 'Vendor List',        'items': []}),
                ('new_vend',   'New Vendor',         {'title': 'New Vendor',         'items': []}),
                ('vend_perf',  'Vendor Performance', {'title': 'Vendor Performance', 'items': []}),
                ('vend_cont',  'Vendor Contracts',   {'title': 'Vendor Contracts',   'items': []}),
            ],
        }),
        ('purch_reports', 'Purchase Reports',    {
            'title': 'Purchase Reports',
            'items': [
                ('spend_sum',  'Spending Summary',   {'title': 'Spending Summary',   'items': []}),
                ('po_rpts',    'PO Reports',         {'title': 'PO Reports',         'items': []}),
                ('budg_act',   'Budget vs. Actual',  {'title': 'Budget vs. Actual',  'items': []}),
                ('cat_rpts',   'Category Reports',   {'title': 'Category Reports',   'items': []}),
            ],
        }),
        ('receiving',     'Receiving',           {
            'title': 'Receiving',
            'items': [
                ('pend_recv',  'Pending Receipts',   {'title': 'Pending Receipts',   'items': []}),
                ('recv_items', 'Receive Items',      {'title': 'Receive Items',      'items': []}),
                ('disc_rpts',  'Discrepancy Reports',{'title': 'Discrepancy Reports','items': []}),
                ('recv_hist',  'Receiving History',  {'title': 'Receiving History',  'items': []}),
            ],
        }),
        ('contracts',     'Contract Management', {
            'title': 'Contract Management',
            'items': [
                ('act_cont',   'Active Contracts',   {'title': 'Active Contracts',   'items': []}),
                ('new_cont',   'New Contract',       {'title': 'New Contract',       'items': []}),
                ('cont_renew', 'Contract Renewals',  {'title': 'Contract Renewals',  'items': []}),
                ('cont_arch',  'Contract Archive',   {'title': 'Contract Archive',   'items': []}),
            ],
        }),
        ('requisitions',  'Requisitions',        {
            'title': 'Requisitions',
            'items': [
                ('new_req',    'New Requisition',    {'title': 'New Requisition',    'items': []}),
                ('pend_appr',  'Pending Approval',   {'title': 'Pending Approval',   'items': []}),
                ('appr_reqs',  'Approved Requisitions',{'title': 'Approved Requisitions','items': []}),
                ('req_hist',   'Requisition History',{'title': 'Requisition History','items': []}),
            ],
        }),
    ],
}

MENU_TREE = {
    'accounting': {
        'title': 'Accounting Main Menu',
        'items': [
            ('acct_pay',    'Accounts Payable',    'Accounts_payable.py'),
            ('acct_mgr',    'Accounting Manager', {
                'title': 'Accounting Manager',
                'items': [
                    ('ap',          'Accounts Payable',    'Accounts_payable.py'),
                    ('rcv',         'Accounts Receivable', 'Accounts_receivable.py'),
                    ('credit',      'Credit Department',   'Credit_dept.py'),
                    ('pay',         'Payroll Department',  'Payroll_dept.py'),
                    ('fin_reports', 'Financial Reports',   {
                        'title': 'Financial Reports',
                        'items': [
                            ('inc_stmt',   'Income Statement',    'General_ledger.py'),
                            ('bal_sheet',  'Balance Sheet',       'General_ledger.py'),
                            ('cash_flow',  'Cash Flow',           'General_ledger.py'),
                            ('cust_rpts',  'Custom Reports',      'General_ledger.py'),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management',   {
                        'title': 'Budget Management',
                        'items': [
                            ('budg_plan',  'Budget Planning',     'Budget_mgmt.py'),
                            ('budg_act',   'Budget vs. Actual',   'Budget_mgmt.py'),
                            ('budg_amend', 'Budget Amendments',   'Budget_mgmt.py'),
                            ('budg_rpts',  'Budget Reports',      'Budget_mgmt.py'),
                        ],
                    }),
                    ('audit_mgmt',  'Audit Management',    {
                        'title': 'Audit Management',
                        'items': [
                            ('audit_sched','Audit Schedule',      'Accounting_manager.py'),
                            ('findings',   'Audit Findings',      'Accounting_manager.py'),
                            ('corr_act',   'Corrective Actions',  'Accounting_manager.py'),
                            ('audit_rpts', 'Audit Reports',       'Accounting_manager.py'),
                        ],
                    }),
                ],
            }),
            ('acct_rcv',    'Accounts Receivable', 'Accounts_receivable.py'),
            ('credit',      'Credit Department',   'Credit_dept.py'),
            ('payroll',     'Payroll Department',  'Payroll_dept.py'),
            ('gen_ledger',  'General Ledger',      'General_ledger.py'),
            ('budget_mgmt', 'Budget Management',   {
                'title': 'Budget Management',
                'items': [
                    ('budg_plan',  'Budget Planning',     'Budget_mgmt.py'),
                    ('budg_act',   'Budget vs. Actual',   'Budget_mgmt.py'),
                    ('budg_amend', 'Budget Amendments',   'Budget_mgmt.py'),
                    ('budg_rpts',  'Budget Reports',      'Budget_mgmt.py'),
                ],
            }),
            ('fin_reports', 'Financial Reports',   {
                'title': 'Financial Reports',
                'items': [
                    ('inc_stmt',   'Income Statement',    'General_ledger.py'),
                    ('bal_sheet',  'Balance Sheet',       'General_ledger.py'),
                    ('cash_flow',  'Cash Flow',           'General_ledger.py'),
                    ('cust_rpts',  'Custom Reports',      'General_ledger.py'),
                ],
            }),
            ('tax_mgmt',    'Tax Management',      {
                'title': 'Tax Management',
                'items': [
                    ('tax_cal',    'Tax Calendar',        'taxes.py'),
                    ('tax_filing', 'Tax Filing',          'taxes.py'),
                    ('tax_pay',    'Tax Payments',        'taxes.py'),
                    ('tax_rpts',   'Tax Reports',         'taxes.py'),
                ],
            }),
            ('exp_reports', 'Expense Reports',     {
                'title': 'Expense Reports',
                'items': [
                    ('sub_exp',    'Submit Expense',      'Accounts_payable.py'),
                    ('pend_appr',  'Pending Approval',    'Accounts_payable.py'),
                    ('appr_exp',   'Approved Expenses',   'Accounts_payable.py'),
                    ('exp_sum',    'Expense Summary',     'Accounts_payable.py'),
                ],
            }),
            ('bank_recon',  'Bank Reconciliation', {
                'title': 'Bank Reconciliation',
                'items': [
                    ('recon_acct', 'Reconcile Account',   'General_ledger.py'),
                    ('pend_items', 'Pending Items',        'General_ledger.py'),
                    ('recon_hist', 'Reconciliation History','General_ledger.py'),
                    ('bank_rpts',  'Bank Reports',         'General_ledger.py'),
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
                    ('cs_menu',    'Customer Service Menu',  _CS_MENU),
                    ('ticket_rpts','Ticket Reports',         {
                        'title': 'Ticket Reports',
                        'items': [
                            ('daily_tick', 'Daily Ticket Report',   {'title': 'Daily Ticket Report', 'items': []}),
                            ('week_sum',   'Weekly Summary',        {'title': 'Weekly Summary',      'items': []}),
                            ('res_analy',  'Resolution Analysis',   {'title': 'Resolution Analysis', 'items': []}),
                            ('sla_rpts',   'SLA Reports',           {'title': 'SLA Reports',         'items': []}),
                        ],
                    }),
                    ('staff_mgmt', 'Staff Management',       {
                        'title': 'Staff Management',
                        'items': [
                            ('staff_sched','Staff Schedule',        {'title': 'Staff Schedule',      'items': []}),
                            ('perf_met',   'Performance Metrics',   {'title': 'Performance Metrics', 'items': []}),
                            ('staff_train','Staff Training',        {'title': 'Staff Training',      'items': []}),
                            ('staff_rpts', 'Staff Reports',         {'title': 'Staff Reports',       'items': []}),
                        ],
                    }),
                    ('cust_sat',   'Customer Satisfaction',  {
                        'title': 'Customer Satisfaction',
                        'items': [
                            ('csat_res',   'CSAT Survey Results',   {'title': 'CSAT Survey Results', 'items': []}),
                            ('nps_rpts',   'NPS Reports',           {'title': 'NPS Reports',         'items': []}),
                            ('sat_trends', 'Satisfaction Trends',   {'title': 'Satisfaction Trends', 'items': []}),
                            ('impr_plans', 'Improvement Plans',     {'title': 'Improvement Plans',   'items': []}),
                        ],
                    }),
                    ('escalations','Escalations',            {
                        'title': 'Escalations',
                        'items': [
                            ('act_esc',    'Active Escalations',    {'title': 'Active Escalations',  'items': []}),
                            ('esc_hist',   'Escalation History',    {'title': 'Escalation History',  'items': []}),
                            ('esc_rpts',   'Escalation Reports',    {'title': 'Escalation Reports',  'items': []}),
                            ('res_track',  'Resolution Tracking',   {'title': 'Resolution Tracking', 'items': []}),
                        ],
                    }),
                ],
            }),
            ('cs_menu',  'Customer Service Menu',  _CS_MENU),
            ('cs_calls', 'Customer Service Calls', 'cs_calls.py'),
        ],
    },
    'engineering': {
        'title': 'Engineering Main Menu',
        'items': [
            ('eng_mgr', 'Engineering Manager', {
                'title': 'Engineering Manager',
                'items': [
                    ('engineers',  'Engineers',           'engineer.py'),
                    ('proj_appr',  'Project Approvals',   {
                        'title': 'Project Approvals',
                        'items': [
                            ('pend_appr',  'Pending Approvals',    {'title': 'Pending Approvals',  'items': []}),
                            ('appr_proj',  'Approved Projects',    {'title': 'Approved Projects',  'items': []}),
                            ('rej_proj',   'Rejected Projects',    {'title': 'Rejected Projects',  'items': []}),
                            ('appr_hist',  'Approval History',     {'title': 'Approval History',   'items': []}),
                        ],
                    }),
                    ('resource',   'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc',  'Resource Allocation',   {'title': 'Resource Allocation', 'items': []}),
                            ('cap_plan',   'Capacity Planning',     {'title': 'Capacity Planning',   'items': []}),
                            ('res_rpts',   'Resource Reports',      {'title': 'Resource Reports',    'items': []}),
                            ('avail_cal',  'Availability Calendar', {'title': 'Availability Calendar','items': []}),
                        ],
                    }),
                    ('budget',     'Budget Management',   {
                        'title': 'Budget Management',
                        'items': [
                            ('eng_budg',   'Engineering Budget',    {'title': 'Engineering Budget',  'items': []}),
                            ('budg_act',   'Budget vs. Actual',     {'title': 'Budget vs. Actual',   'items': []}),
                            ('cost_rpts',  'Cost Reports',          {'title': 'Cost Reports',        'items': []}),
                            ('budg_req',   'Budget Requests',       {'title': 'Budget Requests',     'items': []}),
                        ],
                    }),
                    ('eng_reports','Engineering Reports', {
                        'title': 'Engineering Reports',
                        'items': [
                            ('proj_stat',  'Project Status',        {'title': 'Project Status',      'items': []}),
                            ('res_util',   'Resource Utilization',  {'title': 'Resource Utilization','items': []}),
                            ('kpi_dash',   'KPI Dashboard',         {'title': 'KPI Dashboard',       'items': []}),
                            ('month_rpts', 'Monthly Reports',       {'title': 'Monthly Reports',     'items': []}),
                        ],
                    }),
                ],
            }),
            ('engineers',   'Engineers',              'engineer.py'),
            ('proj_mgmt',   'Project Management',     {
                'title': 'Project Management',
                'items': [
                    ('act_proj',   'Active Projects',      {'title': 'Active Projects',    'items': []}),
                    ('new_proj',   'New Project',          {'title': 'New Project',        'items': []}),
                    ('proj_time',  'Project Timeline',     {'title': 'Project Timeline',   'items': []}),
                    ('proj_rpts',  'Project Reports',      {'title': 'Project Reports',    'items': []}),
                ],
            }),
            ('design_docs', 'Design Documents',       {
                'title': 'Design Documents',
                'items': [
                    ('doc_lib',    'Document Library',     {'title': 'Document Library',   'items': []}),
                    ('new_doc',    'New Document',         {'title': 'New Document',       'items': []}),
                    ('doc_review', 'Document Review',      {'title': 'Document Review',    'items': []}),
                    ('archive',    'Archive',              {'title': 'Archive',            'items': []}),
                ],
            }),
            ('bom',         'Bill of Materials',      {
                'title': 'Bill of Materials',
                'items': [
                    ('bom_list',   'BOM List',            {'title': 'BOM List',           'items': []}),
                    ('new_bom',    'Create BOM',          {'title': 'Create BOM',         'items': []}),
                    ('bom_rev',    'BOM Revision',        {'title': 'BOM Revision',       'items': []}),
                    ('bom_rpts',   'BOM Reports',         {'title': 'BOM Reports',        'items': []}),
                ],
            }),
            ('chg_orders',  'Change Orders',          {
                'title': 'Change Orders',
                'items': [
                    ('new_co',     'New Change Order',    {'title': 'New Change Order',   'items': []}),
                    ('pend_appr',  'Pending Approval',    {'title': 'Pending Approval',   'items': []}),
                    ('appr_chg',   'Approved Changes',    {'title': 'Approved Changes',   'items': []}),
                    ('chg_hist',   'Change History',      {'title': 'Change History',     'items': []}),
                ],
            }),
            ('test_val',    'Test & Validation',      {
                'title': 'Test & Validation',
                'items': [
                    ('test_plans', 'Test Plans',          {'title': 'Test Plans',         'items': []}),
                    ('test_res',   'Test Results',        {'title': 'Test Results',       'items': []}),
                    ('val_rpts',   'Validation Reports',  {'title': 'Validation Reports', 'items': []}),
                    ('issue_track','Issue Tracking',      {'title': 'Issue Tracking',     'items': []}),
                ],
            }),
            ('eng_reports', 'Engineering Reports',    {
                'title': 'Engineering Reports',
                'items': [
                    ('proj_stat',  'Project Status',      {'title': 'Project Status',     'items': []}),
                    ('design_rev', 'Design Review',       {'title': 'Design Review',      'items': []}),
                    ('res_rpt',    'Resource Report',     {'title': 'Resource Report',    'items': []}),
                    ('cust_rpts',  'Custom Reports',      {'title': 'Custom Reports',     'items': []}),
                ],
            }),
            ('standards',   'Standards & Compliance', {
                'title': 'Standards & Compliance',
                'items': [
                    ('std_lib',    'Standards Library',   {'title': 'Standards Library',  'items': []}),
                    ('comp_chk',   'Compliance Checklist',{'title': 'Compliance Checklist','items': []}),
                    ('audit_res',  'Audit Results',       {'title': 'Audit Results',      'items': []}),
                    ('reg_upd',    'Regulatory Updates',  {'title': 'Regulatory Updates', 'items': []}),
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
                    ('it_tech',    'IT Technician',       _IT_TECH),
                    ('budget',     'Budget & Procurement', {
                        'title': 'Budget & Procurement',
                        'items': [
                            ('it_budg',    'IT Budget',           {'title': 'IT Budget',          'items': []}),
                            ('hw_proc',    'Hardware Procurement', {'title': 'Hardware Procurement','items': []}),
                            ('sw_lic',     'Software Licensing',   {'title': 'Software Licensing', 'items': []}),
                            ('proc_rpts',  'Procurement Reports',  {'title': 'Procurement Reports','items': []}),
                        ],
                    }),
                    ('vendor_con', 'Vendor Contracts',     {
                        'title': 'Vendor Contracts',
                        'items': [
                            ('act_cont',   'Active Contracts',     {'title': 'Active Contracts',   'items': []}),
                            ('cont_renew', 'Contract Renewals',    {'title': 'Contract Renewals',  'items': []}),
                            ('vend_perf',  'Vendor Performance',   {'title': 'Vendor Performance', 'items': []}),
                            ('cont_arch',  'Contract Archive',     {'title': 'Contract Archive',   'items': []}),
                        ],
                    }),
                    ('it_projects','IT Projects',          {
                        'title': 'IT Projects',
                        'items': [
                            ('act_proj',   'Active Projects',      {'title': 'Active Projects',    'items': []}),
                            ('proj_pipe',  'Project Pipeline',     {'title': 'Project Pipeline',   'items': []}),
                            ('proj_rpts',  'Project Reports',      {'title': 'Project Reports',    'items': []}),
                            ('res_alloc',  'Resource Allocation',  {'title': 'Resource Allocation','items': []}),
                        ],
                    }),
                    ('security',   'Security Management',  {
                        'title': 'Security Management',
                        'items': [
                            ('sec_dash',   'Security Dashboard',   {'title': 'Security Dashboard', 'items': []}),
                            ('inc_rpts',   'Incident Reports',     {'title': 'Incident Reports',   'items': []}),
                            ('vuln_mgmt',  'Vulnerability Management',{'title': 'Vulnerability Management','items': []}),
                            ('comp_rpts',  'Compliance Reports',   {'title': 'Compliance Reports', 'items': []}),
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
                    ('maint',       'Maintenance',         _MAINT_MENU),
                    ('wo_approvals','Work Order Approvals', {
                        'title': 'Work Order Approvals',
                        'items': [
                            ('pend_appr',  'Pending Approvals',    {'title': 'Pending Approvals',  'items': []}),
                            ('appr_wo',    'Approved Work Orders',  {'title': 'Approved Work Orders','items': []}),
                            ('rej_wo',     'Rejected',             {'title': 'Rejected',           'items': []}),
                            ('appr_hist',  'Approval History',     {'title': 'Approval History',   'items': []}),
                        ],
                    }),
                    ('budget_mgmt', 'Budget Management',   {
                        'title': 'Budget Management',
                        'items': [
                            ('maint_budg', 'Maintenance Budget',   {'title': 'Maintenance Budget', 'items': []}),
                            ('budg_act',   'Budget vs. Actual',    {'title': 'Budget vs. Actual',  'items': []}),
                            ('cost_analy', 'Cost Analysis',        {'title': 'Cost Analysis',      'items': []}),
                            ('budg_req',   'Budget Requests',      {'title': 'Budget Requests',    'items': []}),
                        ],
                    }),
                    ('maint_rpts',  'Maintenance Reports', {
                        'title': 'Maintenance Reports',
                        'items': [
                            ('daily_rpt',  'Daily Report',         {'title': 'Daily Report',       'items': []}),
                            ('month_sum',  'Monthly Summary',      {'title': 'Monthly Summary',    'items': []}),
                            ('equip_rpts', 'Equipment Reports',    {'title': 'Equipment Reports',  'items': []}),
                            ('cost_rpts',  'Cost Reports',         {'title': 'Cost Reports',       'items': []}),
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
                    ('mkt_menu',   'Marketing Menu',     _MKT_MENU),
                    ('mkt_budget', 'Marketing Budget',   {
                        'title': 'Marketing Budget',
                        'items': [
                            ('budg_over',  'Budget Overview',      {'title': 'Budget Overview',    'items': []}),
                            ('budg_camp',  'Budget by Campaign',   {'title': 'Budget by Campaign', 'items': []}),
                            ('budg_act',   'Budget vs. Actual',    {'title': 'Budget vs. Actual',  'items': []}),
                            ('budg_req',   'Budget Requests',      {'title': 'Budget Requests',    'items': []}),
                        ],
                    }),
                    ('camp_appr',  'Campaign Approvals', {
                        'title': 'Campaign Approvals',
                        'items': [
                            ('pend_appr',  'Pending Approvals',    {'title': 'Pending Approvals',  'items': []}),
                            ('appr_camp',  'Approved Campaigns',   {'title': 'Approved Campaigns', 'items': []}),
                            ('camp_arch',  'Campaign Archive',     {'title': 'Campaign Archive',   'items': []}),
                            ('appr_hist',  'Approval History',     {'title': 'Approval History',   'items': []}),
                        ],
                    }),
                    ('mkt_reports','Marketing Reports',  {
                        'title': 'Marketing Reports',
                        'items': [
                            ('camp_perf',  'Campaign Performance', {'title': 'Campaign Performance','items': []}),
                            ('roi_rpts',   'ROI Reports',          {'title': 'ROI Reports',        'items': []}),
                            ('month_sum',  'Monthly Summary',      {'title': 'Monthly Summary',    'items': []}),
                            ('kpi_dash',   'KPI Dashboard',        {'title': 'KPI Dashboard',      'items': []}),
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
                    ('pers_menu', 'Personnel Menu',      _PERS_MENU),
                    ('hiring',    'Hiring & Recruitment', {
                        'title': 'Hiring & Recruitment',
                        'items': [
                            ('open_pos',   'Open Positions',       {'title': 'Open Positions',     'items': []}),
                            ('appl_track', 'Applicant Tracking',   {'title': 'Applicant Tracking', 'items': []}),
                            ('int_sched',  'Interview Schedule',   {'title': 'Interview Schedule', 'items': []}),
                            ('offer_mgmt', 'Offer Management',     {'title': 'Offer Management',   'items': []}),
                        ],
                    }),
                    ('term',      'Terminations',        {
                        'title': 'Terminations',
                        'items': [
                            ('term_proc',  'Termination Process',  {'title': 'Termination Process','items': []}),
                            ('exit_int',   'Exit Interviews',      {'title': 'Exit Interviews',    'items': []}),
                            ('final_pay',  'Final Pay Processing', {'title': 'Final Pay Processing','items': []}),
                            ('offboard',   'Offboarding Checklist',{'title': 'Offboarding Checklist','items': []}),
                        ],
                    }),
                    ('salary',    'Salary Management',   {
                        'title': 'Salary Management',
                        'items': [
                            ('sal_review', 'Salary Review',        {'title': 'Salary Review',      'items': []}),
                            ('sal_adj',    'Salary Adjustments',   {'title': 'Salary Adjustments', 'items': []}),
                            ('comp_rpts',  'Compensation Reports', {'title': 'Compensation Reports','items': []}),
                            ('pay_grades', 'Pay Grades',           {'title': 'Pay Grades',         'items': []}),
                        ],
                    }),
                    ('hr_reports','HR Reports',          {
                        'title': 'HR Reports',
                        'items': [
                            ('hd_rpt',     'Headcount Report',     {'title': 'Headcount Report',   'items': []}),
                            ('turn_rpt',   'Turnover Report',      {'title': 'Turnover Report',    'items': []}),
                            ('comp_rpts',  'Compliance Reports',   {'title': 'Compliance Reports', 'items': []}),
                            ('month_sum',  'Monthly Summary',      {'title': 'Monthly Summary',    'items': []}),
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
                    ('prod',        'Production',         _PROD_MENU),
                    ('shipping',    'Shipping',           _SHIP_MENU),
                    ('prod_reports','Production Reports', {
                        'title': 'Production Reports',
                        'items': [
                            ('daily_prod', 'Daily Production',     {'title': 'Daily Production',   'items': []}),
                            ('week_sum',   'Weekly Summary',       {'title': 'Weekly Summary',     'items': []}),
                            ('eff_rpts',   'Efficiency Reports',   {'title': 'Efficiency Reports', 'items': []}),
                            ('kpi_dash',   'KPI Dashboard',        {'title': 'KPI Dashboard',      'items': []}),
                        ],
                    }),
                    ('resource',    'Resource Management', {
                        'title': 'Resource Management',
                        'items': [
                            ('res_alloc',  'Resource Allocation',   {'title': 'Resource Allocation','items': []}),
                            ('cap_plan',   'Capacity Planning',     {'title': 'Capacity Planning',  'items': []}),
                            ('res_rpts',   'Resource Reports',      {'title': 'Resource Reports',   'items': []}),
                            ('wf_plan',    'Workforce Planning',    {'title': 'Workforce Planning', 'items': []}),
                        ],
                    }),
                    ('budget',      'Budget Management',  {
                        'title': 'Budget Management',
                        'items': [
                            ('prod_budg',  'Production Budget',    {'title': 'Production Budget',  'items': []}),
                            ('cost_analy', 'Cost Analysis',        {'title': 'Cost Analysis',      'items': []}),
                            ('budg_act',   'Budget vs. Actual',    {'title': 'Budget vs. Actual',  'items': []}),
                            ('budg_rpts',  'Budget Reports',       {'title': 'Budget Reports',     'items': []}),
                        ],
                    }),
                ],
            }),
            ('prod',     'Production', _PROD_MENU),
            ('shipping', 'Shipping',   _SHIP_MENU),
        ],
    },
    'purchasing': {
        'title': 'Purchasing Main Menu',
        'items': [
            ('purch_mgr', 'Purchasing Manager Menu', {
                'title': 'Purchasing Manager Menu',
                'items': [
                    ('purch',       'Purchasing Menu',          _PURCH_MENU),
                    ('po_approvals','PO Approvals',            {
                        'title': 'PO Approvals',
                        'items': [
                            ('pend_appr',  'Pending Approvals',    {'title': 'Pending Approvals',  'items': []}),
                            ('appr_pos',   'Approved POs',         {'title': 'Approved POs',       'items': []}),
                            ('rej_pos',    'Rejected POs',         {'title': 'Rejected POs',       'items': []}),
                            ('appr_hist',  'Approval History',     {'title': 'Approval History',   'items': []}),
                        ],
                    }),
                    ('budget',      'Budget Management',        {
                        'title': 'Budget Management',
                        'items': [
                            ('purch_budg', 'Purchasing Budget',    {'title': 'Purchasing Budget',  'items': []}),
                            ('budg_act',   'Budget vs. Actual',    {'title': 'Budget vs. Actual',  'items': []}),
                            ('spend_analy','Spending Analysis',    {'title': 'Spending Analysis',  'items': []}),
                            ('budg_rpts',  'Budget Reports',       {'title': 'Budget Reports',     'items': []}),
                        ],
                    }),
                    ('vendor_mgmt', 'Vendor Management',        {
                        'title': 'Vendor Management',
                        'items': [
                            ('vend_list',  'Vendor List',          {'title': 'Vendor List',        'items': []}),
                            ('vend_eval',  'Vendor Evaluation',    {'title': 'Vendor Evaluation',  'items': []}),
                            ('vend_perf',  'Vendor Performance',   {'title': 'Vendor Performance', 'items': []}),
                            ('appr_vend',  'Approved Vendors',     {'title': 'Approved Vendors',   'items': []}),
                        ],
                    }),
                    ('purch_rpts',  'Purchasing Reports',       {
                        'title': 'Purchasing Reports',
                        'items': [
                            ('spend_rpt',  'Spending Report',      {'title': 'Spending Report',    'items': []}),
                            ('vend_rpt',   'Vendor Report',        {'title': 'Vendor Report',      'items': []}),
                            ('cat_analy',  'Category Analysis',    {'title': 'Category Analysis',  'items': []}),
                            ('month_sum',  'Monthly Summary',      {'title': 'Monthly Summary',    'items': []}),
                        ],
                    }),
                    ('contracts',   'Contract Management',      {
                        'title': 'Contract Management',
                        'items': [
                            ('act_cont',   'Active Contracts',     {'title': 'Active Contracts',   'items': []}),
                            ('pend_renew', 'Pending Renewals',     {'title': 'Pending Renewals',   'items': []}),
                            ('cont_arch',  'Contract Archive',     {'title': 'Contract Archive',   'items': []}),
                            ('cont_rpts',  'Contract Reports',     {'title': 'Contract Reports',   'items': []}),
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
                    ('qa_menu',    'Quality Assurance Menu', _QA_MENU),
                    ('audit_mgmt', 'Audit Management',   {
                        'title': 'Audit Management',
                        'items': [
                            ('audit_sched','Audit Schedule',       {'title': 'Audit Schedule',     'items': []}),
                            ('act_audits', 'Active Audits',        {'title': 'Active Audits',      'items': []}),
                            ('findings',   'Audit Findings',       {'title': 'Audit Findings',     'items': []}),
                            ('corr_act',   'Corrective Actions',   {'title': 'Corrective Actions', 'items': []}),
                        ],
                    }),
                    ('compliance', 'Compliance',          {
                        'title': 'Compliance',
                        'items': [
                            ('comp_dash',  'Compliance Dashboard', {'title': 'Compliance Dashboard','items': []}),
                            ('reg_req',    'Regulatory Requirements',{'title': 'Regulatory Requirements','items': []}),
                            ('comp_rpts',  'Compliance Reports',   {'title': 'Compliance Reports', 'items': []}),
                            ('non_comp',   'Non-Compliance Issues', {'title': 'Non-Compliance Issues','items': []}),
                        ],
                    }),
                    ('corr_action','Corrective Actions',  {
                        'title': 'Corrective Actions',
                        'items': [
                            ('open_cars',  'Open CARs',            {'title': 'Open CARs',          'items': []}),
                            ('inprog_cars','In Progress',          {'title': 'In Progress',        'items': []}),
                            ('closed_cars','Closed CARs',          {'title': 'Closed CARs',        'items': []}),
                            ('car_rpts',   'CAR Reports',          {'title': 'CAR Reports',        'items': []}),
                        ],
                    }),
                    ('qa_reports', 'QA Reports',          {
                        'title': 'QA Reports',
                        'items': [
                            ('daily_qa',   'Daily QA Report',      {'title': 'Daily QA Report',    'items': []}),
                            ('week_sum',   'Weekly Summary',       {'title': 'Weekly Summary',     'items': []}),
                            ('month_rpt',  'Monthly Report',       {'title': 'Monthly Report',     'items': []}),
                            ('kpi_dash',   'KPI Dashboard',        {'title': 'KPI Dashboard',      'items': []}),
                        ],
                    }),
                    ('supp_qual',  'Supplier Quality',    {
                        'title': 'Supplier Quality',
                        'items': [
                            ('supp_score', 'Supplier Scorecards',  {'title': 'Supplier Scorecards','items': []}),
                            ('inc_insp',   'Incoming Inspection',  {'title': 'Incoming Inspection','items': []}),
                            ('supp_audit', 'Supplier Audits',      {'title': 'Supplier Audits',    'items': []}),
                            ('supp_rpts',  'Supplier Reports',     {'title': 'Supplier Reports',   'items': []}),
                        ],
                    }),
                    ('cust_comp',  'Customer Complaints', {
                        'title': 'Customer Complaints',
                        'items': [
                            ('new_comp',   'New Complaint',        {'title': 'New Complaint',      'items': []}),
                            ('open_comp',  'Open Complaints',      {'title': 'Open Complaints',    'items': []}),
                            ('res_track',  'Resolution Tracking',  {'title': 'Resolution Tracking','items': []}),
                            ('comp_rpts',  'Complaint Reports',    {'title': 'Complaint Reports',  'items': []}),
                        ],
                    }),
                    ('doc_control','Document Control',    {
                        'title': 'Document Control',
                        'items': [
                            ('doc_lib',    'Document Library',     {'title': 'Document Library',   'items': []}),
                            ('new_doc',    'New Document',         {'title': 'New Document',       'items': []}),
                            ('doc_review', 'Document Review',      {'title': 'Document Review',    'items': []}),
                            ('rev_hist',   'Revision History',     {'title': 'Revision History',   'items': []}),
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
                    ('sales',        'Sales Menu',            _SALES_MENU),
                    ('sales_targets','Sales Targets',         {
                        'title': 'Sales Targets',
                        'items': [
                            ('set_tgt',    'Set Targets',          {'title': 'Set Targets',        'items': []}),
                            ('tgt_act',    'Target vs. Actual',    {'title': 'Target vs. Actual',  'items': []}),
                            ('tgt_rep',    'Target by Rep',        {'title': 'Target by Rep',      'items': []}),
                            ('tgt_rpts',   'Target Reports',       {'title': 'Target Reports',     'items': []}),
                        ],
                    }),
                    ('territory',    'Territory Management',  {
                        'title': 'Territory Management',
                        'items': [
                            ('terr_map',   'Territory Map',        {'title': 'Territory Map',      'items': []}),
                            ('terr_assign','Territory Assignments',{'title': 'Territory Assignments','items': []}),
                            ('terr_perf',  'Territory Performance',{'title': 'Territory Performance','items': []}),
                            ('terr_rpts',  'Territory Reports',    {'title': 'Territory Reports',  'items': []}),
                        ],
                    }),
                    ('commission',   'Commission Tracking',   {
                        'title': 'Commission Tracking',
                        'items': [
                            ('comm_calc',  'Commission Calculator',{'title': 'Commission Calculator','items': []}),
                            ('comm_rpts',  'Commission Reports',   {'title': 'Commission Reports', 'items': []}),
                            ('pay_hist',   'Payment History',      {'title': 'Payment History',    'items': []}),
                            ('comm_plans', 'Commission Plans',     {'title': 'Commission Plans',   'items': []}),
                        ],
                    }),
                    ('staff_perf',   'Staff Performance',     {
                        'title': 'Staff Performance',
                        'items': [
                            ('perf_dash',  'Performance Dashboard',{'title': 'Performance Dashboard','items': []}),
                            ('rep_rank',   'Rep Rankings',         {'title': 'Rep Rankings',       'items': []}),
                            ('perf_revs',  'Performance Reviews',  {'title': 'Performance Reviews','items': []}),
                            ('coaching',   'Coaching Notes',       {'title': 'Coaching Notes',     'items': []}),
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
            ('budgets',    'Budgets',             'Budget_mgmt.py'),
            ('bud_detail', 'Budget Detail',       'Budget_mgmt.py'),
            ('bva',        'Budget vs. Actual',   'Budget_mgmt.py'),
            ('variance',   'Variance Report',     'Budget_mgmt.py'),
        ],
    },
    'finance': {
        'title': 'Finance Main Menu',
        'items': [
            ('fin_mgr',      'Finance Manager', {
                'title': 'Finance Manager',
                'items': [
                    ('fin_plan',     'Financial Planning',    {'title': 'Financial Planning',    'items': []}),
                    ('fin_forecast', 'Budget & Forecasting',  {'title': 'Budget & Forecasting',  'items': []}),
                    ('treasury_mgmt','Treasury Management',   {'title': 'Treasury Management',   'items': []}),
                    ('invest_mgmt',  'Investment Management', {'title': 'Investment Management', 'items': []}),
                    ('fin_rpts_mgr', 'Financial Reports',     {'title': 'Financial Reports',     'items': []}),
                ],
            }),
            ('fin_analysis',  'Financial Analysis',   {'title': 'Financial Analysis',   'items': []}),
            ('fin_reporting', 'Financial Reporting',   {'title': 'Financial Reporting',   'items': []}),
            ('treasury_ops',  'Treasury Operations',   {'title': 'Treasury Operations',   'items': []}),
            ('capital_mgmt',  'Capital Management',    {'title': 'Capital Management',    'items': []}),
            ('tax_planning',  'Tax Planning',           {'title': 'Tax Planning',           'items': []}),
        ],
    },
    'legal': {
        'title': 'Legal Main Menu',
        'items': [
            ('legal_mgr',    'Legal Manager', {
                'title': 'Legal Manager',
                'items': [
                    ('contracts_mgmt',  'Contract Management',   {'title': 'Contract Management',   'items': []}),
                    ('litigation_mgmt', 'Litigation Management', {'title': 'Litigation Management', 'items': []}),
                    ('compliance_mgmt', 'Compliance Management', {'title': 'Compliance Management', 'items': []}),
                    ('corp_gov',        'Corporate Governance',  {'title': 'Corporate Governance',  'items': []}),
                ],
            }),
            ('contracts',  'Contracts',            {'title': 'Contracts',            'items': []}),
            ('compliance', 'Compliance',           {'title': 'Compliance',           'items': []}),
            ('litigation', 'Litigation',           {'title': 'Litigation',           'items': []}),
            ('ip_mgmt',    'Intellectual Property',{'title': 'Intellectual Property','items': []}),
            ('emp_law',    'Employment Law',        {'title': 'Employment Law',        'items': []}),
        ],
    },
    'risk_management': {
        'title': 'Risk Management Main Menu',
        'items': [
            ('risk_mgr',     'Risk Manager', {
                'title': 'Risk Manager',
                'items': [
                    ('risk_framework', 'Risk Framework',      {'title': 'Risk Framework',      'items': []}),
                    ('risk_reporting', 'Risk Reporting',      {'title': 'Risk Reporting',      'items': []}),
                    ('biz_continuity', 'Business Continuity', {'title': 'Business Continuity', 'items': []}),
                ],
            }),
            ('risk_assess',   'Risk Assessment',     {'title': 'Risk Assessment',     'items': []}),
            ('risk_register', 'Risk Register',        {'title': 'Risk Register',        'items': []}),
            ('insurance',     'Insurance Management', {'title': 'Insurance Management', 'items': []}),
            ('biz_cont',      'Business Continuity',  {'title': 'Business Continuity',  'items': []}),
            ('comp_audit',    'Compliance & Audit',   {'title': 'Compliance & Audit',   'items': []}),
        ],
    },
}


def _walk_tree(dept, parts):
    """Walk MENU_TREE by dept + list of key parts. Returns the node dict, or None."""
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


DB_PATH = os.path.join(os.path.dirname(__file__), 'company.db')

# Maps dept.dept_name → MENU_TREE key (None = full access, e.g. Company)
DEPT_MENU_KEY = {
    'Accounting':               'accounting',
    'Customer Service':         'customer_service',
    'Engineering':              'engineering',
    'Information Technologies': 'information_tech',
    'Maintenance':              'maintenance',
    'Marketing':                'marketing',
    'Personnel':                'personnel',
    'Production':               'production',
    'Purchasing':               'purchasing',
    'Quality Assurance':        'quality_assurance',
    'Sales':                    'sales',
    'Budget Management':        'budget_management',
    'Company':                  None,   # full access
    'Labs':                     'quality_assurance',
    'Finance':                  'finance',
    'Legal':                    'legal',
    'Risk Management':          'risk_management',
}

FULL_ACCESS_ROLES = {'Admin', 'President', 'Vice President', 'Auditor'}
READ_ONLY_ROLES   = {'Auditor'}   # can browse all depts but cannot launch scripts

# dept_sub_ids whose holders are department managers
MANAGER_DEPT_SUB_IDS = {5, 7, 10, 11, 13, 15, 17, 19, 22, 24, 25, 26, 28, 31, 33, 36, 40}

# MENU_TREE item keys that are hidden from non-managers
MANAGER_MENU_KEYS = {
    'acct_mgr', 'cs_mgr', 'eng_mgr', 'it_mgr', 'maint_mgr',
    'mkt_mgr', 'pers_mgr', 'prod_mgr', 'purch_mgr', 'qa_mgr', 'sales_mgr',
    'fin_mgr', 'legal_mgr', 'risk_mgr',
}


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_roles():
    """Insert any missing roles into the roles table."""
    conn = _get_db()
    for name, desc in [
        ('President',           'Full access — company president'),
        ('Vice President',      'Full access — company vice president'),
        ('Department Manager',  'Full access to own department including management screens'),
        ('Supervisor',          'Access to own department operational screens'),
        ('Auditor',             'Read-only browse access across all departments — cannot launch apps'),
        ('HR / Personnel',      'Full access to Personnel department'),
    ]:
        conn.execute(
            "INSERT INTO roles(role_name, description) SELECT ?,? WHERE NOT EXISTS "
            "(SELECT 1 FROM roles WHERE role_name=?)", (name, desc, name)
        )
    conn.commit()
    conn.close()


def _get_user_profile(email: str) -> dict:
    conn = _get_db()
    row = conn.execute("""
        SELECT p.id, p.dept_id, p.dept_Sub_id, d.dept_name,
               r.role_name,
               pos.position
        FROM people p
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        LEFT JOIN position pos ON pos.people_id = p.id
        WHERE p.email = ?
    """, (email,)).fetchone()
    conn.close()
    if not row:
        return {}
    dept_name   = row['dept_name'] or ''
    dept_key    = DEPT_MENU_KEY.get(dept_name)
    role_name   = row['role_name'] or ''
    dept_sub_id = row['dept_Sub_id']
    is_manager  = (
        dept_sub_id in MANAGER_DEPT_SUB_IDS
        or role_name in {'Department Manager'} | FULL_ACCESS_ROLES
    )
    return {
        'people_id':   row['id'],
        'dept_name':   dept_name,
        'dept_key':    dept_key,
        'role_name':   role_name,
        'position':    row['position'] or '',
        'dept_sub_id': dept_sub_id,
        'is_manager':  is_manager,
    }


def _is_full_access(profile: dict) -> bool:
    """Admin, President, Vice President, or Company dept users see all departments."""
    return (
        profile.get('role_name') in FULL_ACCESS_ROLES
        or profile.get('dept_key') is None
    )


def _verify_login(email: str, password: str) -> bool:
    conn = _get_db()
    row = conn.execute(
        "SELECT pw.password FROM passwd pw JOIN people p ON pw.people_id = p.id WHERE p.email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return row is not None and password == row["password"]


def _email_exists(email: str) -> bool:
    conn = _get_db()
    found = conn.execute("SELECT id FROM people WHERE email = ?", (email,)).fetchone()
    conn.close()
    return found is not None


def _create_user(email, password, first_name='', last_name='',
                 address='', city='', state='', zip_code='', employee_id=0) -> bool:
    try:
        conn = _get_db()
        if conn.execute("SELECT id FROM people WHERE email = ?", (email,)).fetchone():
            conn.close()
            return False
        cursor = conn.execute(
            "INSERT INTO people (first_name, last_name, ID, address, city, state, zip_code, email) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (first_name, last_name, employee_id, address, city, state, zip_code, email),
        )
        conn.execute(
            "INSERT INTO passwd (people_id, password) VALUES (?, ?)",
            (cursor.lastrowid, password),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def _reset_password(email: str, new_password: str) -> bool:
    conn = _get_db()
    row = conn.execute(
        "SELECT pw.id as pw_id FROM passwd pw JOIN people p ON pw.people_id = p.id WHERE p.email = ?",
        (email,),
    ).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("UPDATE passwd SET password = ? WHERE id = ?", (new_password, row["pw_id"]))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Login / dashboard / logout
# ---------------------------------------------------------------------------

def home(request):
    _ensure_roles()
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
            request.session['user_role']        = profile.get('role_name', '')
            request.session['user_dept_key']    = profile.get('dept_key') or ''
            request.session['user_dept_name']   = profile.get('dept_name', '')
            request.session['user_full_access'] = _is_full_access(profile)
            request.session['user_is_manager']  = profile.get('is_manager', False)
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
    return render(request, 'dashboard.html', {
        'email':       email,
        'user_role':   request.session.get('user_role', ''),
        'dept_name':   request.session.get('user_dept_name', ''),
        'full_access': request.session.get('user_full_access', False),
    })


def logout(request):
    request.session.flush()
    return redirect('home')


def generic_menu(request, dept, subpath=''):
    if not request.session.get('user_email'):
        return redirect('home')
    if not request.session.get('user_full_access'):
        user_dept = request.session.get('user_dept_key', '')
        if user_dept and dept != user_dept:
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
            url = '/run/{}/{}/'.format(dept, '/'.join(new_parts))
        items.append((url, label))

    if parts:
        parent = parts[:-1]
        back_url = '/dept/{}/{}/'.format(dept, '/'.join(parent)) if parent else '/dept/{}/'.format(dept)
    else:
        back_url = '/dashboard/'

    return render(request, 'dept_menu.html', {
        'email':       request.session['user_email'],
        'user_role':   request.session.get('user_role', ''),
        'full_access': request.session.get('user_full_access', False),
        'title':       node['title'],
        'items':       items,
        'back_url':    back_url,
    })


def run_script(request, dept, subpath):
    if not request.session.get('user_email'):
        return redirect('home')
    if request.session.get('user_role') in READ_ONLY_ROLES:
        return redirect('dept_menu', dept=dept)
    if not request.session.get('user_full_access'):
        user_dept = request.session.get('user_dept_key', '')
        if user_dept and dept != user_dept:
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
                subprocess.Popen([sys.executable, os.path.join(mfg_dir, target)], cwd=mfg_dir)
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
            return render(request, 'register.html', {'error': error, 'form': request.POST})

        emp_id = int(emp_id_text) if emp_id_text else 0
        ok = _create_user(email, password, first, last, address, city, state, zip_code, emp_id)

        if ok:
            return render(request, 'home.html', {
                'success': f'Account created for {first} {last}. You can now log in.',
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

def _get_all_users_with_roles():
    conn = _get_db()
    rows = conn.execute("""
        SELECT p.id, p.first_name, p.last_name, p.email,
               d.dept_name,
               r.id as role_id, r.role_name
        FROM people p
        LEFT JOIN dept d ON d.dept_id = p.dept_id
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        ORDER BY d.dept_name, p.last_name, p.first_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_all_roles():
    conn = _get_db()
    rows = conn.execute("SELECT id, role_name FROM roles ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _set_user_role(people_id: int, role_id: int):
    conn = _get_db()
    conn.execute("""
        INSERT INTO user_roles (people_id, role_id) VALUES (?, ?)
        ON CONFLICT(people_id) DO UPDATE SET role_id = excluded.role_id
    """, (people_id, role_id))
    conn.commit()
    conn.close()


def _remove_user_role(people_id: int):
    conn = _get_db()
    conn.execute("DELETE FROM user_roles WHERE people_id = ?", (people_id,))
    conn.commit()
    conn.close()


def user_roles(request):
    if not request.session.get('user_email'):
        return redirect('home')

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
