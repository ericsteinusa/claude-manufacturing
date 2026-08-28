import { useEffect, useState } from 'react';
import NetInfo from '@react-native-community/netinfo';

/** True unless NetInfo positively reports no connection or no internet
 * reachability — defaults optimistic (true) before the first event fires,
 * so a screen never flashes an "offline" state on cold start just because
 * the very first NetInfo callback hasn't arrived yet. */
export function useIsOnline(): boolean {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      setIsOnline(state.isConnected !== false && state.isInternetReachable !== false);
    });
    return unsubscribe;
  }, []);

  return isOnline;
}
