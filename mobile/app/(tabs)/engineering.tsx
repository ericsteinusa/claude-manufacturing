import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getEngineeringDashboard } from '../../src/api/engineering';
import KpiCard from '../../src/components/KpiCard';
import StatusBadge from '../../src/components/StatusBadge';
import type { EngineeringDashboardData } from '../../src/api/engineering';

export default function EngineeringScreen() {
  const [data, setData] = useState<EngineeringDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getEngineeringDashboard();
      setData(res.data.data);
    } catch {
      setError('Could not load the engineering dashboard.');
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
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !data ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" /> : null}

      {data ? (
        <View style={styles.cards}>
          <KpiCard
            title="Active Projects"
            value={data.projects.in_progress}
            subtitle={`${data.projects.total} total, ${data.projects.planning} planning`}
            accent="#1a73e8"
          />
          <KpiCard
            title="Overdue Tasks"
            value={data.tasks.overdue_tasks}
            subtitle={`${data.tasks.active_tasks} active, ${data.tasks.open_tasks} open`}
            accent={data.tasks.overdue_tasks > 0 ? '#d93025' : '#34a853'}
          />
          <KpiCard
            title="Pending ECRs"
            value={data.ecrs.pending}
            subtitle={`${data.ecrs.approved} approved, ${data.ecrs.draft} draft`}
            accent={data.ecrs.pending > 0 ? '#f9ab00' : '#34a853'}
          />

          <Text style={styles.sectionTitle}>Recent Projects</Text>
          {data.recent_projects.length === 0 ? (
            <Text style={styles.empty}>No projects yet.</Text>
          ) : (
            <View style={styles.projectCard}>
              {data.recent_projects.map((p) => (
                <View key={p.id} style={styles.projectRow}>
                  <View style={styles.projectHeader}>
                    <Text style={styles.projectNumber}>{p.project_number}</Text>
                    <StatusBadge status={p.status} />
                  </View>
                  <Text style={styles.projectTitle} numberOfLines={1}>{p.title}</Text>
                  <View style={styles.projectFooter}>
                    <Text style={styles.projectMeta}>{p.engineer || 'Unassigned'}</Text>
                    <Text style={styles.projectMeta}>
                      {`${p.done_count}/${p.task_count} tasks`}
                      {p.overdue_tasks > 0 ? ` · ${p.overdue_tasks} overdue` : ''}
                    </Text>
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
  projectCard:    { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  projectRow:     { paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  projectHeader:  { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  projectNumber:  { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  projectTitle:   { fontSize: 12, color: '#555', marginBottom: 4 },
  projectFooter:  { flexDirection: 'row', justifyContent: 'space-between' },
  projectMeta:    { fontSize: 11, color: '#888' },
});
