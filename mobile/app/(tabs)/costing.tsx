import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getInventory } from '../../src/api/inventory';
import {
  getProductCost, rollStandardCost, getCostHistory,
  getGlAccounts, getWorkcenters, getProductRouting,
} from '../../src/api/costing';

export default function CostingScreen() {
  const [products, setProducts] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const [selected, setSelected] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [cost, setCost] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [routing, setRouting] = useState<any[]>([]);
  const [rolling, setRolling] = useState(false);

  const [workcentersModal, setWorkcentersModal] = useState(false);
  const [workcenters, setWorkcenters] = useState<any[]>([]);
  const [glModal, setGlModal] = useState(false);
  const [glAccounts, setGlAccounts] = useState<any[]>([]);
  const [referenceLoading, setReferenceLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getInventory(search ? { q: search } : undefined);
      setProducts(res.data.data.products ?? []);
    } catch {
      Alert.alert('Error', 'Could not load products.');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openDetail = async (product: any) => {
    setSelected(product);
    setDetailLoading(true);
    setCost(null);
    setHistory([]);
    setRouting([]);
    try {
      const [historyRes, routingRes] = await Promise.all([
        getCostHistory(product.id),
        getProductRouting(product.id),
      ]);
      setHistory(historyRes.data.data.history ?? []);
      setRouting(routingRes.data.data.steps ?? []);
    } catch {
      Alert.alert('Error', 'Could not load cost history or routing.');
    }
    try {
      const costRes = await getProductCost(product.id);
      setCost(costRes.data.data.cost ?? null);
    } catch {
      setCost(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const doRollStandardCost = async () => {
    if (!selected) return;
    setRolling(true);
    try {
      const res = await rollStandardCost(selected.id);
      setCost(res.data.data.cost ?? null);
      const historyRes = await getCostHistory(selected.id);
      setHistory(historyRes.data.data.history ?? []);
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not roll standard cost.');
    } finally {
      setRolling(false);
    }
  };

  const openWorkcenters = async () => {
    setWorkcentersModal(true);
    setReferenceLoading(true);
    try {
      const res = await getWorkcenters();
      setWorkcenters(res.data.data.workcenters ?? []);
    } catch {
      Alert.alert('Error', 'Could not load workcenters.');
    } finally {
      setReferenceLoading(false);
    }
  };

  const openGlAccounts = async () => {
    setGlModal(true);
    setReferenceLoading(true);
    try {
      const res = await getGlAccounts();
      setGlAccounts(res.data.data.accounts ?? []);
    } catch {
      Alert.alert('Error', 'Could not load GL accounts.');
    } finally {
      setReferenceLoading(false);
    }
  };

  return (
    <View style={styles.screen}>
      <View style={styles.headerRow}>
        <TouchableOpacity style={styles.headerBtn} onPress={openWorkcenters}>
          <Text style={styles.headerBtnTxt}>Workcenters</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.headerBtn} onPress={openGlAccounts}>
          <Text style={styles.headerBtnTxt}>GL Accounts</Text>
        </TouchableOpacity>
      </View>

      <TextInput
        style={styles.searchInput}
        placeholder="Search products…"
        value={search}
        onChangeText={setSearch}
        onSubmitEditing={load}
        returnKeyType="search"
      />

      {loading
        ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" />
        : (
          <FlatList
            data={products}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.card} onPress={() => openDetail(item)}>
                <Text style={styles.productName}>{item.name}</Text>
                <Text style={styles.productMeta}>
                  {`${item.item_type ?? 'buy'} · ${item.uom ?? 'ea'}`}
                </Text>
              </TouchableOpacity>
            )}
            ListEmptyComponent={<Text style={styles.empty}>No products found.</Text>}
            contentContainerStyle={{ padding: 12 }}
          />
        )
      }

      {/* Product Cost/Routing Detail Modal */}
      <Modal visible={!!selected} animationType="slide" onRequestClose={() => setSelected(null)}>
        {selected && (
          <ScrollView style={styles.modal}>
            <TouchableOpacity style={styles.closeBtn} onPress={() => setSelected(null)}>
              <Text style={styles.closeTxt}>← Back</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>{selected.name}</Text>

            {detailLoading ? (
              <ActivityIndicator style={{ marginTop: 24 }} size="large" color="#1a73e8" />
            ) : (
              <>
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Standard Cost</Text>
                  {cost ? (
                    <View style={styles.infoSection}>
                      {[
                        ['Material', cost.std_material_cost],
                        ['Labor', cost.std_labor_cost],
                        ['Overhead', cost.std_overhead_cost],
                        ['Total', cost.total_std_cost],
                        ['Effective', cost.effective_date],
                      ].map(([label, value]) => (
                        <View key={label as string} style={styles.infoRow}>
                          <Text style={styles.infoLabel}>{label}</Text>
                          <Text style={styles.infoValue}>{String(value)}</Text>
                        </View>
                      ))}
                    </View>
                  ) : (
                    <Text style={styles.bodyText}>No standard cost on record for this product.</Text>
                  )}
                  <TouchableOpacity
                    style={[styles.rollBtn, rolling && { opacity: 0.6 }]}
                    onPress={doRollStandardCost}
                    disabled={rolling}
                  >
                    {rolling
                      ? <ActivityIndicator color="#fff" />
                      : <Text style={styles.rollBtnTxt}>Roll Standard Cost</Text>}
                  </TouchableOpacity>
                </View>

                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Cost History</Text>
                  {history.length > 0 ? history.map((h) => (
                    <View key={h.id} style={styles.infoRow}>
                      <Text style={styles.infoLabel}>{h.effective_date}</Text>
                      <Text style={styles.infoValue}>{h.total_std_cost}</Text>
                    </View>
                  )) : (
                    <Text style={styles.bodyText}>No cost history on record.</Text>
                  )}
                </View>

                <View style={[styles.section, { marginBottom: 40 }]}>
                  <Text style={styles.sectionTitle}>Routing</Text>
                  {routing.length > 0 ? routing.map((step) => (
                    <View key={step.id} style={styles.infoRow}>
                      <Text style={styles.infoLabel}>
                        {`${step.operation_seq}. ${step.operation_name}`}
                      </Text>
                      <Text style={styles.infoValue}>
                        {`${step.workcenter_name ?? '—'} (${step.std_hours}h)`}
                      </Text>
                    </View>
                  )) : (
                    <Text style={styles.bodyText}>No routing defined for this product.</Text>
                  )}
                </View>
              </>
            )}
          </ScrollView>
        )}
      </Modal>

      {/* Workcenters Reference Modal */}
      <Modal visible={workcentersModal} animationType="slide" onRequestClose={() => setWorkcentersModal(false)}>
        <ScrollView style={styles.modal}>
          <TouchableOpacity style={styles.closeBtn} onPress={() => setWorkcentersModal(false)}>
            <Text style={styles.closeTxt}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.modalTitle}>Workcenters</Text>
          {referenceLoading ? (
            <ActivityIndicator style={{ marginTop: 24 }} size="large" color="#1a73e8" />
          ) : workcenters.length > 0 ? workcenters.map((wc) => (
            <View key={wc.id} style={styles.infoRow}>
              <Text style={styles.infoLabel}>{wc.name}</Text>
              <Text style={styles.infoValue}>{`${wc.dept ?? ''} · ${wc.capacity_hours_per_day}h/day`}</Text>
            </View>
          )) : (
            <Text style={styles.bodyText}>No workcenters on record.</Text>
          )}
        </ScrollView>
      </Modal>

      {/* GL Accounts Reference Modal */}
      <Modal visible={glModal} animationType="slide" onRequestClose={() => setGlModal(false)}>
        <ScrollView style={styles.modal}>
          <TouchableOpacity style={styles.closeBtn} onPress={() => setGlModal(false)}>
            <Text style={styles.closeTxt}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.modalTitle}>GL Accounts</Text>
          {referenceLoading ? (
            <ActivityIndicator style={{ marginTop: 24 }} size="large" color="#1a73e8" />
          ) : glAccounts.length > 0 ? glAccounts.map((acc) => (
            <View key={acc.id} style={styles.infoRow}>
              <Text style={styles.infoLabel}>{`${acc.account_number} — ${acc.category}`}</Text>
              <Text style={styles.infoValue}>{acc.description}</Text>
            </View>
          )) : (
            <Text style={styles.bodyText}>No GL accounts on record.</Text>
          )}
        </ScrollView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:       { flex: 1, backgroundColor: '#f4f6fb' },
  headerRow:    { flexDirection: 'row', gap: 8, paddingHorizontal: 12, paddingTop: 12 },
  headerBtn:    { flex: 1, borderRadius: 10, padding: 10, alignItems: 'center', backgroundColor: '#fff', borderWidth: 1, borderColor: '#ddd' },
  headerBtnTxt: { color: '#1a1a2e', fontWeight: '600', fontSize: 13 },
  searchInput:  { margin: 12, borderWidth: 1, borderColor: '#ddd', borderRadius: 10, padding: 12, fontSize: 14, backgroundColor: '#fff' },
  card:         { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  productName:  { fontWeight: '700', fontSize: 15, color: '#1a1a2e' },
  productMeta:  { color: '#888', fontSize: 12, marginTop: 4 },
  empty:        { textAlign: 'center', color: '#999', marginTop: 40 },
  modal:        { flex: 1, backgroundColor: '#f4f6fb', padding: 20 },
  closeBtn:     { marginBottom: 16, marginTop: 12 },
  closeTxt:     { color: '#1a73e8', fontSize: 16, fontWeight: '600' },
  modalTitle:   { fontSize: 20, fontWeight: '700', color: '#1a1a2e', marginBottom: 8 },
  section:      { marginTop: 20 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: '#1a1a2e', marginBottom: 8 },
  bodyText:     { fontSize: 13, color: '#555', lineHeight: 20, marginBottom: 4 },
  infoSection:  { marginTop: 4 },
  infoRow:      { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  infoLabel:    { color: '#888', fontSize: 13, flex: 1 },
  infoValue:    { color: '#1a1a2e', fontSize: 13, fontWeight: '600', flex: 1, textAlign: 'right', marginLeft: 12 },
  rollBtn:      { backgroundColor: '#1a73e8', borderRadius: 10, padding: 14, alignItems: 'center', marginTop: 14 },
  rollBtnTxt:   { color: '#fff', fontWeight: '700', fontSize: 15 },
});
