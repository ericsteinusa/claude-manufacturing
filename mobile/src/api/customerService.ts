import { apiClient } from './client';

export interface RecentTicket {
  id: number;
  customer_name: string;
  call: string;
  call_date: string | null;
  completion_box: number;
}

export interface CustomerServiceDashboardData {
  total: number;
  open_count: number;
  completed_count: number;
  completion_rate: number;
  avg_resolution: number | null;
  avg_age_open: number | null;
  recent_tickets: RecentTicket[];
}

export const getCustomerServiceDashboard = () =>
  apiClient.get<{ ok: boolean; data: CustomerServiceDashboardData }>('/dashboards/customer-service/');
