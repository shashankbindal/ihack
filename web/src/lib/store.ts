import type { ReportRecord } from "./types";

const REPORTS_KEY = "gharmoolya:reports";
const DECISIONS_KEY = "gharmoolya:decisions";
const MAX_STORED = 20;

export type Decision = "approve" | "flag";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be blocked or full; the app still works for the current page view.
  }
}

export const listStoredReports = (): ReportRecord[] => read<ReportRecord[]>(REPORTS_KEY, []);

export const findStoredReport = (id: string): ReportRecord | undefined =>
  listStoredReports().find((record) => record.id === id);

export function saveReport(record: ReportRecord): void {
  const others = listStoredReports().filter((item) => item.id !== record.id);
  write(REPORTS_KEY, [record, ...others].slice(0, MAX_STORED));
}

export const readDecision = (id: string): Decision | null =>
  read<Record<string, Decision>>(DECISIONS_KEY, {})[id] ?? null;

export function saveDecision(id: string, decision: Decision): void {
  write(DECISIONS_KEY, { ...read<Record<string, Decision>>(DECISIONS_KEY, {}), [id]: decision });
}
