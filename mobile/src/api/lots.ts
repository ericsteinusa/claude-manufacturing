import { apiClient } from './client';

export const getLots = (params?: { product_id?: number; status?: string }) =>
  apiClient.get('/lots/', { params });

export const getLotExpiry = (days = 30) =>
  apiClient.get('/lots/expiry/', { params: { days } });

export const getLot = (lotId: number) =>
  apiClient.get(`/lots/${lotId}/`);

export const createLot = (payload: {
  product_id: number;
  qty: number;
  lot_number?: string;
  received_date?: string;
  expiry_date?: string;
  notes?: string;
}) => apiClient.post('/lots/', payload);

export const updateLotStatus = (lotId: number, status: string, notes = '') =>
  apiClient.post(`/lots/${lotId}/status/`, { status, notes });

export const getSerials = (params?: { product_id?: number; lot_id?: number; status?: string }) =>
  apiClient.get('/serials/', { params });

export const createSerial = (payload: {
  serial_number: string;
  product_id: number;
  lot_id?: number;
  notes?: string;
}) => apiClient.post('/serials/', payload);

export const updateSerialStatus = (serialId: number, status: string, notes = '') =>
  apiClient.post(`/serials/${serialId}/status/`, { status, notes });
