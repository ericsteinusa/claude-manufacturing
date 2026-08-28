import { apiClient } from './client';

export interface RecentCollection {
  id: number;
  customer_name: string;
  activity_type: string;
  activity_date: string;
  status: string;
  amount_promised: number | null;
}

export interface CustomersDashboardData {
  accounts: {
    total: number;
    good: number;
    hold: number;
    suspended: number;
    total_exposure: number;
  };
  applications: {
    total: number;
    pending: number;
  };
  collections: {
    total: number;
    open: number;
  };
  recent_collections: RecentCollection[];
}

export const getCustomersDashboard = () =>
  apiClient.get<{ ok: boolean; data: CustomersDashboardData }>('/dashboards/customers/');
