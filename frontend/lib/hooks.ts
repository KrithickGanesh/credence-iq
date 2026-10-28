"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useDebouncedValue<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refetch: () => void;
}

export function useApi<T>(key: string, loader: () => Promise<T>, enabled = true): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);
  const loaderRef = useRef(loader);
  const generation = useRef(0);
  loaderRef.current = loader;

  const refetch = useCallback(() => {
    generation.current += 1;
    const current = generation.current;
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    loaderRef
      .current()
      .then((value) => {
        if (generation.current === current) {
          setData(value);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (generation.current === current) {
          setError(reason instanceof Error ? reason.message : "Unexpected API error");
        }
      })
      .finally(() => {
        if (generation.current === current) setLoading(false);
      });
  }, [enabled]);

  useEffect(() => {
    refetch();
    return () => {
      generation.current += 1;
    };
  }, [key, refetch]);

  return { data, error, loading, refetch };
}
