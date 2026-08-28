import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiClient } from '../api/client';

const QUEUE_KEY = 'offline_mutation_queue';

export interface QueuedMutation {
  id: string;
  method: 'post' | 'put' | 'patch';
  url: string;
  body?: unknown;
  /** Short human-readable label shown in the pending-sync banner, e.g.
   * "Clock in". Not sent to the server — display only. */
  description: string;
  queuedAt: string;
}

async function readQueue(): Promise<QueuedMutation[]> {
  const raw = await AsyncStorage.getItem(QUEUE_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as QueuedMutation[];
  } catch {
    return [];
  }
}

async function writeQueue(queue: QueuedMutation[]): Promise<void> {
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

export async function enqueueMutation(
  method: QueuedMutation['method'],
  url: string,
  body: unknown,
  description: string,
): Promise<void> {
  const queue = await readQueue();
  queue.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    method,
    url,
    body,
    description,
    queuedAt: new Date().toISOString(),
  });
  await writeQueue(queue);
}

export async function getQueuedMutations(): Promise<QueuedMutation[]> {
  return readQueue();
}

/** Replay every queued mutation against the real API, in the order they
 * were queued, removing each one on success. Stops at the first failure
 * (still offline, or the request is now genuinely invalid) rather than
 * skipping ahead — replaying a later action before an earlier one that
 * hasn't landed yet could reorder real business events (e.g. a queued
 * clock-out replaying before a queued clock-in). Whatever failed and
 * everything queued after it stays in the queue for the next flush
 * attempt. */
export async function flushQueue(): Promise<{ succeeded: number; remaining: number }> {
  const queue = await readQueue();
  let succeeded = 0;
  let i = 0;
  for (; i < queue.length; i++) {
    const m = queue[i];
    try {
      await apiClient.request({ method: m.method, url: m.url, data: m.body });
      succeeded++;
    } catch {
      break;
    }
  }
  const remaining = queue.slice(i);
  await writeQueue(remaining);
  return { succeeded, remaining: remaining.length };
}
