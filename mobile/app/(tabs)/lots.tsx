import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getLots, getLot, getLotExpiry, createLot, updateLotStatus } from '../../src/api/lots';
import StatusBadge from '../../src/components/StatusBadge';

const LOT_STATUSES = ['available', 'quarantine', 'hold', 'consumed', 'rejected'];

const STATUS_COLORS: Record<string, string> = {
  available: '#34a853',
  quarantine: '#e8710a',
  hold: '#f9ab00',
  consumed: '#888',
  rejected: '#d93025',
};

export default function LotsScreen() {
  const [lots, setLots] = useState<any[]>([]);
  const [expiryAlerts, setExpiryAlerts] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [createModal, setCreateModal] = useState(false);
  const [statusModal, setStatusModal] = useState<{ lot: any } | null>(null);
  const [newStatus, setNewStatus] = useState('available');
  const [statusNotes, setStatusNotes] = useState('');
  const [form, setForm] = useState({ lot_number: '', qty: '', received_date: '', expiry_date: '', notes: '' });
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [lotsRes, expiryRes] = await Promise.all([
        getLots(statusFilter ? { status: statusFilter } : undefined),
        getLotExpiry(30),
      ]);
      setLots(lotsRes.data.data.lots ?? []);
      setExpiryAlerts(expiryRes.data.data.alerts ?? []);
    } catch {
      Alert.alert('Error', 'Could not load lots.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openDetail = async (id: number) => {
    try {
      const res = await getLot(id);
      setSelected(res.data.data);
    } catch {
      Alert.alert('Error', 'Could not load lot details.');
    }
  };

  const submitCreate = async () => {
    const qty = parseFloat(form.qty);
    if (!qty || qty <= 0) { Alert.alert('Required', 'Enter a valid quantity.'); return; }
    setSubmitting(true);
    try {
      await createLot({
        product_id: 0,
        qty,
        lot_number: form.lot_number.trim() || undefined,
        received_date: form.received_date || undefined,
        expiry_date: form.expiry_date || undefined,
        notes: form.notes.trim(),
      });
      setCreateModal(false);
      setForm({ lot_number: '', qty: '', received_date: '', expiry_date: '', notes: '' });
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not create lot.');
    } finally {
      setSubmitting(false);
    }
  };

  const submitStatus = async () => {
    if (!statusModal) return;
    setSubmitting(true);
    try {
      await updateLotStatus(statusModal.lot.id, newStatus, statusNotes.trim());
      const res = await getLot(statusModal.lot.id);
      setSelected(res.data.data);
      setStatusModal(null);
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not update status.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={styles.screen}>
      {expiryAlerts.length > 0 && (
        <View style={styles.expiryBanner}>
          <Text style={styles.expiryTxt}>
            {`⚠ ${expiryAlerts.length} lot${expiryAlerts.length > 1 ? 's' : ''} expiring within 30 days`}
          </Text>
        </View>
      )}

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterBar}>
        {['', ...LOT_STATUSES].map((s) => (
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
            data={lots}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.card} onPress={() => openDetail(item.id)}>
                <View style={styles.cardHeader}>
                  <Text style={styles.lotNum}>{item.lot_number}</Text>
                  <View style={[styles.statusDot, { backgroundColor: STATUS_COLORS[item.status] ?? '#888' }]} />
                </View>
                <Text style={styles.productName}>{item.product_name ?? `Product #${item.product_id}`}</Text>
                <View style={styles.metaRow}>
                  <Text style={styles.qty}>{`Qty: ${item.qty}`}</Text>
                  {item.expiry_date && (
                    <Text style={styles.expiry}>{`Exp: ${item.expiry_date}`}</Text>
                  )}
                  <StatusBadge status={item.status} />
                </View>
              </TouchableOpacity>
            )}
            ListEmptyComponent={<Text style={styles.empty}>No lots found.</Text>}
            contentContainerStyle={{ padding: 12 }}
          />
        )
      }

      {/* Detail Modal */}
      <Modal visible={!!selected} animationType="slide" onRequestClose={() => setSelected(null)}>
        {selected && (
          <ScrollView style={styles.modal}>
            <TouchableOpacity style={styles.closeBtn} onPress={() => setSelected(null)}>
              <Text style={styles.closeTxt}>← Back</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>{selected.lot?.lot_number}</Text>
            <StatusBadge status={selected.lot?.status} />

            <View style={styles.infoSection}>
              {[
                ['Product', selected.lot?.product_name ?? `#${selected.lot?.product_id}`],
                ['Quantity', String(selected.lot?.qty ?? '')],
                ['Received', selected.lot?.received_date],
                ['Expires', selected.lot?.expiry_date],
                ['Notes', selected.lot?.notes],
                ['Created by', selected.lot?.created_by],
              ].filter(([, v]) => v).map(([label, value]) => (
                <View key={label} style={styles.infoRow}>
                  <Text style={styles.infoLabel}>{label}</Text>
                  <Text style={styles.infoValue}>{value}</Text>
                </View>
              ))}
            </View>

            {(selected.genealogy?.input_lots?.length > 0) && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Input Lots</Text>
                {selected.genealogy.input_lots.map((il: any) => (
                  <Text key={il.id} style={styles.bodyText}>
                    {`• ${il.lot_number} — ${il.product_name ?? ''} (${il.qty})`}
                  </Text>
                ))}
              </View>
            )}

            {(selected.serials?.length > 0) && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Serial Numbers ({selected.serials.length})</Text>
                {selected.serials.map((s: any) => (
                  <View key={s.id} style={styles.serialRow}>
                    <Text style={styles.serialNum}>{s.serial_number}</Text>
                    <StatusBadge status={s.status} />
                  </View>
                ))}
              </View>
            )}

            <TouchableOpacity
              style={styles.statusBtn}
              onPress={() => { setNewStatus(selected.lot?.status ?? 'available'); setStatusNotes(''); setStatusModal({ lot: selected.lot }); }}
            >
              <Text style={styles.statusBtnTxt}>Update Status</Text>
            </TouchableOpacity>
          </ScrollView>
        )}
      </Modal>

      {/* Status Update Modal */}
      <Modal visible={!!statusModal} animationType="slide" transparent onRequestClose={() => setStatusModal(null)}>
        <View style={styles.sheetOverlay}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Update Lot Status</Text>
            <View style={styles.chipRow}>
              {LOT_STATUSES.map((s) => (
                <TouchableOpacity
                  key={s}
                  style={[styles.chip, newStatus === s && { backgroundColor: STATUS_COLORS[s], borderColor: STATUS_COLORS[s] }]}
                  onPress={() => setNewStatus(s)}
                >
                  <Text style={[styles.chipTxt, newStatus === s && { color: '#fff' }]}>{s}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput
              style={styles.notesInput}
              placeholder="Notes (optional)"
              value={statusNotes}
              onChangeText={setStatusNotes}
            />
            <View style={styles.sheetActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setStatusModal(null)}>
                <Text style={styles.cancelTxt}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.submitBtn, submitting && { opacity: 0.6 }]}
                onPress={submitStatus}
                disabled={submitting}
              >
                {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitTxt}>Update</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:       { flex: 1, backgroundColor: '#f4f6fb' },
  expiryBanner: { backgroundColor: '#fff3cd', padding: 10, borderBottomWidth: 1, borderBottomColor: '#ffc107' },
  expiryTxt:    { color: '#856404', fontSize: 13, fontWeight: '600', textAlign: 'center' },
  filterBar:    { maxHeight: 48, paddingHorizontal: 12, paddingVertical: 8 },
  filterBtn:    { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#fff', marginRight: 8, borderWidth: 1, borderColor: '#ddd' },
  filterBtnActive: { backgroundColor: '#1a73e8', borderColor: '#1a73e8' },
  filterLabel:  { fontSize: 13, color: '#555', fontWeight: '500' },
  filterLabelActive: { color: '#fff' },
  card:         { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  cardHeader:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  lotNum:       { fontWeight: '700', fontSize: 15, color: '#1a1a2e' },
  statusDot:    { width: 10, height: 10, borderRadius: 5 },
  productName:  { color: '#555', fontSize: 13, marginBottom: 6 },
  metaRow:      { flexDirection: 'row', gap: 10, alignItems: 'center', flexWrap: 'wrap' },
  qty:          { fontSize: 13, color: '#1a1a2e', fontWeight: '600' },
  expiry:       { fontSize: 12, color: '#888' },
  empty:        { textAlign: 'center', color: '#999', marginTop: 40 },
  modal:        { flex: 1, backgroundColor: '#f4f6fb', padding: 20 },
  closeBtn:     { marginBottom: 16, marginTop: 12 },
  closeTxt:     { color: '#1a73e8', fontSize: 16, fontWeight: '600' },
  modalTitle:   { fontSize: 20, fontWeight: '700', color: '#1a1a2e', marginBottom: 8 },
  infoSection:  { marginTop: 16 },
  infoRow:      { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  infoLabel:    { color: '#888', fontSize: 13 },
  infoValue:    { color: '#1a1a2e', fontSize: 13, fontWeight: '600', flex: 1, textAlign: 'right', marginLeft: 12 },
  section:      { marginTop: 20 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginBottom: 8 },
  bodyText:     { fontSize: 13, color: '#555', lineHeight: 20, marginBottom: 4 },
  serialRow:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#eee' },
  serialNum:    { fontSize: 13, color: '#1a1a2e', fontWeight: '600' },
  statusBtn:    { backgroundColor: '#1a73e8', borderRadius: 10, padding: 14, alignItems: 'center', marginTop: 24, marginBottom: 40 },
  statusBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  sheetOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  sheet:        { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  sheetTitle:   { fontSize: 17, fontWeight: '700', color: '#1a1a2e', marginBottom: 16 },
  chipRow:      { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  chip:         { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 16, borderWidth: 1, borderColor: '#ddd', backgroundColor: '#fff' },
  chipTxt:      { fontSize: 13, color: '#555', fontWeight: '500' },
  notesInput:   { borderWidth: 1, borderColor: '#ddd', borderRadius: 10, padding: 12, fontSize: 14, backgroundColor: '#f9f9f9', marginBottom: 16 },
  sheetActions: { flexDirection: 'row', gap: 12 },
  cancelBtn:    { flex: 1, borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#ddd' },
  cancelTxt:    { color: '#555', fontWeight: '600' },
  submitBtn:    { flex: 1, borderRadius: 10, padding: 14, alignItems: 'center', backgroundColor: '#1a73e8' },
  submitTxt:    { color: '#fff', fontWeight: '700' },
});
