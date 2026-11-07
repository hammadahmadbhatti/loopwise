"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/** Fetch JSON for a path; re-fetches when the path changes. Pass null to skip. */
export function useApi<T>(path: string | null, opts: { pollMs?: number } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const seq = useRef(0);

  const load = useCallback(async (quiet = false) => {
    if (path === null) return;
    const id = ++seq.current;
    if (!quiet) setLoading(true);
    try {
      const result = await api<T>(path);
      if (id === seq.current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (id === seq.current) setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetching on path change
    void load();
  }, [load]);

  useEffect(() => {
    if (!opts.pollMs) return;
    const t = setInterval(() => void load(true), opts.pollMs);
    return () => clearInterval(t);
  }, [load, opts.pollMs]);

  return { data, error, loading, reload: load, setData };
}

/** Debounce a fast-changing value (search boxes). */
export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
