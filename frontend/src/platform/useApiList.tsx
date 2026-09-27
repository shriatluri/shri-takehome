import { useEffect, useState } from "react";

import { useIdentity } from "./identity";

/** Fetch a list, and fetch it again whenever the signed-in user changes. */
export function useApiList<T>(load: () => Promise<T[]>) {
  const { identity } = useIdentity();
  const [data, setData] = useState<T[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((rows) => {
        if (!cancelled) {
          setData(rows);
          setError(null);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setData([]);
          setError(e.message);
        }
      });
    return () => {
      cancelled = true;
    };
    // The loader is defined inline by callers; the identity is what changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [identity?.sub]);

  return { data, error };
}
