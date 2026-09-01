import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getMarketingDashboard } from '../../src/api/marketing';
import KpiCard from '../../src/components/KpiCard';
import OfflineBanner from '../../src/components/OfflineBanner';
import StatusBadge from '../../src/components/StatusBadge';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import type { MarketingDashboardData } from '../../src/api/marketing';

const fmtMoney = (n: number) =>
  `$${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function MarketingScreen() {
  const [data, setData] = useState<MarketingDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWithOfflineCache(
        'marketing_dashboard',
        async () => (await getMarketingDashboard()).data.data,
      );
      setData(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      setError('Could not load the marketing dashboard.');
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
            title="Active Campaigns"
            value={data.campaigns.active}
            subtitle={`${data.campaigns.planned} planned · ${data.campaigns.total} total`}
            accent="#1a73e8"
          />
          <KpiCard
            title="New Leads"
            value={data.leads.new_count}
            subtitle={`${data.leads.qualified} qualified of ${data.leads.total}`}
            accent={data.leads.new_count > 0 ? '#f9ab00' : '#34a853'}
          />
          <KpiCard
            title="Published Content"
            value={data.content.published}
            subtitle={`${data.content.draft} in draft of ${data.content.total}`}
            accent="#34a853"
          />

          <Text style={styles.sectionTitle}>Recent Campaigns</Text>
          {data.recent_campaigns.length === 0 ? (
            <Text style={styles.empty}>No recent campaigns.</Text>
          ) : (
            <View style={styles.campaignCard}>
              {data.recent_campaigns.map((c) => (
                <View key={c.id} style={styles.campaignRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.campaignName}>{c.name || 'Untitled Campaign'}</Text>
                    <Text style={styles.campaignMeta}>
                      {`${c.channel} · ${c.objective} · ${c.start_date} – ${c.end_date}`}
                    </Text>
                  </View>
                  <View style={styles.campaignRight}>
                    {c.budget > 0 && <Text style={styles.campaignBudget}>{fmtMoney(c.budget)}</Text>}
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
  screen:          { flex: 1, backgroundColor: '#f4f6fb' },
  error:           { color: '#d93025', margin: 16, textAlign: 'center' },
  cards:           { padding: 16 },
  sectionTitle:    { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginTop: 8, marginBottom: 10 },
  empty:           { textAlign: 'center', color: '#999', marginTop: 12 },
  campaignCard:    { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  campaignRow:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0', gap: 10 },
  campaignName:    { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  campaignMeta:    { fontSize: 12, color: '#888', marginTop: 2 },
  campaignRight:   { alignItems: 'flex-end', gap: 4 },
  campaignBudget:  { fontSize: 12, fontWeight: '700', color: '#1a1a2e' },
});
