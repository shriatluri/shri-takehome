import { useEffect, useState } from "react";

import { useIdentity } from "./identity";

type Loaded<T> = { sub: number | null; rows: T[] };

/** Fetch a list, and fetch it again whenever the signed-in user changes. */
export function useApiList<T>(load: () => Promise<T[]>) {
  const { identity } = useIdentity();
  const sub = identity?.sub ?? null;
  const [loaded, setLoaded] = useState<Loaded<T>>({ sub: null, rows: [] });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    load()
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
    return () => {
      cancelled = true;
    };
    // The loader is defined inline by callers; the identity is what changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sub]);

  // Rows belong to the user they were fetched for. Rendering them under anyone
  // else would show one role the other's data for as long as the fetch takes.
  const stale = loaded.sub !== sub;
  return { data: stale ? [] : loaded.rows, error: stale ? null : error, loading: stale };
}
