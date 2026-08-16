import { apiClient } from './client';

export const getWorkOrders = (status?: string) =>
  apiClient.get('/wo/', { params: status ? { status } : {} });

export const getWorkOrder = (id: number) =>
  apiClient.get(`/wo/${id}/`);

export const setWorkOrderStatus = (id: number, status: string) =>
  apiClient.post(`/wo/${id}/status/`, { status });

export const getWoOperations = (woId: number) =>
  apiClient.get(`/wo/${woId}/operations/`);

export const startWoOperation = (woId: number, seq: number) =>
  apiClient.post(`/wo/${woId}/operations/${seq}/start/`);

export const completeWoOperation = (woId: number, seq: number, actualHours: number) =>
  apiClient.post(`/wo/${woId}/operations/${seq}/complete/`, { actual_hours: actualHours });

export const getWoCost = (woId: number) =>
  apiClient.get(`/wo/${woId}/cost/`);

export const computeWoCost = (woId: number) =>
  apiClient.post(`/wo/${woId}/cost/compute/`);

export const getWoAssignees = () =>
  apiClient.get('/wo/assignees/');

export const assignWorkOrder = (woId: number, assignedTo: string) =>
  apiClient.post(`/wo/${woId}/assign/`, { assigned_to: assignedTo });
