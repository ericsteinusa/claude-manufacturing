import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, RefreshControl, ScrollView,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { clockIn, clockOut, getHours, getStatus } from '../../src/api/timeclock';
import { fetchWithOfflineCache } from '../../src/offline/cache';
import { enqueueMutation, getQueuedMutations } from '../../src/offline/queue';
import { useIsOnline } from '../../src/offline/netStatus';
import OfflineBanner from '../../src/components/OfflineBanner';

type Period = 'today' | 'week' | 'month';

export default function TimeClockScreen() {
  const isOnline = useIsOnline();
  const [clockedIn, setClockedIn] = useState(false);
  const [currentEntry, setCurrentEntry] = useState<any>(null);
  const [hours, setHours] = useState<any>(null);
  const [period, setPeriod] = useState<Period>('week');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [queuedCount, setQueuedCount] = useState(0);

  const refreshQueueCount = useCallback(async () => {
    const queue = await getQueuedMutations();
    setQueuedCount(queue.filter((m) => m.url === '/time-clock/clock-in/' || m.url === '/time-clock/clock-out/').length);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statusResult, hoursResult] = await Promise.all([
        fetchWithOfflineCache('tc_status', async () => (await getStatus()).data.data),
        fetchWithOfflineCache(`tc_hours_${period}`, async () => (await getHours(period)).data.data),
      ]);
      setClockedIn(statusResult.data.clocked_in);
      setCurrentEntry(statusResult.data.entry);
      setHours(hoursResult.data);
      setIsStale(statusResult.isStale || hoursResult.isStale);
      setCachedAt(statusResult.isStale ? statusResult.cachedAt : hoursResult.cachedAt);
    } catch {
      Alert.alert('Error', 'Could not load time clock data.');
    } finally {
      await refreshQueueCount();
      setLoading(false);
    }
  }, [period, refreshQueueCount]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  // Pick up mutations the app-wide reconnect listener (app/_layout.tsx)
  // just flushed while this screen wasn't focused — only on an actual
  // offline-to-online transition, not on the initial mount (useFocusEffect
  // above already covers that).
  const wasOnline = useRef(isOnline);
  useEffect(() => {
    if (isOnline && !wasOnline.current) load();
    wasOnline.current = isOnline;
  }, [isOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggle = async () => {
    setActionLoading(true);
    const goingClockedIn = !clockedIn;
    try {
      if (!isOnline) {
        // Queue it and optimistically flip the toggle — a plant-floor
        // worker needs clock-in/out to work with no signal; this is
        // exactly the case COMPETITIVE_GAP_ANALYSIS.md's §6.10 called out.
        await enqueueMutation(
          'post',
          goingClockedIn ? '/time-clock/clock-in/' : '/time-clock/clock-out/',
          goingClockedIn ? { notes: '' } : undefined,
          goingClockedIn ? 'Clock in' : 'Clock out',
        );
        setClockedIn(goingClockedIn);
        await refreshQueueCount();
        Alert.alert(
          goingClockedIn ? 'Clock-in queued' : 'Clock-out queued',
          'No connection — this will sync automatically once you\'re back online.',
        );
      } else if (clockedIn) {
        await clockOut();
        Alert.alert('Clocked Out', 'Your time has been recorded.');
        await load();
      } else {
        await clockIn();
        Alert.alert('Clocked In', 'Have a great shift!');
        await load();
      }
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
      <OfflineBanner isStale={isStale} cachedAt={cachedAt} queuedCount={queuedCount} />
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
