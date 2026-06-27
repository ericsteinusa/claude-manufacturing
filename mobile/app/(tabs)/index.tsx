import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getDashboard } from '../../src/api/dashboard';
import KpiCard from '../../src/components/KpiCard';
import { useAuth } from '../../src/hooks/useAuth';
import type { DashboardData } from '../../src/api/dashboard';

export default function DashboardScreen() {
  const { user, logout } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getDashboard();
      setData(res.data.data);
    } catch {
      setError('Could not load dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const activeWOs = data
    ? (data.wo.by_status['open'] ?? 0) + (data.wo.by_status['in_progress'] ?? 0)
    : 0;
  const openPOs = data
    ? (data.po.by_status['draft'] ?? 0) + (data.po.by_status['pending_approval'] ?? 0) + (data.po.by_status['sent'] ?? 0)
    : 0;

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <View style={styles.header}>
        <Text style={styles.greeting}>
          Hello, {user?.role ?? 'User'}
        </Text>
        <TouchableOpacity onPress={logout}>
          <Text style={styles.logoutBtn}>Sign out</Text>
        </TouchableOpacity>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !data ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" /> : null}

      {data ? (
        <View style={styles.cards}>
          <KpiCard
            title="Active Work Orders"
            value={activeWOs}
            subtitle={`${data.wo.by_status['completed'] ?? 0} completed`}
            accent="#1a73e8"
          />
          <KpiCard
            title="Open Purchase Orders"
            value={openPOs}
            subtitle={`${data.po.overdue} overdue`}
            accent={data.po.overdue > 0 ? '#d93025' : '#34a853'}
          />
          <KpiCard
            title="Inventory Alerts"
            value={data.inventory.alert_count}
            subtitle="items at or below reorder point"
            accent={data.inventory.alert_count > 0 ? '#f9ab00' : '#34a853'}
          />
          <KpiCard
            title="CS Open Tickets"
            value={data.cs.open}
            subtitle={`${data.cs.today} opened today`}
            accent="#1a73e8"
          />
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen:    { flex: 1, backgroundColor: '#f4f6fb' },
  header:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16 },
  greeting:  { fontSize: 16, fontWeight: '600', color: '#1a1a2e' },
  logoutBtn: { fontSize: 14, color: '#d93025', fontWeight: '600' },
  error:     { color: '#d93025', margin: 16, textAlign: 'center' },
  cards:     { padding: 16 },
});
