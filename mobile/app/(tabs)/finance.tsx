import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getFinancialDashboard } from '../../src/api/finance';
import KpiCard from '../../src/components/KpiCard';
import OfflineBanner from '../../src/components/OfflineBanner';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import type { FinancialDashboardData } from '../../src/api/finance';

const AGING_LABELS: [keyof FinancialDashboardData['ar_aging'], string][] = [
  ['current', 'Current'],
  ['1_30', '1–30 days'],
  ['31_60', '31–60 days'],
  ['61_90', '61–90 days'],
  ['over_90', 'Over 90 days'],
];

const fmtMoney = (n: number) =>
  `$${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function FinanceScreen() {
  const [data, setData] = useState<FinancialDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWithOfflineCache(
        'finance_dashboard',
        async () => (await getFinancialDashboard()).data.data,
      );
      setData(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      setError('Could not load the financial dashboard.');
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
            title="Cash Position"
            value={fmtMoney(data.cash_position)}
            subtitle="Across active bank accounts"
            accent="#34a853"
          />
          <KpiCard
            title="Days Sales Outstanding"
            value={data.dso}
            subtitle="90-day AR collection window"
            accent="#1a73e8"
          />
          <KpiCard
            title="Days Payable Outstanding"
            value={data.dpo}
            subtitle="90-day AP payment window"
            accent="#1a73e8"
          />
          <KpiCard
            title="Gross Margin"
            value={`${data.gross_margin_pct}%`}
            subtitle="Year to date"
            accent={data.gross_margin_pct >= 0 ? '#34a853' : '#d93025'}
          />
          <KpiCard
            title="AP Due This Week"
            value={fmtMoney(data.ap_due_week)}
            subtitle="Payments due in the next 7 days"
            accent={data.ap_due_week > 0 ? '#f9ab00' : '#34a853'}
          />

          <Text style={styles.sectionTitle}>AR Aging</Text>
          <View style={styles.agingCard}>
            {AGING_LABELS.map(([key, label]) => (
              <View key={key} style={styles.agingRow}>
                <Text style={styles.agingLabel}>{label}</Text>
                <Text style={[styles.agingValue, key === 'over_90' && data.ar_aging[key] > 0 && styles.agingOverdue]}>
                  {fmtMoney(data.ar_aging[key])}
                </Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen:       { flex: 1, backgroundColor: '#f4f6fb' },
  error:        { color: '#d93025', margin: 16, textAlign: 'center' },
  cards:        { padding: 16 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginTop: 8, marginBottom: 10 },
  agingCard:    { backgroundColor: '#fff', borderRadius: 10, padding: 16, elevation: 2 },
  agingRow:     { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  agingLabel:   { fontSize: 13, color: '#555' },
  agingValue:   { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  agingOverdue: { color: '#d93025' },
});
