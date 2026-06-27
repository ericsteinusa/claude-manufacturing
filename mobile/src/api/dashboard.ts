import { apiClient } from './client';

export interface DashboardData {
  po: {
    by_status: Record<string, number>;
    total_spend: number;
    overdue: number;
  };
  wo: { by_status: Record<string, number> };
  inventory: { alert_count: number; items: { name: string; on_hand: number; reorder_point: number }[] };
  cs: { total: number; open: number; closed: number; today: number };
}

export const getDashboard = () =>
  apiClient.get<{ ok: boolean; data: DashboardData }>('/dashboard/');
