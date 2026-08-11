import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function useStoredPerPage(storageKey: string, fallback = 20): {
  perPage: number;
  setPerPage: (value: number) => void;
} {
  const [perPage, setPerPageState] = useState(() => {
    const stored = localStorage.getItem(storageKey);
    const parsed = stored ? Number(stored) : fallback;
    return [10, 20, 30, 50].includes(parsed) ? parsed : fallback;
  });

  function setPerPage(value: number) {
    setPerPageState(value);
    localStorage.setItem(storageKey, String(value));
  }

  return { perPage, setPerPage };
}
