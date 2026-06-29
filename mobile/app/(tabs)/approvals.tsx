import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getPendingSteps, decideStep } from '../../src/api/approvals';

const ENTITY_LABELS: Record<string, string> = {
  purchase_order: 'Purchase Order',
  purchase_requisition: 'Requisition',
  gl_journal: 'GL Journal',
};

export default function ApprovalsScreen() {
  const [steps, setSteps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getPendingSteps();
      setSteps(res.data.data.steps ?? []);
    } catch {
      Alert.alert('Error', 'Could not load pending approvals.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const decide = async (decision: 'approved' | 'rejected') => {
    if (!selected) return;
    setSubmitting(true);
    try {
      await decideStep(selected.id, decision, notes.trim());
      setSelected(null);
      setNotes('');
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not submit decision.');
    } finally {
      setSubmitting(false);
    }
  };

  const confirmDecide = (decision: 'approved' | 'rejected') => {
    Alert.alert(
      decision === 'approved' ? 'Approve' : 'Reject',
      `${decision === 'approved' ? 'Approve' : 'Reject'} this item?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: decision === 'approved' ? 'Approve' : 'Reject',
          style: decision === 'rejected' ? 'destructive' : 'default',
          onPress: () => decide(decision) },
      ],
    );
  };

  return (
    <View style={styles.screen}>
      {loading
        ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" />
        : (
          <FlatList
            data={steps}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.card} onPress={() => { setSelected(item); setNotes(''); }}>
                <View style={styles.cardHeader}>
                  <Text style={styles.entityLabel}>
                    {ENTITY_LABELS[item.entity_type] ?? item.entity_type} #{item.entity_id}
                  </Text>
                  <Text style={styles.seqBadge}>Step {item.seq}</Text>
                </View>
                <Text style={styles.roleText}>{item.approver_role}</Text>
                {item.threshold_amount > 0 && (
                  <Text style={styles.meta}>{`Threshold: $${item.threshold_amount.toLocaleString()}`}</Text>
                )}
                <Text style={styles.meta}>{`Submitted: ${item.created_at?.slice(0, 10) ?? '—'}`}</Text>
              </TouchableOpacity>
            )}
            ListEmptyComponent={(
              <View style={styles.emptyWrap}>
                <Text style={styles.emptyIcon}>✅</Text>
                <Text style={styles.emptyText}>No pending approvals.</Text>
              </View>
            )}
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

            <Text style={styles.modalTitle}>
              {ENTITY_LABELS[selected.entity_type] ?? selected.entity_type} #{selected.entity_id}
            </Text>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Required role</Text>
              <Text style={styles.infoValue}>{selected.approver_role}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Step sequence</Text>
              <Text style={styles.infoValue}>{selected.seq}</Text>
            </View>
            {selected.threshold_amount > 0 && (
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Amount threshold</Text>
                <Text style={styles.infoValue}>${selected.threshold_amount.toLocaleString()}</Text>
              </View>
            )}
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Escalates after</Text>
              <Text style={styles.infoValue}>{selected.escalate_after_hours}h</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Submitted</Text>
              <Text style={styles.infoValue}>{selected.created_at?.slice(0, 16).replace('T', ' ') ?? '—'}</Text>
            </View>

            <Text style={styles.sectionTitle}>Notes (optional)</Text>
            <TextInput
              style={styles.notesInput}
              placeholder="Add a note..."
              value={notes}
              onChangeText={setNotes}
              multiline
              numberOfLines={3}
            />

            {submitting
              ? <ActivityIndicator style={{ marginTop: 20 }} color="#1a73e8" />
              : (
                <View style={styles.actionRow}>
                  <TouchableOpacity
                    style={[styles.actionBtn, styles.approveBtn]}
                    onPress={() => confirmDecide('approved')}
                  >
                    <Text style={styles.approveTxt}>Approve</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionBtn, styles.rejectBtn]}
                    onPress={() => confirmDecide('rejected')}
                  >
                    <Text style={styles.rejectTxt}>Reject</Text>
                  </TouchableOpacity>
                </View>
              )
            }
          </ScrollView>
        )}
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:       { flex: 1, backgroundColor: '#f4f6fb' },
  card:         { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  cardHeader:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  entityLabel:  { fontWeight: '700', fontSize: 15, color: '#1a1a2e', flex: 1 },
  seqBadge:     { backgroundColor: '#e8f0fe', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  roleText:     { fontSize: 13, color: '#1a73e8', fontWeight: '600', marginBottom: 4 },
  meta:         { color: '#888', fontSize: 12, marginTop: 2 },
  emptyWrap:    { alignItems: 'center', marginTop: 60 },
  emptyIcon:    { fontSize: 40, marginBottom: 12 },
  emptyText:    { color: '#999', fontSize: 15 },
  modal:        { flex: 1, backgroundColor: '#f4f6fb', padding: 20 },
  closeBtn:     { marginBottom: 16, marginTop: 12 },
  closeTxt:     { color: '#1a73e8', fontSize: 16, fontWeight: '600' },
  modalTitle:   { fontSize: 20, fontWeight: '700', color: '#1a1a2e', marginBottom: 16 },
  infoRow:      { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  infoLabel:    { color: '#888', fontSize: 13 },
  infoValue:    { color: '#1a1a2e', fontSize: 13, fontWeight: '600' },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginTop: 20, marginBottom: 8 },
  notesInput:   { backgroundColor: '#fff', borderRadius: 10, borderWidth: 1, borderColor: '#ddd', padding: 12, fontSize: 14, minHeight: 80, textAlignVertical: 'top' },
  actionRow:    { flexDirection: 'row', gap: 12, marginTop: 24, marginBottom: 40 },
  actionBtn:    { flex: 1, borderRadius: 10, padding: 16, alignItems: 'center' },
  approveBtn:   { backgroundColor: '#34a853' },
  approveTxt:   { color: '#fff', fontWeight: '700', fontSize: 15 },
  rejectBtn:    { backgroundColor: '#fff', borderWidth: 1.5, borderColor: '#d93025' },
  rejectTxt:    { color: '#d93025', fontWeight: '700', fontSize: 15 },
});
