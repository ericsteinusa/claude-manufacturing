import { apiClient } from './client';

export interface LedgerSummary {
  open_count: number;
  overdue_count: number;
  total_outstanding: number;
  total_invoiced: number;
  total_invoices: number;
}

export interface RecentJournal {
  id: number;
  journal_date: string;
  reference: string;
  description: string;
  posted: number;
  line_count: number;
  total_debit: number;
}

export interface AccountingDashboardData {
  ap: LedgerSummary;
  ar: LedgerSummary;
  recent_journals: RecentJournal[];
}

export const getAccountingDashboard = () =>
  apiClient.get<{ ok: boolean; data: AccountingDashboardData }>('/dashboards/accounting/');
