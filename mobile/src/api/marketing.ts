import { apiClient } from './client';

export interface RecentMarketingCampaign {
  id: number;
  name: string;
  channel: string;
  objective: string;
  status: string;
  start_date: string;
  end_date: string;
  budget: number;
}

export interface MarketingDashboardData {
  campaigns: {
    total: number;
    active: number;
    planned: number;
  };
  leads: {
    total: number;
    new_count: number;
    qualified: number;
  };
  content: {
    total: number;
    draft: number;
    published: number;
  };
  recent_campaigns: RecentMarketingCampaign[];
}

export const getMarketingDashboard = () =>
  apiClient.get<{ ok: boolean; data: MarketingDashboardData }>('/dashboards/marketing/');
