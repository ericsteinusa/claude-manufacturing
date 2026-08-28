import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getSalesDashboard } from '../../src/api/sales';
import KpiCard from '../../src/components/KpiCard';
import StatusBadge from '../../src/components/StatusBadge';
import type { SalesDashboardData } from '../../src/api/sales';

const fmtMoney = (n: number) =>
  `$${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function SalesScreen() {
  const [data, setData] = useState<SalesDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getSalesDashboard();
      setData(res.data.data);
    } catch {
      setError('Could not load the sales dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openOrders = data ? data.orders.draft + data.orders.confirmed : 0;
  const targetPct = data && data.targets.total_target > 0
    ? Math.round((data.targets.total_actual / data.targets.total_target) * 100)
    : 0;

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !data ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" /> : null}

      {data ? (
        <View style={styles.cards}>
          <KpiCard
            title="Open Sales Orders"
            value={openOrders}
            subtitle={`${data.orders.total} total, ${data.orders.shipped} shipped`}
            accent="#1a73e8"
          />
          <KpiCard
            title="Order Value"
            value={fmtMoney(data.orders.total_value)}
            subtitle="Across all open and closed orders"
            accent="#34a853"
          />
          <KpiCard
            title="Quotes Won"
            value={`${data.quotes.won} / ${data.quotes.total}`}
            subtitle={fmtMoney(data.quotes.won_value)}
            accent="#1a73e8"
          />
          <KpiCard
            title="Target Attainment"
            value={`${targetPct}%`}
            subtitle={`${fmtMoney(data.targets.total_actual)} of ${fmtMoney(data.targets.total_target)}`}
            accent={targetPct >= 100 ? '#34a853' : '#f9ab00'}
          />

          <Text style={styles.sectionTitle}>Recent Orders</Text>
          {data.recent_orders.length === 0 ? (
            <Text style={styles.empty}>No sales orders yet.</Text>
          ) : (
            <View style={styles.ordersCard}>
              {data.recent_orders.map((so) => (
                <View key={so.id} style={styles.orderRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.orderNumber}>{so.so_number}</Text>
                    <Text style={styles.orderCustomer}>{so.customer || '—'}</Text>
                  </View>
                  <View style={styles.orderRight}>
                    <Text style={styles.orderTotal}>{fmtMoney(so.total)}</Text>
                    <StatusBadge status={so.status} />
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen:        { flex: 1, backgroundColor: '#f4f6fb' },
  error:         { color: '#d93025', margin: 16, textAlign: 'center' },
  cards:         { padding: 16 },
  sectionTitle:  { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginTop: 8, marginBottom: 10 },
  empty:         { textAlign: 'center', color: '#999', marginTop: 12 },
  ordersCard:    { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  orderRow:      { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  orderNumber:   { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  orderCustomer: { fontSize: 12, color: '#888', marginTop: 2 },
  orderRight:    { alignItems: 'flex-end', gap: 4 },
  orderTotal:    { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
});
