import { apiClient } from './client';

export interface SalesOrderSummary {
  id: number;
  so_number: string;
  customer: string;
  status: string;
  total: number;
  order_date: string | null;
}

export interface SalesDashboardData {
  orders: {
    draft: number;
    confirmed: number;
    shipped: number;
    invoiced: number;
    total: number;
    total_value: number;
  };
  quotes: {
    draft: number;
    sent: number;
    won: number;
    total: number;
    won_value: number;
  };
  targets: {
    total_target: number;
    total_actual: number;
  };
  recent_orders: SalesOrderSummary[];
}

export const getSalesDashboard = () =>
  apiClient.get<{ ok: boolean; data: SalesDashboardData }>('/dashboards/sales/');
