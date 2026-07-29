import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import {
  getMaintWorkOrders, getMaintWorkOrder, completeMaintWorkOrder,
} from '../../src/api/maintenance';
import StatusBadge from '../../src/components/StatusBadge';

const STATUSES = ['', 'Open', 'Assigned', 'In Progress', 'On Hold', 'Completed', 'Cancelled'];

export default function MaintenanceScreen() {
  const [wos, setWos] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [completing, setCompleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getMaintWorkOrders(statusFilter || undefined);
      setWos(res.data.data.work_orders ?? []);
    } catch {
      Alert.alert('Error', 'Could not load maintenance work orders.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openDetail = async (id: number) => {
    try {
      const res = await getMaintWorkOrder(id);
      setSelected(res.data.data.work_order);
    } catch {
      Alert.alert('Error', 'Could not load work order details.');
    }
  };

  const complete = async () => {
    if (!selected) return;
    Alert.alert('Complete Work Order', 'Mark this work order as completed?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Complete',
        onPress: async () => {
          setCompleting(true);
          try {
            await completeMaintWorkOrder(selected.id);
            const res = await getMaintWorkOrder(selected.id);
            setSelected(res.data.data.work_order);
            load();
          } catch (err: any) {
            Alert.alert('Error', err?.response?.data?.error ?? 'Could not complete work order.');
          } finally {
            setCompleting(false);
          }
        },
      },
    ]);
  };

  return (
    <View style={styles.screen}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterBar}>
        {STATUSES.map((s) => (
          <TouchableOpacity
            key={s || 'all'}
            style={[styles.filterBtn, statusFilter === s && styles.filterBtnActive]}
            onPress={() => setStatusFilter(s)}
          >
            <Text style={[styles.filterLabel, statusFilter === s && styles.filterLabelActive]}>
              {s || 'All'}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {loading
        ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" />
        : (
          <FlatList
            data={wos}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.card} onPress={() => openDetail(item.id)}>
                <View style={styles.cardHeader}>
                  <Text style={styles.woNum}>{`MWO-${item.id}`}</Text>
                  <StatusBadge status={item.status} />
                </View>
                <Text style={styles.desc} numberOfLines={2}>{item.title}</Text>
                <Text style={styles.meta}>
                  {[
                    item.equipment && `Equipment: ${item.equipment}`,
                    item.priority && `Priority: ${item.priority}`,
                    item.due_date && `Due: ${item.due_date}`,
                  ].filter(Boolean).join('  ·  ') || 'No details'}
                </Text>
              </TouchableOpacity>
            )}
            ListEmptyComponent={<Text style={styles.empty}>No maintenance work orders found.</Text>}
            contentContainerStyle={{ padding: 12 }}
          />
        )
      }

      <Modal visible={!!selected} animationType="slide" onRequestClose={() => setSelected(null)}>
        {selected && (
          <ScrollView style={styles.modal}>
            <TouchableOpacity style={styles.closeBtn} onPress={() => setSelected(null)}>
              <Text style={styles.closeTxt}>← Back</Text>
            </TouchableOpacity>

            <Text style={styles.modalTitle}>{`MWO-${selected.id}`}</Text>
            <StatusBadge status={selected.status} />
            <Text style={styles.modalDesc}>{selected.title}</Text>

            <View style={{ marginTop: 16 }}>
              {[
                ['Equipment', selected.equipment],
                ['Work type', selected.work_type],
                ['Priority', selected.priority],
                ['Requested', selected.requested_date],
                ['Due', selected.due_date],
                ['Completed', selected.completed_date],
                ['Assigned to', selected.assigned_to],
              ]
                .filter(([, v]) => v)
                .map(([label, value]) => (
                  <View key={label} style={styles.infoRow}>
                    <Text style={styles.infoLabel}>{label}</Text>
                    <Text style={styles.infoValue}>{value}</Text>
                  </View>
                ))}
            </View>

            {selected.notes ? (
              <View style={{ marginTop: 12 }}>
                <Text style={styles.sectionTitle}>Notes</Text>
                <Text style={styles.notes}>{selected.notes}</Text>
              </View>
            ) : null}

            {selected.status !== 'Completed' && selected.status !== 'Cancelled' && (
              <TouchableOpacity
                style={[styles.completeBtn, completing && { opacity: 0.6 }]}
                onPress={complete}
                disabled={completing}
              >
                {completing
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={styles.completeTxt}>Mark Completed</Text>
                }
              </TouchableOpacity>
            )}
          </ScrollView>
        )}
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:       { flex: 1, backgroundColor: '#f4f6fb' },
  filterBar:    { maxHeight: 48, paddingHorizontal: 12, paddingVertical: 8 },
  filterBtn:    { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#fff', marginRight: 8, borderWidth: 1, borderColor: '#ddd' },
  filterBtnActive: { backgroundColor: '#1a73e8', borderColor: '#1a73e8' },
  filterLabel:  { fontSize: 13, color: '#555', fontWeight: '500' },
  filterLabelActive: { color: '#fff' },
  card:         { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  cardHeader:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  woNum:        { fontWeight: '700', fontSize: 15, color: '#1a1a2e' },
  desc:         { color: '#444', fontSize: 13, marginBottom: 4 },
  meta:         { color: '#888', fontSize: 12 },
  empty:        { textAlign: 'center', color: '#999', marginTop: 40 },
  modal:        { flex: 1, backgroundColor: '#f4f6fb', padding: 20 },
  closeBtn:     { marginBottom: 16, marginTop: 12 },
  closeTxt:     { color: '#1a73e8', fontSize: 16, fontWeight: '600' },
  modalTitle:   { fontSize: 20, fontWeight: '700', color: '#1a1a2e', marginBottom: 8 },
  modalDesc:    { fontSize: 14, color: '#444', marginTop: 10, lineHeight: 21 },
  infoRow:      { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  infoLabel:    { color: '#888', fontSize: 13 },
  infoValue:    { color: '#1a1a2e', fontSize: 13, fontWeight: '600' },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginBottom: 6 },
  notes:        { fontSize: 13, color: '#555', lineHeight: 20 },
  completeBtn:  { backgroundColor: '#34a853', borderRadius: 10, padding: 16, alignItems: 'center', marginTop: 24, marginBottom: 40 },
  completeTxt:  { color: '#fff', fontWeight: '700', fontSize: 15 },
});
