import { useCallback, useEffect, useMemo, useState } from "react";

type Row = Record<string, any>;
type List = { items: Row[]; total: number };
type Request = (path: string, method?: string, body?: Row, signal?: AbortSignal) => Promise<any>;

// Session memory only: never share results between users or persist them to disk.
export function createPublicationCache(request: Request, now = Date.now) {
  const entries = new Map<string, { data: List; at: number }>();
  const pending = new Map<string, { controller: AbortController; promise: Promise<List> }>();
  const abort = (key: string) => {
    pending.get(key)?.controller.abort();
    pending.delete(key);
  };
  return {
    peek: (key: string | null) => key ? entries.get(key)?.data : undefined,
    abort,
    clear() {
      for (const key of pending.keys()) abort(key);
      entries.clear();
    },
    load(key: string, force = false): Promise<List> {
      const saved = entries.get(key);
      if (!force && saved && now() - saved.at < 30000) return Promise.resolve(saved.data);
      const running = pending.get(key);
      if (running) return running.promise;
      const controller = new AbortController();
      const promise = (async () => {
        try {
          const data: List = await request(key, "GET", undefined, controller.signal);
          if (controller.signal.aborted) throw new DOMException("Cancelled", "AbortError");
          entries.delete(key);
          entries.set(key, { data, at: now() });
          while (entries.size > 12) entries.delete(entries.keys().next().value!);
          return data;
        } finally {
          if (pending.get(key)?.controller === controller) pending.delete(key);
        }
      })();
      pending.set(key, { controller, promise });
      return promise;
    },
  };
}

export default function usePublicationList(
  request: Request, ready: boolean, key: string | null, delay: number, prefetch: string | null,
) {
  const cache = useMemo(() => createPublicationCache(request), [request]);
  const [result, setResult] = useState<{ cache: typeof cache; key: string; data: List } | null>(null);
  const [failure, setFailure] = useState<{ cache: typeof cache; key: string; message: string } | null>(null);
  const data = result?.cache === cache && result.key === key ? result.data : cache.peek(key);
  const error = failure?.cache === cache && failure.key === key ? failure.message : "";

  useEffect(() => () => cache.clear(), [cache]);
  const refresh = useCallback(async () => {
    if (!ready || !key) return;
    setFailure(null);
    try {
      const data = await cache.load(key, true);
      setResult({ cache, key, data });
    } catch (error) {
      if ((error as Error).name !== "AbortError") setFailure({ cache, key, message: (error as Error).message });
    }
  }, [ready, key, cache]);

  useEffect(() => {
    if (!ready || !key) return;
    let live = true;
    setFailure(null);
    const timer = window.setTimeout(() => {
      void cache.load(key, true).then((data) => {
        if (!live) return;
        setResult({ cache, key, data });
        setFailure(null);
        // One default list at a time; a click reuses this request if still pending.
        if (prefetch) void cache.load(prefetch).catch(() => {});
      }).catch((error: Error) => {
        if (live && error.name !== "AbortError") setFailure({ cache, key, message: error.message });
      });
    }, delay);
    return () => {
      live = false;
      clearTimeout(timer);
      // Default tab loads can finish for reuse. Abandon obsolete searches/filters.
      if (!prefetch) cache.abort(key);
    };
  }, [ready, key, delay, cache, prefetch]);

  return {
    items: data?.items || [], total: data?.total || 0,
    busy: Boolean(ready && key && !data && !error), error,
    refresh, invalidate: () => cache.clear(),
  };
}
