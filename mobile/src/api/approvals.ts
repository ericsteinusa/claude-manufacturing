import { apiClient } from './client';

export const getPendingSteps = () =>
  apiClient.get('/approvals/pending/');

export const decideStep = (stepId: number, decision: 'approved' | 'rejected', notes = '') =>
  apiClient.post(`/approvals/steps/${stepId}/decide/`, { decision, notes });
