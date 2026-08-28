import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

interface Props {
  /** True when the screen is showing a cached response instead of a fresh one. */
  isStale?: boolean;
  cachedAt?: string | null;
  /** Number of mutations queued locally, waiting to sync once back online. */
  queuedCount?: number;
}

export default function OfflineBanner({ isStale, cachedAt, queuedCount }: Props) {
  if (!isStale && !queuedCount) return null;
  return (
    <View style={styles.banner}>
      {isStale && (
        <Text style={styles.text}>
          Offline — showing data from {cachedAt ? new Date(cachedAt).toLocaleTimeString() : 'earlier'}
        </Text>
      )}
      {!!queuedCount && (
        <Text style={styles.text}>
          {queuedCount} action{queuedCount === 1 ? '' : 's'} waiting to sync
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: '#fff3cd',
    paddingVertical: 6,
    paddingHorizontal: 12,
    alignItems: 'center',
  },
  text: { color: '#856404', fontSize: 12, fontWeight: '600' },
});
