import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getLegalDashboard } from '../../src/api/legal';
import KpiCard from '../../src/components/KpiCard';
import OfflineBanner from '../../src/components/OfflineBanner';
import StatusBadge from '../../src/components/StatusBadge';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import type { LegalDashboardData } from '../../src/api/legal';

const fmtMoney = (n: number) =>
  `$${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function LegalScreen() {
  const [data, setData] = useState<LegalDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWithOfflineCache(
        'legal_dashboard',
        async () => (await getLegalDashboard()).data.data,
      );
      setData(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      setError('Could not load the legal dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <OfflineBanner isStale={isStale} cachedAt={cachedAt} />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !data ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" /> : null}

      {data ? (
        <View style={styles.cards}>
          <KpiCard
            title="Active Contracts"
            value={data.contracts.active}
            subtitle={`${data.contracts.total} total`}
            accent="#1a73e8"
          />
          <KpiCard
            title="Pending Compliance"
            value={data.compliance.pending}
            subtitle={`${data.compliance.completed} completed of ${data.compliance.total}`}
            accent={data.compliance.pending > 0 ? '#f9ab00' : '#34a853'}
          />
          <KpiCard
            title="Open Litigation"
            value={data.litigation.open}
            subtitle={`${data.litigation.total} total cases`}
            accent={data.litigation.open > 0 ? '#d93025' : '#34a853'}
          />

          <Text style={styles.sectionTitle}>Recent Contracts</Text>
          {data.recent_contracts.length === 0 ? (
            <Text style={styles.empty}>No recent contracts.</Text>
          ) : (
            <View style={styles.contractCard}>
              {data.recent_contracts.map((c) => (
                <View key={c.id} style={styles.contractRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.contractTitle}>{c.title}</Text>
                    <Text style={styles.contractMeta}>
                      {`${c.counterparty} · ${c.contract_type} · ends ${c.end_date}`}
                    </Text>
                  </View>
                  <View style={styles.contractRight}>
                    {c.value > 0 && <Text style={styles.contractValue}>{fmtMoney(c.value)}</Text>}
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
  screen:         { flex: 1, backgroundColor: '#f4f6fb' },
  error:          { color: '#d93025', margin: 16, textAlign: 'center' },
  cards:          { padding: 16 },
  sectionTitle:   { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginTop: 8, marginBottom: 10 },
  empty:          { textAlign: 'center', color: '#999', marginTop: 12 },
  contractCard:   { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  contractRow:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0', gap: 10 },
  contractTitle:  { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  contractMeta:   { fontSize: 12, color: '#888', marginTop: 2 },
  contractRight:  { alignItems: 'flex-end', gap: 4 },
  contractValue:  { fontSize: 12, fontWeight: '700', color: '#1a1a2e' },
});
