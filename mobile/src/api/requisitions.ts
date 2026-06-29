import { apiClient } from './client';

export const getRequisitions = () =>
  apiClient.get('/req/');

export const createRequisition = (purpose: string, notes = '') =>
  apiClient.post('/req/', { purpose, notes });

export const addRequisitionItem = (
  req_id: number,
  item: { description: string; quantity: number; unit_price: number; notes?: string }
) => apiClient.post(`/req/${req_id}/items/`, item);

export const submitRequisition = (req_id: number) =>
  apiClient.post(`/req/${req_id}/submit/`);

export const getPendingRequisitions = () =>
  apiClient.get('/req/pending/');

export const decideRequisition = (
  req_id: number,
  decision: 'approve' | 'deny',
  comment = ''
) => apiClient.post(`/req/${req_id}/decide/`, { decision, comment });
