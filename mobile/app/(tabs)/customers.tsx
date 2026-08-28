import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getCustomersDashboard } from '../../src/api/customers';
import KpiCard from '../../src/components/KpiCard';
import StatusBadge from '../../src/components/StatusBadge';
import type { CustomersDashboardData } from '../../src/api/customers';

const fmtMoney = (n: number) =>
  `$${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function CustomersScreen() {
  const [data, setData] = useState<CustomersDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getCustomersDashboard();
      setData(res.data.data);
    } catch {
      setError('Could not load the customers dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const atRisk = data ? data.accounts.hold + data.accounts.suspended : 0;

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
            title="Accounts at Risk"
            value={atRisk}
            subtitle={`${data.accounts.total} total accounts`}
            accent={atRisk > 0 ? '#d93025' : '#34a853'}
          />
          <KpiCard
            title="Total Credit Exposure"
            value={fmtMoney(data.accounts.total_exposure)}
            subtitle={`${data.accounts.good} in good standing`}
            accent="#1a73e8"
          />
          <KpiCard
            title="Pending Applications"
            value={data.applications.pending}
            subtitle={`${data.applications.total} total`}
            accent={data.applications.pending > 0 ? '#f9ab00' : '#34a853'}
          />
          <KpiCard
            title="Open Collections"
            value={data.collections.open}
            subtitle={`${data.collections.total} total`}
            accent={data.collections.open > 0 ? '#d93025' : '#34a853'}
          />

          <Text style={styles.sectionTitle}>Recent Collection Activity</Text>
          {data.recent_collections.length === 0 ? (
            <Text style={styles.empty}>No open collection activity.</Text>
          ) : (
            <View style={styles.collCard}>
              {data.recent_collections.map((c) => (
                <View key={c.id} style={styles.collRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.collCustomer}>{c.customer_name || 'Unknown'}</Text>
                    <Text style={styles.collMeta}>{`${c.activity_type} · ${c.activity_date}`}</Text>
                  </View>
                  <View style={styles.collRight}>
                    {c.amount_promised != null && (
                      <Text style={styles.collAmount}>{fmtMoney(c.amount_promised)}</Text>
                    )}
                    <StatusBadge status={c.status} />
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
  collCard:      { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  collRow:       { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0', gap: 10 },
  collCustomer:  { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  collMeta:      { fontSize: 12, color: '#888', marginTop: 2 },
  collRight:     { alignItems: 'flex-end', gap: 4 },
  collAmount:    { fontSize: 12, fontWeight: '700', color: '#1a1a2e' },
});
