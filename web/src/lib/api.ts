import type { Valuation, ValuationRequest } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const REQUEST_TIMEOUT_MS = 20_000;
const HEALTH_TIMEOUT_MS = 8_000;
const WAKE_POLL_MS = 4_000;
const WAKE_LIMIT_MS = 90_000;

export class ServiceUnreachableError extends Error {
  constructor() {
    super("Valuation service unreachable");
  }
}

export class ValuationRejectedError extends Error {}

async function post(request: ValuationRequest, signal: AbortSignal): Promise<Valuation> {
  const response = await fetch(`${API_URL}/valuate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
    signal: AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
  });
  if (response.status === 422) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ValuationRejectedError(
      typeof body?.detail === "string" ? body.detail : "The request was rejected as invalid.",
    );
  }
  if (response.status >= 500) throw new ServiceUnreachableError();
  if (!response.ok) throw new ValuationRejectedError(`Unexpected response (HTTP ${response.status}).`);
  return (await response.json()) as Valuation;
}

async function isReady(signal: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, {
      signal: AbortSignal.any([signal, AbortSignal.timeout(HEALTH_TIMEOUT_MS)]),
    });
    return response.ok && ((await response.json()) as { ready?: boolean }).ready === true;
  } catch {
    return false;
  }
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(signal.reason);
    });
  });

/** Free-tier hosts sleep when idle, so a failed first call is followed by polling /health, then one retry. */
export async function requestValuation(
  request: ValuationRequest,
  signal: AbortSignal,
  onWaking: () => void,
): Promise<Valuation> {
  try {
    return await post(request, signal);
  } catch (error) {
    if (error instanceof ValuationRejectedError || signal.aborted) throw error;
  }
  onWaking();
  const deadline = Date.now() + WAKE_LIMIT_MS;
  while (Date.now() < deadline) {
    if (await isReady(signal)) {
      try {
        return await post(request, signal);
      } catch (error) {
        if (error instanceof ValuationRejectedError || signal.aborted) throw error;
        throw new ServiceUnreachableError();
      }
    }
    await sleep(WAKE_POLL_MS, signal);
  }
  throw new ServiceUnreachableError();
}
