import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getAccountingDashboard } from '../../src/api/accounting';
import KpiCard from '../../src/components/KpiCard';
import OfflineBanner from '../../src/components/OfflineBanner';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import type { AccountingDashboardData } from '../../src/api/accounting';

const fmtMoney = (n: number) =>
  `$${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function AccountingScreen() {
  const [data, setData] = useState<AccountingDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWithOfflineCache(
        'accounting_dashboard',
        async () => (await getAccountingDashboard()).data.data,
      );
      setData(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      setError('Could not load the accounting dashboard.');
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
            title="AP Outstanding"
            value={fmtMoney(data.ap.total_outstanding)}
            subtitle={`${data.ap.open_count} open, ${data.ap.overdue_count} overdue`}
            accent={data.ap.overdue_count > 0 ? '#d93025' : '#34a853'}
          />
          <KpiCard
            title="AR Outstanding"
            value={fmtMoney(data.ar.total_outstanding)}
            subtitle={`${data.ar.open_count} open, ${data.ar.overdue_count} overdue`}
            accent={data.ar.overdue_count > 0 ? '#d93025' : '#34a853'}
          />
          <KpiCard
            title="AP Invoiced (All Time)"
            value={fmtMoney(data.ap.total_invoiced)}
            subtitle={`${data.ap.total_invoices} invoices`}
            accent="#1a73e8"
          />
          <KpiCard
            title="AR Invoiced (All Time)"
            value={fmtMoney(data.ar.total_invoiced)}
            subtitle={`${data.ar.total_invoices} invoices`}
            accent="#1a73e8"
          />

          <Text style={styles.sectionTitle}>Recent GL Journals</Text>
          {data.recent_journals.length === 0 ? (
            <Text style={styles.empty}>No journal entries yet.</Text>
          ) : (
            <View style={styles.journalCard}>
              {data.recent_journals.map((j) => (
                <View key={j.id} style={styles.journalRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.journalRef}>{j.reference}</Text>
                    <Text style={styles.journalDesc} numberOfLines={1}>{j.description}</Text>
                    <Text style={styles.journalDate}>{j.journal_date}</Text>
                  </View>
                  <View style={styles.journalRight}>
                    <Text style={styles.journalTotal}>{fmtMoney(j.total_debit)}</Text>
                    <View style={[styles.badge, j.posted ? styles.badgePosted : styles.badgeDraft]}>
                      <Text style={styles.badgeText}>{j.posted ? 'Posted' : 'Draft'}</Text>
                    </View>
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
  journalCard:   { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  journalRow:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  journalRef:    { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  journalDesc:   { fontSize: 12, color: '#666', marginTop: 2 },
  journalDate:   { fontSize: 11, color: '#999', marginTop: 2 },
  journalRight:  { alignItems: 'flex-end', gap: 4 },
  journalTotal:  { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  badge:         { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  badgePosted:   { backgroundColor: '#d4edda' },
  badgeDraft:    { backgroundColor: '#f0f0f0' },
  badgeText:     { fontSize: 10, fontWeight: '700', color: '#333' },
});
