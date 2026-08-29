import { apiClient } from './client';

export interface RecentPayrollRun {
  id: number;
  run_date: string;
  pay_period_start: string;
  pay_period_end: string;
  status: string;
  emp_count: number;
  total_gross: number;
  total_net: number;
}

export interface PayrollDashboardData {
  counts: {
    total_runs: number;
    emp_with_rates: number;
    total_people: number;
    active_ded_types: number;
    ytd_gross: number;
  };
  recent_runs: RecentPayrollRun[];
}

export const getPayrollDashboard = () =>
  apiClient.get<{ ok: boolean; data: PayrollDashboardData }>('/dashboards/payroll/');
