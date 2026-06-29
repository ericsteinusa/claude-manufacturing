import { apiClient } from './client';

export const getStatus = () =>
  apiClient.get('/time-clock/status/');

export const clockIn = (notes = '') =>
  apiClient.post('/time-clock/clock-in/', { notes });

export const clockOut = () =>
  apiClient.post('/time-clock/clock-out/');

export const getHours = (period: 'today' | 'week' | 'month' = 'week') =>
  apiClient.get('/time-clock/hours/', { params: { period } });

export const getTimeOffRequests = () =>
  apiClient.get('/time-off/');

export const submitTimeOff = (data: {
  start_date: string;
  end_date: string;
  request_type: string;
  notes?: string;
}) => apiClient.post('/time-off/', data);
