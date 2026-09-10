import React, { useCallback, useEffect, useState } from 'react';
import { Slot, useRouter, useSegments } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import { AuthContext } from '../src/hooks/useAuth';
import { login as apiLogin, logout as apiLogout } from '../src/api/auth';
import type { User } from '../src/api/auth';
import { flushQueue } from '../src/offline/queue';

export default function RootLayout() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    AsyncStorage.getItem('api_token').then((t) => {
      if (t) {
        AsyncStorage.getItem('api_user').then((u) => {
          if (u) setUser(JSON.parse(u));
          setToken(t);
        });
      }
      setReady(true);
    });
  }, []);

  useEffect(() => {
    if (!ready) return;
    const inAuth = segments[0] === '(auth)';
    if (!token && !inAuth) router.replace('/(auth)/login');
    if (token && inAuth) router.replace('/(tabs)');
  }, [token, ready, segments, router]);

  // Replay any offline-queued mutations (see src/offline/queue.ts) the
  // moment connectivity comes back, regardless of which screen the user
  // happens to be on — a queued clock-out shouldn't wait for the user to
  // revisit the Time Clock screen before it syncs.
  useEffect(() => {
    if (!token) return;
    let wasOffline = false;
    const unsubscribe = NetInfo.addEventListener((state) => {
      const isOnline = state.isConnected !== false && state.isInternetReachable !== false;
      if (isOnline && wasOffline) {
        flushQueue().catch(() => { /* will retry on the next reconnect event */ });
      }
      wasOffline = !isOnline;
    });
    return unsubscribe;
  }, [token]);

  const login = useCallback(async (email: string, password: string, totpCode?: string) => {
    const res = await apiLogin(email, password, totpCode);
    const { token: t, user: u } = res.data.data;
    await AsyncStorage.setItem('api_token', t);
    await AsyncStorage.setItem('api_user', JSON.stringify(u));
    setToken(t);
    setUser(u);
  }, []);

  const logout = useCallback(async () => {
    try { await apiLogout(); } catch { /* ignore */ }
    await AsyncStorage.multiRemove(['api_token', 'api_user']);
    setToken(null);
    setUser(null);
  }, []);

  if (!ready) return null;

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      <Slot />
    </AuthContext.Provider>
  );
}
