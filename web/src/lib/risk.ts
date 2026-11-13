import type { Tone } from "../components/ui/Badge";
import type { Grade, Routing } from "./types";

export const ROUTING_TONE: Record<Routing, Tone> = {
  AUTO_ACCEPT: "ok",
  DESKTOP_REVIEW: "warn",
  PHYSICAL_VALUATION: "bad",
};

export const ROUTING_RISK: Record<Routing, string> = {
  AUTO_ACCEPT: "Low risk",
  DESKTOP_REVIEW: "Moderate risk",
  PHYSICAL_VALUATION: "High risk",
};

export const GRADE_TONE: Record<Grade, Tone> = { A: "ok", B: "ok", C: "warn", D: "bad" };

/** Asking above the estimate means the lender would be lending against an overstated price. */
export function varianceTone(variancePct: number): Tone {
  if (variancePct > 20) return "bad";
  if (variancePct > 10) return "warn";
  return "neutral";
}
