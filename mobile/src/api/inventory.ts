import { apiClient } from './client';

export const getInventory = (params?: { q?: string; status?: string }) =>
  apiClient.get('/inventory/', { params });

export const receiveStock = (productId: number, qty: number, reference = '', notes = '') =>
  apiClient.post('/inventory/receive/', { product_id: productId, qty, reference, notes });
