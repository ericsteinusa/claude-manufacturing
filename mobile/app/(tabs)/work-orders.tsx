import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import {
  getWorkOrder, getWorkOrders, setWorkOrderStatus,
  getWoOperations, startWoOperation, completeWoOperation,
  getWoAssignees, assignWorkOrder,
} from '../../src/api/workorders';
import StatusBadge from '../../src/components/StatusBadge';
import { useAuth } from '../../src/hooks/useAuth';

const STATUSES = ['', 'draft', 'open', 'in_progress', 'completed', 'cancelled'];

const OP_STATUS_COLORS: Record<string, string> = {
  pending: '#888',
  in_progress: '#1a73e8',
  completed: '#34a853',
  skipped: '#aaa',
};

export default function WorkOrdersScreen() {
  const { user } = useAuth();
  // "Production Manager"/"Production Foreman" aren't roles in this app's
  // role table (they're only job titles) — the actual manager-of-Production
  // and foremen are whoever holds the 'Department Manager' or 'Supervisor'
  // role in the 'production' dept.
  const canAssign = !!user?.full_access
    || (user?.dept_key === 'production'
        && (user?.role === 'Department Manager' || user?.role === 'Supervisor'));
  const [wos, setWos] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [operations, setOperations] = useState<any[]>([]);
  const [updating, setUpdating] = useState(false);
  const [completeModal, setCompleteModal] = useState<{ op: any } | null>(null);
  const [actualHours, setActualHours] = useState('');
  const [assignees, setAssignees] = useState<any[]>([]);

  useEffect(() => {
    if (!canAssign) return;
    getWoAssignees()
      .then((res) => setAssignees(res.data.data.assignees ?? []))
      .catch(() => setAssignees([]));
  }, [canAssign]);

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
      const [woRes, opsRes] = await Promise.all([
        getWorkOrder(id),
        getWoOperations(id).catch(() => ({ data: { data: { operations: [] } } })),
      ]);
      setSelected(woRes.data.data.work_order);
      setOperations(opsRes.data.data.operations ?? []);
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

  const assignTo = async (name: string) => {
    if (!selected) return;
    setUpdating(true);
    try {
      await assignWorkOrder(selected.id, name);
      const res = await getWorkOrder(selected.id);
      setSelected(res.data.data.work_order);
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not assign work order.');
    } finally {
      setUpdating(false);
    }
  };

  const startOp = async (op: any) => {
    if (!selected) return;
    Alert.alert('Start Operation', `Start "${op.operation_name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Start',
        onPress: async () => {
          setUpdating(true);
          try {
            await startWoOperation(selected.id, op.operation_seq);
            const opsRes = await getWoOperations(selected.id);
            setOperations(opsRes.data.data.operations ?? []);
          } catch (err: any) {
            Alert.alert('Error', err?.response?.data?.error ?? 'Could not start operation.');
          } finally {
            setUpdating(false);
          }
        },
      },
    ]);
  };

  const completeOp = async () => {
    if (!completeModal || !selected) return;
    const hrs = parseFloat(actualHours);
    if (isNaN(hrs) || hrs < 0) { Alert.alert('Invalid', 'Enter actual hours.'); return; }
    setUpdating(true);
    try {
      await completeWoOperation(selected.id, completeModal.op.operation_seq, hrs);
      const opsRes = await getWoOperations(selected.id);
      setOperations(opsRes.data.data.operations ?? []);
      setCompleteModal(null);
      setActualHours('');
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not complete operation.');
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
                  {`Qty: ${item.quantity}${item.due_date ? `  ·  Due: ${item.due_date}` : ''}${item.mat_count > 0 ? `  ·  ${item.mat_count} materials` : ''}${item.op_total > 0 ? `  ·  ${item.op_done}/${item.op_total} steps` : ''}`}
                </Text>
                <Text style={styles.meta}>
                  {`Assigned: ${item.assigned_to || 'Unassigned'}`}
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
            <Text style={styles.modalMeta}>{`Assigned: ${selected.assigned_to || 'Unassigned'}`}</Text>

            {canAssign && (
              <View style={{ marginTop: 16 }}>
                <Text style={styles.sectionTitle}>Assign To</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  <TouchableOpacity
                    style={styles.transitionBtn}
                    onPress={() => assignTo('')}
                    disabled={updating}
                  >
                    <Text style={styles.transitionLabel}>Unassigned</Text>
                  </TouchableOpacity>
                  {assignees.map((a: any) => (
                    <TouchableOpacity
                      key={a.id}
                      style={styles.transitionBtn}
                      onPress={() => assignTo(a.name)}
                      disabled={updating}
                    >
                      <Text style={styles.transitionLabel}>{a.name}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            )}

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

            {operations.length > 0 && (
              <View style={{ marginTop: 16 }}>
                <Text style={styles.sectionTitle}>Operations</Text>
                {operations.map((op: any) => (
                  <View key={op.id} style={styles.opCard}>
                    <View style={styles.opHeader}>
                      <View style={[styles.seqBadge, { backgroundColor: OP_STATUS_COLORS[op.status] ?? '#888' }]}>
                        <Text style={styles.seqTxt}>{op.operation_seq}</Text>
                      </View>
                      <Text style={styles.opName}>{op.operation_name}</Text>
                      <StatusBadge status={op.status} />
                    </View>
                    {op.workcenter_name ? (
                      <Text style={styles.opMeta}>{`WC: ${op.workcenter_name}  ·  Std: ${op.std_hours}h`}</Text>
                    ) : null}
                    {op.status === 'pending' && (
                      <TouchableOpacity
                        style={styles.opStartBtn}
                        onPress={() => startOp(op)}
                        disabled={updating}
                      >
                        <Text style={styles.opStartTxt}>▶ Start</Text>
                      </TouchableOpacity>
                    )}
                    {op.status === 'in_progress' && (
                      <TouchableOpacity
                        style={styles.opCompleteBtn}
                        onPress={() => { setCompleteModal({ op }); setActualHours(String(op.std_hours ?? '')); }}
                        disabled={updating}
                      >
                        <Text style={styles.opCompleteTxt}>✓ Complete</Text>
                      </TouchableOpacity>
                    )}
                  </View>
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

      {/* Complete Operation Modal */}
      <Modal visible={!!completeModal} animationType="slide" transparent onRequestClose={() => setCompleteModal(null)}>
        <View style={styles.sheetOverlay}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>
              Complete: {completeModal?.op?.operation_name}
            </Text>
            <Text style={styles.sheetLabel}>Actual Hours</Text>
            <TextInput
              style={styles.sheetInput}
              value={actualHours}
              onChangeText={setActualHours}
              keyboardType="decimal-pad"
              autoFocus
            />
            <View style={styles.sheetActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setCompleteModal(null)}>
                <Text style={styles.cancelTxt}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.submitBtn, updating && { opacity: 0.6 }]}
                onPress={completeOp}
                disabled={updating}
              >
                {updating ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitTxt}>Complete</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
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
  opCard:           { backgroundColor: '#fff', borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#e8eaf6' },
  opHeader:         { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  seqBadge:         { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  seqTxt:           { color: '#fff', fontSize: 11, fontWeight: '700' },
  opName:           { flex: 1, fontSize: 13, fontWeight: '600', color: '#1a1a2e' },
  opMeta:           { fontSize: 12, color: '#888', marginBottom: 6 },
  opStartBtn:       { backgroundColor: '#e8f0fe', borderRadius: 8, paddingVertical: 7, alignItems: 'center' },
  opStartTxt:       { color: '#1a73e8', fontWeight: '700', fontSize: 13 },
  opCompleteBtn:    { backgroundColor: '#e6f4ea', borderRadius: 8, paddingVertical: 7, alignItems: 'center' },
  opCompleteTxt:    { color: '#34a853', fontWeight: '700', fontSize: 13 },
  transitionBtn:    { backgroundColor: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#1a73e8', alignItems: 'center' },
  transitionLabel:  { color: '#1a73e8', fontWeight: '600', fontSize: 14, textTransform: 'capitalize' },
  sheetOverlay:     { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  sheet:            { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  sheetTitle:       { fontSize: 16, fontWeight: '700', color: '#1a1a2e', marginBottom: 16 },
  sheetLabel:       { fontSize: 13, fontWeight: '600', color: '#555', marginBottom: 6 },
  sheetInput:       { borderWidth: 1, borderColor: '#ddd', borderRadius: 10, padding: 12, fontSize: 18, textAlign: 'center', marginBottom: 16 },
  sheetActions:     { flexDirection: 'row', gap: 12 },
  cancelBtn:        { flex: 1, borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#ddd' },
  cancelTxt:        { color: '#555', fontWeight: '600' },
  submitBtn:        { flex: 1, borderRadius: 10, padding: 14, alignItems: 'center', backgroundColor: '#34a853' },
  submitTxt:        { color: '#fff', fontWeight: '700' },
});
