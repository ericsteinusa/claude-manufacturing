import { apiClient } from './client';

export interface FinancialDashboardData {
  cash_position: number;
  dso: number;
  dpo: number;
  ar_aging: {
    current: number;
    '1_30': number;
    '31_60': number;
    '61_90': number;
    over_90: number;
  };
  ap_due_week: number;
  gross_margin_pct: number;
}

export const getFinancialDashboard = () =>
  apiClient.get<{ ok: boolean; data: FinancialDashboardData }>('/dashboards/financial/');
