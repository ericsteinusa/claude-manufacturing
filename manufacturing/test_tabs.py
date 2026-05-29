"""Tab-switching regression test. Run from the manufacturing/ directory."""
import sys
import os
import traceback
import importlib
_DIR = r"C:\tester\manufacture\manufacturing"
os.chdir(_DIR)
sys.path.insert(0, _DIR)

from PyQt6 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication(sys.argv)

# (module, class_name, friendly_name)
WINDOWS = [
    ("Accounts_receivable",  "AccountsReceivable",       "Accounts Receivable"),
    ("Audit_mgmt",           "AuditWindow",               "Audit Mgmt"),
    ("Bank_reconciliation",  "BankReconciliationWindow",  "Bank Reconciliation"),
    ("Budget_mgmt",          "BudgetWindow",              "Budget Mgmt"),
    ("Credit_dept",          "CreditDept",                "Credit Dept"),
    ("General_ledger",       "GeneralLedgerWindow",       "General Ledger"),
    ("Tax_mgmt",             "TaxWindow",                 "Tax Mgmt"),
    ("cs_escalations",       "CSEscalationsWindow",       "CS Escalations"),
    ("cs_reports",           "CSReportsWindow",           "CS Reports"),
    ("cs_satisfaction",      "CSSatisfactionWindow",      "CS Satisfaction"),
    ("cs_staff_mgmt",        "CSStaffMgmtWindow",         "CS Staff Mgmt"),
    ("eng_design_review",    "DesignReviewMenu",          "Design Review"),
    ("eng_reports",          "EngReportsMenu",            "Eng Reports"),
    ("engineer",             "EngineerMenu",              "Engineer"),
    ("eng_mgr",              "EngMgrMenu",                "Eng Mgr"),
    ("IT_mgr",               "ITMgrMenu",                 "IT Mgr"),
    ("IT_mgr_reports",       "ITMgrReportsWidget",        "IT Mgr Reports"),
    ("IT_technician",        "ITTechnicianMenu",          "IT Technician"),
    ("IT_tech_reports",      "ITTechReportsWidget",       "IT Tech Reports"),
    ("it_calls",             "ITSupportMenu",             "IT Calls"),
    ("it_calls_reports",     "ITSupportReportsWidget",    "IT Support Reports"),
    ("IT_Tasks",             "ITTasksMenu",               "IT Tasks"),
    ("IT_tasks_reports",     "ITTasksReportsWidget",      "IT Tasks Reports"),
    ("IT_reports",           "ITReportsWidget",           "IT Reports"),
    ("marketing_menu",       "MarketingMenu",             "Marketing"),
    ("marketing_mgr_menu",   "MarketingMgrMenu",          "Marketing Mgr"),
    ("personnel_menu",       "PersonnelMenu",             "Personnel"),
    ("personnel_mgr_menu",   "PersonnelMgrMenu",          "Personnel Mgr"),
    ("personnel_crm",        "PersonnelCRM",              "Personnel CRM"),
    ("Payroll_dept",         "PayrollDept",               "Payroll"),
    ("time_clock_menu",      "TimeClock",                 "Time Clock"),
    ("prod_mgr_Menu",        "ProdMgrMenu",               "Prod Mgr"),
    ("prod_prod_menu",       "WorkOrders",                "Work Orders"),
    ("prod_ship_dept",       "ShippingDept",              "Shipping Dept"),
    ("purchase_orders",      "PurchaseOrdersWindow",      "Purchase Orders"),
    ("receiving_dept",       "ReceivingDept",             "Receiving Dept"),
    ("QA_Lab_menu",          "QALab",                     "QA Lab"),
    ("QA_Mgr_menu",          "QAMgrMenu",                 "QA Mgr"),
    ("Quality_Assurance_menu","QualityAssuranceMenu",     "Quality Assurance"),
    ("Sales_menu",           "SalesOrders",               "Sales Orders"),
    ("Sales_mgr_menu",       "SalesMgrMenu",              "Sales Mgr"),
    ("warehouse_inventory",  "WarehouseWindow",           "Warehouse"),
    ("Supplier_entry",       "Purchasing",                "Supplier/Purchasing"),
    ("Accounting_manager",   "AccountingManagerWindow",   "Accounting Manager"),
    ("cs_menu",              "CSMenu",                    "CS Menu"),
    ("cs_mgr_menu",          "CSMgrMenu",                 "CS Mgr Menu"),
    ("Purchasing_menu",      "PurchasingMenu",            "Purchasing Menu"),
    ("Purchasing_Mgr_menu",  "PurchasingMgrMenu",         "Purchasing Mgr Menu"),
    ("Maint_Maint_menu",     "MaintMenu",                 "Maintenance Menu"),
    ("Maint_mgr_menu",       "MaintMgrMenu",              "Maintenance Mgr"),
    ("Budget_mgr_menu",      "BudgetMgrMenu",             "Budget Mgr"),
    ("Finance_mgr_menu",     "FinanceMgrMenu",            "Finance Mgr"),
    ("Legal_mgr_menu",       "LegalMgrMenu",              "Legal Mgr"),
    ("Risk_mgr_menu",        "RiskMgrMenu",               "Risk Mgr"),
]

def find_tab_widgets(win):
    return win.findChildren(QtWidgets.QTabWidget)

results = []

for mod_name, cls_name, label in WINDOWS:
    try:
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        win = cls()

        tab_errors = []
        tab_widgets = find_tab_widgets(win)
        tab_info = []

        for tw in tab_widgets:
            count = tw.count()
            for i in range(count):
                tab_label = tw.tabText(i)
                try:
                    tw.setCurrentIndex(i)
                    app.processEvents()
                    tab_info.append(f"  tab[{i}] '{tab_label}' OK")
                except Exception as e:
                    tab_info.append(f"  tab[{i}] '{tab_label}' FAIL: {e}")
                    tab_errors.append(f"'{tab_label}': {e}")

        win.close()

        if tab_errors:
            results.append((label, "FAIL", tab_errors, tab_info))
        else:
            results.append((label, "OK", [], tab_info))

    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        short = tb[-1]
        results.append((label, "FAIL", [short], []))

# ── Print results ──────────────────────────────────────────────────────────────
print()
print("=" * 70)
ok  = sum(1 for _,s,_,_ in results if s == "OK")
fail = sum(1 for _,s,_,_ in results if s == "FAIL")
print(f"Results: {ok} passed, {fail} failed  ({len(results)} screens)")
print("=" * 70)

for label, status, errors, tab_info in results:
    if status == "FAIL":
        print(f"\nFAIL  {label}")
        for e in errors:
            print(f"      {e}")
    else:
        tabs_str = f"({len(tab_info)} tabs)" if tab_info else "(no tabs)"
        print(f"OK    {label:<35} {tabs_str}")

if fail:
    print("\n--- Detailed tab output for failures ---")
    for label, status, errors, tab_info in results:
        if status == "FAIL" and tab_info:
            print(f"\n{label}:")
            for t in tab_info:
                print(t)

sys.exit(0)
