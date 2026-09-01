import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getPayrollDashboard } from '../../src/api/payroll';
import KpiCard from '../../src/components/KpiCard';
import OfflineBanner from '../../src/components/OfflineBanner';
import StatusBadge from '../../src/components/StatusBadge';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import type { PayrollDashboardData } from '../../src/api/payroll';

const fmtMoney = (n: number) =>
  `$${(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function PayrollScreen() {
  const [data, setData] = useState<PayrollDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchWithOfflineCache(
        'payroll_dashboard',
        async () => (await getPayrollDashboard()).data.data,
      );
      setData(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      setError('Could not load the payroll dashboard.');
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
            title="YTD Gross Payroll"
            value={fmtMoney(data.counts.ytd_gross)}
            subtitle={`${data.counts.total_runs} runs this year`}
            accent="#1a73e8"
          />
          <KpiCard
            title="Employees w/ Pay Rates"
            value={data.counts.emp_with_rates}
            subtitle={`${data.counts.total_people} total people`}
            accent="#34a853"
          />
          <KpiCard
            title="Active Deduction Types"
            value={data.counts.active_ded_types}
            subtitle="Configured deductions"
            accent="#1a73e8"
          />

          <Text style={styles.sectionTitle}>Recent Payroll Runs</Text>
          {data.recent_runs.length === 0 ? (
            <Text style={styles.empty}>No recent payroll runs.</Text>
          ) : (
            <View style={styles.runCard}>
              {data.recent_runs.map((r) => (
                <View key={r.id} style={styles.runRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.runPeriod}>
                      {`${r.pay_period_start} – ${r.pay_period_end}`}
                    </Text>
                    <Text style={styles.runMeta}>
                      {`${r.emp_count} employees · run ${r.run_date}`}
                    </Text>
                    <Text style={styles.runMeta}>
                      {`Gross ${fmtMoney(r.total_gross)} · Net ${fmtMoney(r.total_net)}`}
                    </Text>
                  </View>
                  <View style={styles.runRight}>
                    <StatusBadge status={r.status} />
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
  runCard:       { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  runRow:        { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0', gap: 10 },
  runPeriod:     { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  runMeta:       { fontSize: 12, color: '#888', marginTop: 2 },
  runRight:      { alignItems: 'flex-end', gap: 4 },
});
