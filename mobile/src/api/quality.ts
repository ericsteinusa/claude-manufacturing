import { apiClient } from './client';

export const getNcrs = (status?: string) =>
  apiClient.get('/quality/ncr/', { params: status ? { status } : {} });

export const getNcr = (id: number) =>
  apiClient.get(`/quality/ncr/${id}/`);

export const createNcr = (payload: {
  title: string;
  source?: string;
  severity?: string;
  product?: string;
  description?: string;
}) => apiClient.post('/quality/ncr/', payload);
