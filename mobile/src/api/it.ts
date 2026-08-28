import { apiClient } from './client';

export interface RecentItTicket {
  id: number;
  ticket_number: string;
  requester: string;
  department: string;
  issue_type: string;
  priority: string;
  status: string;
  submitted_date: string;
}

export interface ItDashboardData {
  tickets: {
    open_count: number;
    in_progress_count: number;
    critical_count: number;
    total_count: number;
  };
  assets: {
    total: number;
    active: number;
    repair: number;
  };
  recent_tickets: RecentItTicket[];
}

export const getItDashboard = () =>
  apiClient.get<{ ok: boolean; data: ItDashboardData }>('/dashboards/it/');
