import { apiClient } from './client';

export interface RecentProject {
  id: number;
  project_number: string;
  title: string;
  engineer: string;
  status: string;
  due_date: string | null;
  task_count: number;
  done_count: number;
  overdue_tasks: number;
}

export interface EngineeringDashboardData {
  projects: {
    planning: number;
    in_progress: number;
    on_hold: number;
    completed: number;
    total: number;
  };
  ecrs: {
    draft: number;
    pending: number;
    approved: number;
    total: number;
  };
  tasks: {
    open_tasks: number;
    active_tasks: number;
    overdue_tasks: number;
  };
  recent_projects: RecentProject[];
}

export const getEngineeringDashboard = () =>
  apiClient.get<{ ok: boolean; data: EngineeringDashboardData }>('/dashboards/engineering/');
