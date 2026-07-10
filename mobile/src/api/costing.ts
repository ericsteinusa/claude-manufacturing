import { apiClient } from './client';

export const getProductCost = (productId: number) =>
  apiClient.get(`/costs/${productId}/`);

export const rollStandardCost = (productId: number) =>
  apiClient.post(`/costs/${productId}/roll/`);

export const getCostHistory = (productId: number) =>
  apiClient.get(`/costs/${productId}/history/`);

export const getGlAccounts = () =>
  apiClient.get('/gl-accounts/');

export const getWorkcenters = () =>
  apiClient.get('/workcenters/');

export const getProductRouting = (productId: number) =>
  apiClient.get(`/routing/${productId}/`);
