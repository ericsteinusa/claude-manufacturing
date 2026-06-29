import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getWorkOrder, getWorkOrders, setWorkOrderStatus } from '../../src/api/workorders';
import StatusBadge from '../../src/components/StatusBadge';

const STATUSES = ['', 'draft', 'open', 'in_progress', 'completed', 'cancelled'];

export default function WorkOrdersScreen() {
  const [wos, setWos] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [updating, setUpdating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getWorkOrders(statusFilter || undefined);
      setWos(res.data.data.work_orders);
    } catch {
      Alert.alert('Error', 'Could not load work orders.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openDetail = async (id: number) => {
    try {
      const res = await getWorkOrder(id);
      setSelected(res.data.data.work_order);
    } catch {
      Alert.alert('Error', 'Could not load work order details.');
    }
  };

  const transition = async (woId: number, status: string) => {
    setUpdating(true);
    try {
      await setWorkOrderStatus(woId, status);
      const res = await getWorkOrder(woId);
      setSelected(res.data.data.work_order);
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Status update failed.');
    } finally {
      setUpdating(false);
    }
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
                  <Text style={styles.woNum}>{item.wo_number}</Text>
                  <StatusBadge status={item.status} />
                </View>
                <Text style={styles.desc} numberOfLines={2}>{item.description}</Text>
                <Text style={styles.meta}>
                  {`Qty: ${item.quantity}${item.due_date ? `  ·  Due: ${item.due_date}` : ''}${item.mat_count > 0 ? `  ·  ${item.mat_count} materials` : ''}`}
                </Text>
              </TouchableOpacity>
            )}
            ListEmptyComponent={<Text style={styles.empty}>No work orders found.</Text>}
            contentContainerStyle={{ padding: 12 }}
          />
        )
      }

      <Modal visible={!!selected} animationType="slide" onRequestClose={() => setSelected(null)}>
        {selected && (
          <ScrollView style={styles.modal}>
            <TouchableOpacity style={styles.closeBtn} onPress={() => setSelected(null)}>
              <Text style={styles.closeTxt}>Close</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>{selected.wo_number}</Text>
            <StatusBadge status={selected.status} />
            <Text style={styles.modalDesc}>{selected.description}</Text>
            <Text style={styles.modalMeta}>{`Qty: ${selected.quantity}`}</Text>
            {selected.due_date ? <Text style={styles.modalMeta}>{`Due: ${selected.due_date}`}</Text> : null}

            {selected.materials?.length > 0 && (
              <View style={{ marginTop: 16 }}>
                <Text style={styles.sectionTitle}>Materials</Text>
                {selected.materials.map((m: any) => (
                  <Text key={m.id} style={styles.materialRow}>
                    {`${m.product_name ?? 'Unknown'} — req: ${m.qty_required}, issued: ${m.qty_issued}`}
                  </Text>
                ))}
              </View>
            )}

            {selected.allowed_transitions?.length > 0 && (
              <View style={{ marginTop: 20 }}>
                <Text style={styles.sectionTitle}>Change Status</Text>
                {selected.allowed_transitions.map((s: string) => (
                  <TouchableOpacity
                    key={s}
                    style={styles.transitionBtn}
                    onPress={() => transition(selected.id, s)}
                    disabled={updating}
                  >
                    {updating
                      ? <ActivityIndicator color="#1a73e8" />
                      : <Text style={styles.transitionLabel}>{s.replace(/_/g, ' ')}</Text>
                    }
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </ScrollView>
        )}
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:           { flex: 1, backgroundColor: '#f4f6fb' },
  filterBar:        { maxHeight: 48, paddingHorizontal: 12, paddingVertical: 8 },
  filterBtn:        { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#fff', marginRight: 8, borderWidth: 1, borderColor: '#ddd' },
  filterBtnActive:  { backgroundColor: '#1a73e8', borderColor: '#1a73e8' },
  filterLabel:      { fontSize: 13, color: '#555', fontWeight: '500' },
  filterLabelActive: { color: '#fff' },
  card:             { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  cardHeader:       { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  woNum:            { fontWeight: '700', fontSize: 15, color: '#1a1a2e' },
  desc:             { color: '#444', fontSize: 13, marginBottom: 4 },
  meta:             { color: '#888', fontSize: 12 },
  empty:            { textAlign: 'center', color: '#999', marginTop: 40 },
  modal:            { flex: 1, backgroundColor: '#f4f6fb', padding: 20 },
  closeBtn:         { marginBottom: 16, marginTop: 12 },
  closeTxt:         { color: '#1a73e8', fontSize: 16, fontWeight: '600' },
  modalTitle:       { fontSize: 20, fontWeight: '700', color: '#1a1a2e', marginBottom: 8 },
  modalDesc:        { fontSize: 15, color: '#444', marginTop: 12, lineHeight: 22 },
  modalMeta:        { fontSize: 13, color: '#888', marginTop: 4 },
  sectionTitle:     { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginBottom: 8 },
  materialRow:      { fontSize: 13, color: '#555', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: '#eee' },
  transitionBtn:    { backgroundColor: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#1a73e8', alignItems: 'center' },
  transitionLabel:  { color: '#1a73e8', fontWeight: '600', fontSize: 14, textTransform: 'capitalize' },
});
