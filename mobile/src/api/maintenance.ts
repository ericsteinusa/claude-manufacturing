import { apiClient } from './client';

export const getMaintWorkOrders = (status?: string) =>
  apiClient.get('/maint/wo/', { params: status ? { status } : {} });

export const getMaintWorkOrder = (id: number) =>
  apiClient.get(`/maint/wo/${id}/`);

export const completeMaintWorkOrder = (id: number) =>
  apiClient.post(`/maint/wo/${id}/complete/`);
