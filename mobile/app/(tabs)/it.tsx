import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getItDashboard } from '../../src/api/it';
import KpiCard from '../../src/components/KpiCard';
import OfflineBanner from '../../src/components/OfflineBanner';
import StatusBadge from '../../src/components/StatusBadge';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import type { ItDashboardData } from '../../src/api/it';

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#d93025',
  high:     '#f9ab00',
  medium:   '#1a73e8',
  low:      '#888',
};

function PriorityTag({ priority }: { priority: string }) {
  const color = PRIORITY_COLORS[priority.trim().toLowerCase()] ?? '#888';
  return (
    <Text style={[styles.priority, { color }]}>{priority.toUpperCase()}</Text>
  );
}

export default function ItScreen() {
  const [data, setData] = useState<ItDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWithOfflineCache(
        'it_dashboard',
        async () => (await getItDashboard()).data.data,
      );
      setData(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      setError('Could not load the IT dashboard.');
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
            value={data.tickets.open_count}
            subtitle={`${data.tickets.total_count} total`}
            accent={data.tickets.open_count > 0 ? '#f9ab00' : '#34a853'}
          />
          <KpiCard
            title="Critical Tickets"
            value={data.tickets.critical_count}
            subtitle="Unresolved, critical priority"
            accent={data.tickets.critical_count > 0 ? '#d93025' : '#34a853'}
          />
          <KpiCard
            title="In Progress"
            value={data.tickets.in_progress_count}
            subtitle="Being worked"
            accent="#1a73e8"
          />
          <KpiCard
            title="Assets in Repair"
            value={data.assets.repair}
            subtitle={`${data.assets.active} active of ${data.assets.total} total`}
            accent={data.assets.repair > 0 ? '#f9ab00' : '#34a853'}
          />

          <Text style={styles.sectionTitle}>Recent Tickets</Text>
          {data.recent_tickets.length === 0 ? (
            <Text style={styles.empty}>No recent tickets.</Text>
          ) : (
            <View style={styles.ticketCard}>
              {data.recent_tickets.map((t) => (
                <View key={t.id} style={styles.ticketRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.ticketNumber}>{t.ticket_number}</Text>
                    <Text style={styles.ticketMeta}>
                      {`${t.requester} · ${t.department} · ${t.issue_type}`}
                    </Text>
                    <PriorityTag priority={t.priority} />
                  </View>
                  <View style={styles.ticketRight}>
                    <StatusBadge status={t.status} />
                    <Text style={styles.ticketDate}>{t.submitted_date}</Text>
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
  ticketCard:    { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  ticketRow:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0', gap: 10 },
  ticketNumber:  { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  ticketMeta:    { fontSize: 12, color: '#888', marginTop: 2 },
  priority:      { fontSize: 11, fontWeight: '700', marginTop: 4, letterSpacing: 0.5 },
  ticketRight:   { alignItems: 'flex-end', gap: 4 },
  ticketDate:    { fontSize: 11, color: '#999' },
});
