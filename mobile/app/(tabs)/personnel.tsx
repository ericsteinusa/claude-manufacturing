import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getPersonnelDashboard } from '../../src/api/personnel';
import KpiCard from '../../src/components/KpiCard';
import type { PersonnelDashboardData } from '../../src/api/personnel';

export default function PersonnelScreen() {
  const [data, setData] = useState<PersonnelDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getPersonnelDashboard();
      setData(res.data.data);
    } catch {
      setError('Could not load the personnel dashboard.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const maxDeptCount = data
    ? Math.max(1, ...data.by_dept.map((d) => d.count))
    : 1;

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
            title="Total Employees"
            value={data.employees.total}
            subtitle="Across all departments"
            accent="#1a73e8"
          />
          <KpiCard
            title="Time Off Pending"
            value={data.time_off.pending}
            subtitle={`${data.time_off.approved} approved`}
            accent={data.time_off.pending > 0 ? '#f9ab00' : '#34a853'}
          />

          <Text style={styles.sectionTitle}>Headcount by Department</Text>
          <View style={styles.deptCard}>
            {data.by_dept.map((d) => (
              <View key={d.dept_name} style={styles.deptRow}>
                <Text style={styles.deptLabel} numberOfLines={1}>{d.dept_name}</Text>
                <View style={styles.deptBarTrack}>
                  <View style={[styles.deptBarFill, { width: `${(d.count / maxDeptCount) * 100}%` }]} />
                </View>
                <Text style={styles.deptCount}>{d.count}</Text>
              </View>
            ))}
          </View>

          <Text style={styles.sectionTitle}>Recent Employees</Text>
          {data.recent_employees.length === 0 ? (
            <Text style={styles.empty}>No employees found.</Text>
          ) : (
            <View style={styles.empCard}>
              {data.recent_employees.map((emp) => (
                <View key={emp.id} style={styles.empRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.empName}>{`${emp.first_name} ${emp.last_name}`}</Text>
                    <Text style={styles.empMeta}>{emp.job_title || '—'}</Text>
                  </View>
                  <Text style={styles.empDept}>{emp.dept_name || '—'}</Text>
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
  deptCard:      { backgroundColor: '#fff', borderRadius: 10, padding: 16, elevation: 2, marginBottom: 8 },
  deptRow:       { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  deptLabel:     { fontSize: 12, color: '#555', width: 100 },
  deptBarTrack:  { flex: 1, height: 8, backgroundColor: '#eef1f6', borderRadius: 4, overflow: 'hidden' },
  deptBarFill:   { height: '100%', backgroundColor: '#1a73e8', borderRadius: 4 },
  deptCount:     { fontSize: 12, fontWeight: '700', color: '#1a1a2e', width: 24, textAlign: 'right' },
  empCard:       { backgroundColor: '#fff', borderRadius: 10, padding: 4, elevation: 2 },
  empRow:        { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#f0f0f0' },
  empName:       { fontSize: 13, fontWeight: '700', color: '#1a1a2e' },
  empMeta:       { fontSize: 12, color: '#888', marginTop: 2 },
  empDept:       { fontSize: 12, color: '#555' },
});
