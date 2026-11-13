import { useEffect, useState } from "react";

const cache = new Map<string, unknown>();

export interface Loaded<T> {
  data: T | null;
  error: string | null;
}

export function useStaticData<T>(file: string): Loaded<T> {
  const [state, setState] = useState<Loaded<T>>(() => ({
    data: (cache.get(file) as T | undefined) ?? null,
    error: null,
  }));

  useEffect(() => {
    if (cache.has(file)) return;
    let cancelled = false;
    fetch(`/data/${file}`)
      .then((response) => {
        if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
        return response.json() as Promise<T>;
      })
      .then((data) => {
        cache.set(file, data);
        if (!cancelled) setState({ data, error: null });
      })
      .catch((error: Error) => {
        if (!cancelled) setState({ data: null, error: error.message });
      });
    return () => {
      cancelled = true;
    };
  }, [file]);

  return state;
}
