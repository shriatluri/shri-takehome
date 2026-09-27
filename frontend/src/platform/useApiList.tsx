import { useCallback, useEffect, useRef, useState } from "react";

import { useIdentity } from "./identity";

type Loaded<T> = { sub: number | null; rows: T[] };

/**
 * Fetch a list, refetch it whenever the signed-in user changes, and optionally
 * poll. Polling replaces rows in place — no spinner between ticks — so a queue
 * open on screen picks up a new case without flickering under the reviewer.
 */
export function useApiList<T>(load: () => Promise<T[]>, pollMs?: number) {
  const { identity } = useIdentity();
  const sub = identity?.sub ?? null;
  const [loaded, setLoaded] = useState<Loaded<T>>({ sub: null, rows: [] });
  const [error, setError] = useState<string | null>(null);

  // The loader is defined inline by callers and changes identity every render;
  // keeping it in a ref lets the effect depend on the user alone.
  const loader = useRef(load);
  loader.current = load;

  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    const run = () =>
      loader
        .current()
        .then((rows) => {
          if (!cancelled) {
            setLoaded({ sub, rows });
            setError(null);
          }
        })
        .catch((e: Error) => {
          if (!cancelled) {
            setLoaded({ sub, rows: [] });
            setError(e.message);
          }
        });

    run();
    const timer = pollMs ? window.setInterval(run, pollMs) : undefined;
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sub, tick, pollMs]);

  // Rows belong to the user they were fetched for. Rendering them under anyone
  // else would show one role the other's data for as long as the fetch takes.
  const stale = loaded.sub !== sub;
  return {
    data: stale ? [] : loaded.rows,
    error: stale ? null : error,
    loading: stale,
    refresh,
  };
}
