import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10_000,
});

// Inject stored Bearer token on every request
apiClient.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('api_token');
  if (token) config.headers['Authorization'] = `Bearer ${token}`;
  return config;
});

export type ApiOk<T> = { ok: true; data: T };
export type ApiErr = { ok: false; error: string };
export type ApiResult<T> = ApiOk<T> | ApiErr;
