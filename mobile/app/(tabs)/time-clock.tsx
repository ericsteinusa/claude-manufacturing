import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, RefreshControl, ScrollView,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { clockIn, clockOut, getHours, getStatus } from '../../src/api/timeclock';

type Period = 'today' | 'week' | 'month';

export default function TimeClockScreen() {
  const [clockedIn, setClockedIn] = useState(false);
  const [currentEntry, setCurrentEntry] = useState<any>(null);
  const [hours, setHours] = useState<any>(null);
  const [period, setPeriod] = useState<Period>('week');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statusRes, hoursRes] = await Promise.all([
        getStatus(),
        getHours(period),
      ]);
      setClockedIn(statusRes.data.data.clocked_in);
      setCurrentEntry(statusRes.data.data.entry);
      setHours(hoursRes.data.data);
    } catch {
      Alert.alert('Error', 'Could not load time clock data.');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const handleToggle = async () => {
    setActionLoading(true);
    try {
      if (clockedIn) {
        await clockOut();
        Alert.alert('Clocked Out', 'Your time has been recorded.');
      } else {
        await clockIn();
        Alert.alert('Clocked In', 'Have a great shift!');
      }
      await load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Action failed.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <ScrollView
      style={styles.screen}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <View style={styles.statusCard}>
        <Text style={styles.statusLabel}>
          {clockedIn ? 'Currently Clocked In' : 'Not Clocked In'}
        </Text>
        {currentEntry && (
          <Text style={styles.statusTime}>Since {currentEntry.clock_in?.substring(11, 16)}</Text>
        )}
        <TouchableOpacity
          style={[styles.toggleBtn, clockedIn ? styles.clockOutBtn : styles.clockInBtn]}
          onPress={handleToggle}
          disabled={actionLoading}
        >
          {actionLoading
            ? <ActivityIndicator color="#fff" />
            : <Text style={styles.toggleBtnText}>{clockedIn ? 'Clock Out' : 'Clock In'}</Text>
          }
        </TouchableOpacity>
      </View>

      <View style={styles.periodRow}>
        {(['today', 'week', 'month'] as Period[]).map((p) => (
          <TouchableOpacity
            key={p}
            style={[styles.periodBtn, period === p && styles.periodBtnActive]}
            onPress={() => setPeriod(p)}
          >
            <Text style={[styles.periodLabel, period === p && styles.periodLabelActive]}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {hours && (
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Hours This {period.charAt(0).toUpperCase() + period.slice(1)}</Text>
          <Text style={styles.totalHours}>{hours.total_hours_fmt}</Text>
          <Text style={styles.dateRange}>{hours.date_from} — {hours.date_to}</Text>
          {hours.entries?.map((e: any) => (
            <View key={e.id} style={styles.entryRow}>
              <Text style={styles.entryDate}>{e.clock_in?.substring(0, 10)}</Text>
              <Text style={styles.entryTime}>
                {e.clock_in?.substring(11, 16)} → {e.clock_out ? e.clock_out.substring(11, 16) : 'ongoing'}
              </Text>
              <Text style={styles.entryHours}>{e.hours_fmt}</Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen:         { flex: 1, backgroundColor: '#f4f6fb' },
  statusCard:     { margin: 16, backgroundColor: '#fff', borderRadius: 16, padding: 24, alignItems: 'center', elevation: 2 },
  statusLabel:    { fontSize: 18, fontWeight: '700', color: '#1a1a2e' },
  statusTime:     { fontSize: 13, color: '#666', marginTop: 4 },
  toggleBtn:      { marginTop: 20, paddingHorizontal: 48, paddingVertical: 16, borderRadius: 30 },
  clockInBtn:     { backgroundColor: '#34a853' },
  clockOutBtn:    { backgroundColor: '#d93025' },
  toggleBtnText:  { color: '#fff', fontWeight: '700', fontSize: 16 },
  periodRow:      { flexDirection: 'row', marginHorizontal: 16, marginBottom: 8, gap: 8 },
  periodBtn:      { flex: 1, padding: 10, borderRadius: 8, backgroundColor: '#fff', alignItems: 'center' },
  periodBtnActive: { backgroundColor: '#1a73e8' },
  periodLabel:    { fontWeight: '600', color: '#555' },
  periodLabelActive: { color: '#fff' },
  summaryCard:    { margin: 16, backgroundColor: '#fff', borderRadius: 16, padding: 20, elevation: 2 },
  summaryTitle:   { fontSize: 14, color: '#666', fontWeight: '500' },
  totalHours:     { fontSize: 36, fontWeight: '800', color: '#1a73e8', marginVertical: 4 },
  dateRange:      { fontSize: 12, color: '#999', marginBottom: 12 },
  entryRow:       { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderTopWidth: 1, borderTopColor: '#f0f0f0' },
  entryDate:      { fontSize: 13, color: '#555', flex: 2 },
  entryTime:      { fontSize: 13, color: '#333', flex: 3 },
  entryHours:     { fontSize: 13, fontWeight: '600', color: '#1a73e8', flex: 1, textAlign: 'right' },
});
