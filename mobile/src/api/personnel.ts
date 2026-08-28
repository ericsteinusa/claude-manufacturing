import { apiClient } from './client';

export interface RecentEmployee {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  dept_name: string;
  job_title: string;
}

export interface PersonnelDashboardData {
  employees: { total: number };
  by_dept: { dept_name: string; count: number }[];
  time_off: { pending: number; approved: number };
  recent_employees: RecentEmployee[];
}

export const getPersonnelDashboard = () =>
  apiClient.get<{ ok: boolean; data: PersonnelDashboardData }>('/dashboards/personnel/');
