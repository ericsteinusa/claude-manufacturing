import { apiClient } from './client';

export const getWorkOrders = (status?: string) =>
  apiClient.get('/wo/', { params: status ? { status } : {} });

export const getWorkOrder = (id: number) =>
  apiClient.get(`/wo/${id}/`);

export const setWorkOrderStatus = (id: number, status: string) =>
  apiClient.post(`/wo/${id}/status/`, { status });
