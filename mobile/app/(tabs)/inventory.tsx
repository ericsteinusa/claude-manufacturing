import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, RefreshControl,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { getInventory, receiveStock } from '../../src/api/inventory';
import OfflineBanner from '../../src/components/OfflineBanner';
import { fetchWithOfflineCache } from '../../src/offline/cache';

export default function InventoryScreen() {
  const [products, setProducts] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any>({});
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [receiveModal, setReceiveModal] = useState<any>(null);
  const [receiveQty, setReceiveQty] = useState('');
  const [receiveRef, setReceiveRef] = useState('');
  const [receiving, setReceiving] = useState(false);
  const [isStale, setIsStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Read-only offline support: falls back to the last cached response
      // when there's no connection. Receiving stock still requires
      // connectivity — not queued in this pass, matching the Work
      // Orders/Maintenance/Quality list precedent (see mobile section of
      // the root CLAUDE.md).
      const result = await fetchWithOfflineCache(
        `inventory_list_${search}`,
        async () => {
          const res = await getInventory(search ? { q: search } : undefined);
          return { products: res.data.data.products ?? [], alerts: res.data.data.alerts ?? {} };
        },
      );
      setProducts(result.data.products);
      setAlerts(result.data.alerts);
      setIsStale(result.isStale);
      setCachedAt(result.cachedAt);
    } catch {
      Alert.alert('Error', 'Could not load inventory.');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const submitReceive = async () => {
    if (!receiveModal) return;
    const qty = parseFloat(receiveQty);
    if (!qty || qty <= 0) {
      Alert.alert('Invalid', 'Enter a valid quantity.');
      return;
    }
    setReceiving(true);
    try {
      const res = await receiveStock(receiveModal.id, qty, receiveRef.trim());
      Alert.alert('Stock Received', `New quantity: ${res.data.data.new_qty}`);
      setReceiveModal(null);
      setReceiveQty('');
      setReceiveRef('');
      load();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Could not receive stock.');
    } finally {
      setReceiving(false);
    }
  };

  const stockLevel = (p: any) => {
    const pct = p.reorder_point > 0 ? p.amount / p.reorder_point : 1;
    if (pct <= 0) return { color: '#d93025', label: 'Out' };
    if (pct < 1) return { color: '#f9ab00', label: 'Low' };
    return { color: '#34a853', label: 'OK' };
  };

  return (
    <View style={styles.screen}>
      <OfflineBanner isStale={isStale} cachedAt={cachedAt} />
      {(alerts.below_reorder > 0) && (
        <View style={styles.alertBanner}>
          <Text style={styles.alertBannerTxt}>
            {`⚠️  ${alerts.below_reorder} item${alerts.below_reorder > 1 ? 's' : ''} below reorder point`}
          </Text>
        </View>
      )}

      <View style={styles.searchRow}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search products..."
          value={search}
          onChangeText={setSearch}
          returnKeyType="search"
          onSubmitEditing={load}
          clearButtonMode="while-editing"
        />
      </View>

      {loading
        ? <ActivityIndicator style={{ marginTop: 40 }} size="large" color="#1a73e8" />
        : (
          <FlatList
            data={products}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
            renderItem={({ item }) => {
              const level = stockLevel(item);
              return (
                <View style={styles.card}>
                  <View style={styles.cardHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.productName}>{item.name}</Text>
                      {item.sku ? <Text style={styles.sku}>{item.sku}</Text> : null}
                    </View>
                    <View style={[styles.levelBadge, { backgroundColor: level.color }]}>
                      <Text style={styles.levelTxt}>{level.label}</Text>
                    </View>
                  </View>
                  <View style={styles.stockRow}>
                    <Text style={styles.qty}>{`${item.amount ?? 0} ${item.unit ?? 'units'}`}</Text>
                    {item.reorder_point > 0 && (
                      <Text style={styles.reorder}>{`Reorder @ ${item.reorder_point}`}</Text>
                    )}
                  </View>
                  {item.bin ? <Text style={styles.bin}>{`Bin: ${item.bin}`}</Text> : null}
                  <TouchableOpacity
                    style={styles.receiveBtn}
                    onPress={() => { setReceiveModal(item); setReceiveQty(''); setReceiveRef(''); }}
                  >
                    <Text style={styles.receiveTxt}>+ Receive Stock</Text>
                  </TouchableOpacity>
                </View>
              );
            }}
            ListEmptyComponent={<Text style={styles.empty}>No products found.</Text>}
            contentContainerStyle={{ padding: 12 }}
          />
        )
      }

      <Modal visible={!!receiveModal} animationType="slide" transparent onRequestClose={() => setReceiveModal(null)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Receive Stock</Text>
            {receiveModal && <Text style={styles.modalSubtitle}>{receiveModal.name}</Text>}

            <Text style={styles.fieldLabel}>Quantity *</Text>
            <TextInput
              style={styles.fieldInput}
              placeholder="Enter quantity"
              value={receiveQty}
              onChangeText={setReceiveQty}
              keyboardType="decimal-pad"
              autoFocus
            />

            <Text style={styles.fieldLabel}>Reference / PO # (optional)</Text>
            <TextInput
              style={styles.fieldInput}
              placeholder="e.g. PO-2026-001"
              value={receiveRef}
              onChangeText={setReceiveRef}
            />

            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setReceiveModal(null)}>
                <Text style={styles.cancelTxt}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.submitBtn, receiving && { opacity: 0.6 }]}
                onPress={submitReceive}
                disabled={receiving}
              >
                {receiving
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={styles.submitTxt}>Receive</Text>
                }
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen:          { flex: 1, backgroundColor: '#f4f6fb' },
  alertBanner:     { backgroundColor: '#fff3cd', padding: 12, borderBottomWidth: 1, borderBottomColor: '#ffc107' },
  alertBannerTxt:  { color: '#856404', fontSize: 13, fontWeight: '600', textAlign: 'center' },
  searchRow:       { paddingHorizontal: 12, paddingVertical: 8 },
  searchInput:     { backgroundColor: '#fff', borderRadius: 10, borderWidth: 1, borderColor: '#ddd', paddingHorizontal: 14, paddingVertical: 9, fontSize: 14 },
  card:            { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10, elevation: 1 },
  cardHeader:      { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 8 },
  productName:     { fontWeight: '700', fontSize: 15, color: '#1a1a2e' },
  sku:             { color: '#888', fontSize: 12, marginTop: 2 },
  levelBadge:      { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, marginLeft: 8 },
  levelTxt:        { color: '#fff', fontSize: 12, fontWeight: '700' },
  stockRow:        { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  qty:             { fontSize: 16, fontWeight: '700', color: '#1a1a2e' },
  reorder:         { fontSize: 12, color: '#888' },
  bin:             { fontSize: 12, color: '#888', marginBottom: 8 },
  receiveBtn:      { backgroundColor: '#e8f0fe', borderRadius: 8, paddingVertical: 8, alignItems: 'center', marginTop: 8 },
  receiveTxt:      { color: '#1a73e8', fontWeight: '600', fontSize: 13 },
  empty:           { textAlign: 'center', color: '#999', marginTop: 40 },
  modalOverlay:    { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalSheet:      { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  modalTitle:      { fontSize: 18, fontWeight: '700', color: '#1a1a2e', marginBottom: 4 },
  modalSubtitle:   { fontSize: 14, color: '#555', marginBottom: 16 },
  fieldLabel:      { fontSize: 13, fontWeight: '600', color: '#555', marginBottom: 6, marginTop: 12 },
  fieldInput:      { borderWidth: 1, borderColor: '#ddd', borderRadius: 10, padding: 12, fontSize: 14, backgroundColor: '#f9f9f9' },
  modalActions:    { flexDirection: 'row', gap: 12, marginTop: 24 },
  cancelBtn:       { flex: 1, borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#ddd' },
  cancelTxt:       { color: '#555', fontWeight: '600' },
  submitBtn:       { flex: 1, borderRadius: 10, padding: 14, alignItems: 'center', backgroundColor: '#1a73e8' },
  submitTxt:       { color: '#fff', fontWeight: '700' },
});
