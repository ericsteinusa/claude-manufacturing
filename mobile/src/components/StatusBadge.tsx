import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

// Matches the status colors used by the desktop app
const STATUS_COLORS: Record<string, string> = {
  // Work orders
  draft:       '#ffffff',
  open:        '#cce5ff',
  in_progress: '#fff3cd',
  completed:   '#d4edda',
  cancelled:   '#dcdcdc',
  // Requisitions
  submitted:      '#cce5ff',
  dept_approved:  '#d4edda',
  dept_denied:    '#f8d7da',
  approved:       '#d4edda',
  denied:         '#f8d7da',
  // Time-off
  pending:  '#fff3cd',
  // Purchase orders
  sent:     '#cce5ff',
  partial:  '#fff3cd',
  received: '#d4edda',
};

interface Props {
  status: string;
}

export default function StatusBadge({ status }: Props) {
  const bg = STATUS_COLORS[status] ?? '#f0f0f0';
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={styles.text}>{status.replace(/_/g, ' ')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  text: { fontSize: 12, fontWeight: '600', textTransform: 'capitalize' },
});
