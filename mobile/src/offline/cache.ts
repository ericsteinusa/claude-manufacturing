import AsyncStorage from '@react-native-async-storage/async-storage';

const CACHE_PREFIX = 'offline_cache:';

export interface CacheEntry<T> {
  data: T;
  cachedAt: string;
}

export async function getCached<T>(key: string): Promise<CacheEntry<T> | null> {
  const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CacheEntry<T>;
  } catch {
    return null;
  }
}

export async function setCached<T>(key: string, data: T): Promise<void> {
  const entry: CacheEntry<T> = { data, cachedAt: new Date().toISOString() };
  await AsyncStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry));
}

/** Fetch fresh data over the network, caching it on success. On failure
 * (offline, timeout, 5xx — any rejected fetcher), falls back to whatever
 * was last cached under *cacheKey* and marks the result stale rather than
 * surfacing a blank screen or an error alert. Re-throws only if there is
 * no cached fallback to show, matching this app's existing screens' own
 * "Alert.alert on failure" behavior for a true first-load-while-offline
 * case. */
export async function fetchWithOfflineCache<T>(
  cacheKey: string,
  fetcher: () => Promise<T>,
): Promise<{ data: T; isStale: boolean; cachedAt: string }> {
  try {
    const data = await fetcher();
    const cachedAt = new Date().toISOString();
    await setCached(cacheKey, data);
    return { data, isStale: false, cachedAt };
  } catch (err) {
    const cached = await getCached<T>(cacheKey);
    if (cached) {
      return { data: cached.data, isStale: true, cachedAt: cached.cachedAt };
    }
    throw err;
  }
}
