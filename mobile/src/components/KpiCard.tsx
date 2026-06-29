import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  accent?: string;
}

export default function KpiCard({ title, value, subtitle, accent = '#1a73e8' }: Props) {
  return (
    <View style={[styles.card, { borderLeftColor: accent }]}>
      <Text style={styles.title}>{title}</Text>
      <Text style={[styles.value, { color: accent }]}>{value}</Text>
      {subtitle ? <Text style={styles.sub}>{subtitle}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
  },
  title: { fontSize: 13, color: '#666', marginBottom: 4, fontWeight: '500' },
  value: { fontSize: 28, fontWeight: '700' },
  sub:   { fontSize: 12, color: '#888', marginTop: 4 },
});
