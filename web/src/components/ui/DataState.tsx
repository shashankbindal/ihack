import type { ReactNode } from "react";
import { Notice } from "./Notice";

interface DataStateProps<T> {
  data: T | null;
  error: string | null;
  children: (data: T) => ReactNode;
}

export function DataState<T>({ data, error, children }: DataStateProps<T>) {
  if (error) return <Notice tone="warn" title="Could not load page data">{error}</Notice>;
  if (!data) {
    return (
      <div className="flex items-center gap-3 py-10 text-sm text-muted" role="status">
        <span className="size-4 animate-spin rounded-full border-2 border-line border-t-ink" />
        Loading
      </div>
    );
  }
  return <>{children(data)}</>;
}
