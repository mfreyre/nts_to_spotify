import { useEffect, useState } from 'react';

// useState that survives full-page navigations (e.g. the OAuth round-trip)
// by mirroring the value into sessionStorage.
export default function usePersistentState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = sessionStorage.getItem(key);
      return raw !== null ? JSON.parse(raw) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Storage full or unavailable — state just won't survive navigation.
    }
  }, [key, value]);

  return [value, setValue];
}
