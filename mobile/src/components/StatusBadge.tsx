import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

// Matches the status colors used by the desktop app
const STATUS_COLORS: Record<string, string> = {
  // Work orders
  draft:       '#ffffff',
  open:        '#cce5ff',
  assigned:    '#cce5ff',
  in_progress: '#fff3cd',
  on_hold:     '#f8d7da',
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
  // Sales orders
  confirmed: '#cce5ff',
  shipped:   '#d4edda',
  invoiced:  '#d1ecf1',
  // Engineering projects
  planning:  '#e2e3e5',
  // Collection activities
  escalated: '#f8d7da',
  closed:    '#d4edda',
};

interface Props {
  status: string;
}

function normalize(status: string): string {
  return status.trim().toLowerCase().replace(/\s+/g, '_');
}

export default function StatusBadge({ status }: Props) {
  const bg = STATUS_COLORS[normalize(status)] ?? '#f0f0f0';
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
