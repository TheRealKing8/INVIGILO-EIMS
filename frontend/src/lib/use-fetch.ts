"use client";

import { useCallback, useEffect, useState } from "react";

export type FetchState<T> = {
  data: T | null;
  error: Error | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
};

/**
 * Run ``fetcher`` on mount and re-run when ``deps`` change. Returns a
 * stable refresh callback so callers can wire it to a "Refresh" button.
 *
 * Usage::
 *
 *     const { data, isLoading, error, refresh } = useFetch(
 *       () => getExamSessions({ page: 1 }),
 *       [page],
 *     );
 */
export function useFetch<T>(
  fetcher: () => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const run = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void run();
  }, [run]);

  return { data, error, isLoading, refresh: run };
}
