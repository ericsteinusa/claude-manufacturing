import { apiClient } from './client';

export interface RecentLegalContract {
  id: number;
  title: string;
  counterparty: string;
  contract_type: string;
  value: number;
  status: string;
  end_date: string;
}

export interface LegalDashboardData {
  contracts: {
    total: number;
    active: number;
    draft: number;
  };
  compliance: {
    total: number;
    pending: number;
    completed: number;
  };
  litigation: {
    total: number;
    open: number;
    closed: number;
  };
  recent_contracts: RecentLegalContract[];
}

export const getLegalDashboard = () =>
  apiClient.get<{ ok: boolean; data: LegalDashboardData }>('/dashboards/legal/');
