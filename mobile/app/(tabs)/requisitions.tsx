import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import {
  createRequisition, decideRequisition, getPendingRequisitions,
  getRequisitions, submitRequisition,
} from '../../src/api/requisitions';
import StatusBadge from '../../src/components/StatusBadge';
import { useAuth } from '../../src/hooks/useAuth';

export default function RequisitionsScreen() {
  const { user } = useAuth();
  const [reqs, setReqs] = useState<any[]>([]);
  const [pendingReqs, setPendingReqs] = useState<any[]>([]);
  const [tab, setTab] = useState<'mine' | 'pending'>('mine');
  const [loading, setLoading] = useState(true);
  const [newModal, setNewModal] = useState(false);
  const [purpose, setPurpose] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const myRes = await getRequisitions();
      setReqs(myRes.data.data.requisitions);
      if (user?.is_manager) {
        const pendRes = await getPendingRequisitions();
        setPendingReqs(pendRes.data.data.requisitions);
      }
    } catch {
      Alert.alert('Error', 'Could not load requisitions.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const handleCreate = async () => {
    if (!purpose.trim()) {
      Alert.alert('Required', 'Enter a purpose for the requisition.');
      return;
    }
    setSaving(true);
    try {
      await createRequisition(purpose.trim());
      setPurpose('');
      setNewModal(false);
      load();
      Alert.alert('Created', 'Requisition created as draft. Submit it when ready.');
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not create requisition.');
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async (reqId: number) => {
    try {
      await submitRequisition(reqId);
      load();
      Alert.alert('Submitted', 'Requisition submitted for approval.');
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Submit failed.');
    }
  };

  const handleDecide = async (reqId: number, decision: 'approve' | 'deny') => {
    try {
      await decideRequisition(reqId, decision);
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Decision failed.');
    }
  };

  const listData = tab === 'mine' ? reqs : pendingReqs;

  return (
    <View style={styles.screen}>
      <View style={styles.tabRow}>
        <TouchableOpacity
          style={[styles.tabBtn, tab === 'mine' && styles.tabBtnActive]}
          onPress={() => setTab('mine')}
        >
          <Text style={[styles.tabLabel, tab === 'mine' && styles.tabLabelActive]}>My Requests</Text>
        </TouchableOpacity>
        {user?.is_manager && (
          <TouchableOpacity
            style={[styles.tabBtn, tab === 'pending' && styles.tabBtnActive]}
            onPress={() => setTab('pending')}
          >
            <Text style={[styles.tabLabel, tab === 'pending' && styles.tabLabelActive]}>
              {`Pending Approval${pendingReqs.length > 0 ? ` (${pendingReqs.length})` : ''}`}
            </Text>
          </TouchableOpacity>
        )}
        {tab === 'mine' && (
          <TouchableOpacity style={styles.newBtn} onPress={() => setNewModal(true)}>
            <Text style={styles.newBtnText}>+ New</Text>
          </TouchableOpacity>
        )}
      </View>

      {loading
        ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" />
        : (
          <FlatList
            data={listData}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
            renderItem={({ item }) => (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.reqNum}>{item.req_number}</Text>
                  <StatusBadge status={item.status} />
                </View>
                <Text style={styles.purpose} numberOfLines={2}>{item.purpose}</Text>
                <Text style={styles.meta}>
                  {`${item.dept_name ?? ''}${item.requester_name ? `  ·  ${item.requester_name}` : ''}`}
                </Text>
                <View style={styles.actions}>
                  {tab === 'mine' && item.status === 'draft' && (
                    <TouchableOpacity
                      style={styles.actionBtn}
                      onPress={() => handleSubmit(item.id)}
                    >
                      <Text style={styles.actionBtnText}>Submit for Approval</Text>
                    </TouchableOpacity>
                  )}
                  {tab === 'pending' && (
                    <>
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.approveBtn]}
                        onPress={() => handleDecide(item.id, 'approve')}
                      >
                        <Text style={styles.actionBtnText}>Approve</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.denyBtn]}
                        onPress={() => handleDecide(item.id, 'deny')}
                      >
                        <Text style={styles.actionBtnText}>Deny</Text>
                      </TouchableOpacity>
                    </>
                  )}
                </View>
              </View>
            )}
            ListEmptyComponent={
              <Text style={styles.empty}>
                {tab === 'mine' ? 'No requisitions yet. Tap + New to create one.' : 'No pending approvals.'}
              </Text>
            }
            contentContainerStyle={{ padding: 12 }}
          />
        )
      }

      <Modal visible={newModal} animationType="slide" onRequestClose={() => setNewModal(false)}>
        <View style={styles.modalContainer}>
          <Text style={styles.modalTitle}>New Requisition</Text>
          <Text style={styles.modalLabel}>Purpose</Text>
          <TextInput
            style={styles.input}
            placeholder="Describe what you need and why..."
            placeholderTextColor="#999"
            multiline
            numberOfLines={4}
            value={purpose}
            onChangeText={setPurpose}
          />
          <TouchableOpacity
            style={[styles.saveBtn, saving && { opacity: 0.6 }]}
            onPress={handleCreate}
            disabled={saving}
          >
            {saving
              ? <ActivityIndicator color="#fff" />
              : <Text style={styles.saveBtnText}>Create Draft</Text>
            }
          </TouchableOpacity>
          <TouchableOpacity style={styles.cancelBtn} onPress={() => setNewModal(false)}>
            <Text style={styles.cancelBtnText}>Cancel</Text>
          </TouchableOpacity>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:         { flex: 1, backgroundColor: '#f4f6fb' },
  tabRow:         { flexDirection: 'row', padding: 12, gap: 8, alignItems: 'center' },
  tabBtn:         { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: '#fff', borderWidth: 1, borderColor: '#ddd' },
  tabBtnActive:   { backgroundColor: '#1a73e8', borderColor: '#1a73e8' },
  tabLabel:       { fontSize: 13, color: '#555', fontWeight: '600' },
  tabLabelActive: { color: '#fff' },
  newBtn:         { marginLeft: 'auto', backgroundColor: '#34a853', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20 },
  newBtnText:     { color: '#fff', fontWeight: '700', fontSize: 13 },
  card:           { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  cardHeader:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  reqNum:         { fontWeight: '700', fontSize: 15, color: '#1a1a2e' },
  purpose:        { color: '#444', fontSize: 13, marginBottom: 4 },
  meta:           { color: '#888', fontSize: 12, marginBottom: 8 },
  actions:        { flexDirection: 'row', gap: 8 },
  actionBtn:      { backgroundColor: '#1a73e8', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8 },
  approveBtn:     { backgroundColor: '#34a853' },
  denyBtn:        { backgroundColor: '#d93025' },
  actionBtnText:  { color: '#fff', fontWeight: '600', fontSize: 13 },
  empty:          { textAlign: 'center', color: '#999', marginTop: 40, paddingHorizontal: 24 },
  modalContainer: { flex: 1, backgroundColor: '#f4f6fb', padding: 24, paddingTop: 60 },
  modalTitle:     { fontSize: 22, fontWeight: '700', color: '#1a1a2e', marginBottom: 20 },
  modalLabel:     { fontSize: 14, fontWeight: '600', color: '#333', marginBottom: 6 },
  input:          { backgroundColor: '#fff', borderRadius: 10, padding: 14, fontSize: 15, borderWidth: 1, borderColor: '#ddd', minHeight: 100, textAlignVertical: 'top', marginBottom: 20 },
  saveBtn:        { backgroundColor: '#1a73e8', borderRadius: 10, padding: 16, alignItems: 'center', marginBottom: 12 },
  saveBtnText:    { color: '#fff', fontWeight: '700', fontSize: 15 },
  cancelBtn:      { padding: 12, alignItems: 'center' },
  cancelBtnText:  { color: '#666', fontSize: 15 },
});
