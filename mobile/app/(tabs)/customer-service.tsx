import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getCustomerServiceDashboard } from '../../src/api/customerService';
import KpiCard from '../../src/components/KpiCard';
import OfflineBanner from '../../src/components/OfflineBanner';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import type { CustomerServiceDashboardData } from '../../src/api/customerService';

export default function CustomerServiceScreen() {
  const [data, setData] = useState<CustomerServiceDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWithOfflineCache(
        'cs_dashboard',
        async () => (await getCustomerServiceDashboard()).data.data,
      );
      setData(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      setError('Could not load the customer service dashboard.');
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
            title="Open Tickets"
            value={data.open_count}
            subtitle={`${data.total} logged in the last year`}
            accent={data.open_count > 0 ? '#f9ab00' : '#34a853'}
          />
          <KpiCard
            title="Completion Rate"
            value={`${data.completion_rate}%`}
            subtitle={`${data.completed_count} completed`}
            accent={data.completion_rate >= 80 ? '#34a853' : '#f9ab00'}
          />
          <KpiCard
            title="Avg Resolution Time"
            value={data.avg_resolution != null ? `${data.avg_resolution}d` : '—'}
            subtitle="Days to close a ticket"
            accent="#1a73e8"
          />
          <KpiCard
            title="Avg Age of Open Tickets"
            value={data.avg_age_open != null ? `${data.avg_age_open}d` : '—'}
            subtitle="Days since opened"
            accent={data.avg_age_open != null && data.avg_age_open > 14 ? '#d93025' : '#1a73e8'}
          />

          <Text style={styles.sectionTitle}>Recent Tickets</Text>
          {data.recent_tickets.length === 0 ? (
            <Text style={styles.empty}>No tickets yet.</Text>
          ) : (
            <View style={styles.ticketCard}>
              {data.recent_tickets.map((t) => (
                <View key={t.id} style={styles.ticketRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.ticketCall} numberOfLines={2}>{t.call}</Text>
                    <Text style={styles.ticketMeta}>
                      {(t.customer_name || 'Unknown customer')}{t.call_date ? ` · ${t.call_date}` : ''}
                    </Text>
                  </View>
                  <View style={[styles.badge, t.completion_box ? styles.badgeDone : styles.badgeOpen]}>
                    <Text style={styles.badgeText}>{t.completion_box ? 'Closed' : 'Open'}</Text>
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
  screen:       { flex: 1, backgroundColor: '#f4f6fb' },
  error:        { color: '#d93025', margin: 16, textAlign: 'center' },
  cards:        { padding: 16 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginTop: 8, marginBottom: 10 },
  empty:        { textAlign: 'center', color: '#999', marginTop: 12 },
  ticketCard:   { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  ticketRow:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0', gap: 10 },
  ticketCall:   { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  ticketMeta:   { fontSize: 12, color: '#888', marginTop: 2 },
  badge:        { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  badgeOpen:    { backgroundColor: '#fff3cd' },
  badgeDone:    { backgroundColor: '#d4edda' },
  badgeText:    { fontSize: 10, fontWeight: '700', color: '#333' },
});
