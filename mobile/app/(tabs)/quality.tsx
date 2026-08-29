import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getNcrs, getNcr, createNcr } from '../../src/api/quality';
import StatusBadge from '../../src/components/StatusBadge';
import OfflineBanner from '../../src/components/OfflineBanner';
import { fetchWithOfflineCache } from '../../src/offline/cache';

const STATUSES = ['', 'Open', 'Under Review', 'Dispositioned', 'Closed'];
const SEVERITIES = ['Minor', 'Major', 'Critical'];
const SOURCES = ['Incoming', 'In-Process', 'Final', 'Customer', 'Supplier', 'Audit'];

const SEVERITY_COLORS: Record<string, string> = {
  Minor: '#f9ab00',
  Major: '#e8710a',
  Critical: '#d93025',
};

export default function QualityScreen() {
  const [ncrs, setNcrs] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [createModal, setCreateModal] = useState(false);
  const [form, setForm] = useState({
    title: '', source: 'Incoming', severity: 'Minor', product: '', description: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Read-only offline support: the list view falls back to the last
      // cached response when there's no connection. Creating an NCR still
      // requires connectivity — not queued in this pass, matching the
      // Work Orders/Maintenance list precedent (see mobile section of the
      // root CLAUDE.md).
      const result = await fetchWithOfflineCache(
        `quality_ncr_list_${statusFilter}`,
        async () => (await getNcrs(statusFilter || undefined)).data.data.ncrs ?? [],
      );
      setNcrs(result.data);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      Alert.alert('Error', 'Could not load NCRs.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openDetail = async (id: number) => {
    try {
      const res = await getNcr(id);
      setSelected(res.data.data.ncr);
    } catch {
      Alert.alert('Error', 'Could not load NCR details.');
    }
  };

  const submitNcr = async () => {
    if (!form.title.trim()) {
      Alert.alert('Required', 'Title is required.');
      return;
    }
    setSubmitting(true);
    try {
      await createNcr({
        title: form.title.trim(),
        source: form.source,
        severity: form.severity,
        product: form.product.trim(),
        description: form.description.trim(),
      });
      setCreateModal(false);
      setForm({ title: '', source: 'Incoming', severity: 'Minor', product: '', description: '' });
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not create NCR.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={styles.screen}>
      <OfflineBanner isStale={isStale} cachedAt={cachedAt} />
      <View style={styles.topBar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
          {STATUSES.map((s) => (
            <TouchableOpacity
              key={s || 'all'}
              style={[styles.filterBtn, statusFilter === s && styles.filterBtnActive]}
              onPress={() => setStatusFilter(s)}
            >
              <Text style={[styles.filterLabel, statusFilter === s && styles.filterLabelActive]}>
                {s.replace(/_/g, ' ') || 'All'}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        <TouchableOpacity style={styles.newBtn} onPress={() => setCreateModal(true)}>
          <Text style={styles.newTxt}>+ New</Text>
        </TouchableOpacity>
      </View>

      {loading
        ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" />
        : (
          <FlatList
            data={ncrs}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.card} onPress={() => openDetail(item.id)}>
                <View style={styles.cardHeader}>
                  <Text style={styles.ncrNum}>{`NCR-${item.id}`}</Text>
                  <View style={styles.badges}>
                    <View style={[styles.severityBadge, { backgroundColor: SEVERITY_COLORS[item.severity] ?? '#888' }]}>
                      <Text style={styles.severityTxt}>{(item.severity ?? '').toUpperCase()}</Text>
                    </View>
                    <StatusBadge status={item.status} />
                  </View>
                </View>
                <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
                <Text style={styles.meta}>
                  {[
                    item.source && `Source: ${item.source}`,
                    item.product && `Product: ${item.product}`,
                    item.detected_date,
                  ].filter(Boolean).join('  ·  ')}
                </Text>
              </TouchableOpacity>
            )}
            ListEmptyComponent={<Text style={styles.empty}>No NCRs found.</Text>}
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
            <Text style={styles.modalTitle}>{`NCR-${selected.id}`}</Text>
            <View style={styles.badges}>
              <View style={[styles.severityBadge, { backgroundColor: SEVERITY_COLORS[selected.severity] ?? '#888' }]}>
                <Text style={styles.severityTxt}>{(selected.severity ?? '').toUpperCase()}</Text>
              </View>
              <StatusBadge status={selected.status} />
            </View>
            <Text style={styles.detailTitle}>{selected.title}</Text>

            {[
              ['Source', selected.source],
              ['Product', selected.product],
              ['Owner', selected.owner],
              ['Reported by', selected.created_by],
              ['Detected', selected.detected_date],
              ['Disposition', selected.disposition],
              ['Closed', selected.closed_date],
            ].filter(([, v]) => v).map(([label, value]) => (
              <View key={label} style={styles.infoRow}>
                <Text style={styles.infoLabel}>{label}</Text>
                <Text style={styles.infoValue}>{value}</Text>
              </View>
            ))}

            {selected.notes ? (
              <View style={{ marginTop: 16 }}>
                <Text style={styles.sectionTitle}>Notes</Text>
                <Text style={styles.bodyText}>{selected.notes}</Text>
              </View>
            ) : null}
          </ScrollView>
        )}
      </Modal>

      {/* Create NCR Modal */}
      <Modal visible={createModal} animationType="slide" onRequestClose={() => setCreateModal(false)}>
        <ScrollView style={styles.modal}>
          <TouchableOpacity style={styles.closeBtn} onPress={() => setCreateModal(false)}>
            <Text style={styles.closeTxt}>Cancel</Text>
          </TouchableOpacity>
          <Text style={styles.modalTitle}>New NCR</Text>

          <Text style={styles.fieldLabel}>Title *</Text>
          <TextInput
            style={styles.fieldInput}
            placeholder="Describe the nonconformance"
            value={form.title}
            onChangeText={(v) => setForm((f) => ({ ...f, title: v }))}
            autoFocus
          />

          <Text style={styles.fieldLabel}>Severity</Text>
          <View style={styles.chipRow}>
            {SEVERITIES.map((s) => (
              <TouchableOpacity
                key={s}
                style={[styles.chip, form.severity === s && { backgroundColor: SEVERITY_COLORS[s] }]}
                onPress={() => setForm((f) => ({ ...f, severity: s }))}
              >
                <Text style={[styles.chipTxt, form.severity === s && { color: '#fff' }]}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.fieldLabel}>Source</Text>
          <View style={styles.chipRow}>
            {SOURCES.map((s) => (
              <TouchableOpacity
                key={s}
                style={[styles.chip, form.source === s && styles.chipActive]}
                onPress={() => setForm((f) => ({ ...f, source: s }))}
              >
                <Text style={[styles.chipTxt, form.source === s && { color: '#fff' }]}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.fieldLabel}>Product / Part (optional)</Text>
          <TextInput
            style={styles.fieldInput}
            placeholder="Product name or part number"
            value={form.product}
            onChangeText={(v) => setForm((f) => ({ ...f, product: v }))}
          />

          <Text style={styles.fieldLabel}>Description (optional)</Text>
          <TextInput
            style={[styles.fieldInput, styles.multiline]}
            placeholder="Additional details..."
            value={form.description}
            onChangeText={(v) => setForm((f) => ({ ...f, description: v }))}
            multiline
            numberOfLines={4}
          />

          <TouchableOpacity
            style={[styles.submitLargeBtn, submitting && { opacity: 0.6 }]}
            onPress={submitNcr}
            disabled={submitting}
          >
            {submitting
              ? <ActivityIndicator color="#fff" />
              : <Text style={styles.submitLargeTxt}>Submit NCR</Text>
            }
          </TouchableOpacity>
        </ScrollView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:         { flex: 1, backgroundColor: '#f4f6fb' },
  topBar:         { flexDirection: 'row', alignItems: 'center', paddingRight: 12, paddingVertical: 8, paddingLeft: 12 },
  filterBtn:      { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#fff', marginRight: 8, borderWidth: 1, borderColor: '#ddd' },
  filterBtnActive: { backgroundColor: '#1a73e8', borderColor: '#1a73e8' },
  filterLabel:    { fontSize: 13, color: '#555', fontWeight: '500' },
  filterLabelActive: { color: '#fff' },
  newBtn:         { backgroundColor: '#1a73e8', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 7, marginLeft: 8 },
  newTxt:         { color: '#fff', fontSize: 13, fontWeight: '700' },
  card:           { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  cardHeader:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  badges:         { flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap' },
  ncrNum:         { fontWeight: '700', fontSize: 14, color: '#1a1a2e' },
  severityBadge:  { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3 },
  severityTxt:    { color: '#fff', fontSize: 11, fontWeight: '700' },
  title:          { color: '#333', fontSize: 13, marginBottom: 6, lineHeight: 19 },
  meta:           { color: '#888', fontSize: 12 },
  empty:          { textAlign: 'center', color: '#999', marginTop: 40 },
  modal:          { flex: 1, backgroundColor: '#f4f6fb', padding: 20 },
  closeBtn:       { marginBottom: 16, marginTop: 12 },
  closeTxt:       { color: '#1a73e8', fontSize: 16, fontWeight: '600' },
  modalTitle:     { fontSize: 20, fontWeight: '700', color: '#1a1a2e', marginBottom: 10 },
  detailTitle:    { fontSize: 15, color: '#444', marginTop: 12, marginBottom: 16, lineHeight: 22 },
  infoRow:        { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  infoLabel:      { color: '#888', fontSize: 13 },
  infoValue:      { color: '#1a1a2e', fontSize: 13, fontWeight: '600', flex: 1, textAlign: 'right', marginLeft: 12 },
  sectionTitle:   { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginBottom: 6 },
  bodyText:       { fontSize: 13, color: '#555', lineHeight: 21 },
  fieldLabel:     { fontSize: 13, fontWeight: '600', color: '#555', marginBottom: 6, marginTop: 16 },
  fieldInput:     { borderWidth: 1, borderColor: '#ddd', borderRadius: 10, padding: 12, fontSize: 14, backgroundColor: '#fff' },
  multiline:      { minHeight: 90, textAlignVertical: 'top' },
  chipRow:        { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip:           { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 16, borderWidth: 1, borderColor: '#ddd', backgroundColor: '#fff' },
  chipActive:     { backgroundColor: '#1a73e8', borderColor: '#1a73e8' },
  chipTxt:        { fontSize: 13, color: '#555', fontWeight: '500' },
  submitLargeBtn: { backgroundColor: '#1a73e8', borderRadius: 12, padding: 16, alignItems: 'center', marginTop: 28, marginBottom: 40 },
  submitLargeTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
