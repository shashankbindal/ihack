const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export const formatInr = (value: number): string => `₹${inr.format(Math.round(value))}`;

export function formatCompactInr(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `₹${(value / 1e5).toFixed(1)} L`;
  return formatInr(value);
}

export const formatRate = (value: number): string => `${formatInr(value)}/sq.ft`;

export const formatCount = (value: number): string => inr.format(value);

export const formatPct = (value: number, digits = 1): string => `${value.toFixed(digits)}%`;

export const formatSignedPct = (value: number, digits = 1): string =>
  `${value > 0 ? "+" : value < 0 ? "-" : ""}${Math.abs(value).toFixed(digits)}%`;

export const formatDate = (iso: string): string =>
  new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

export const formatDistance = (metres: number): string =>
  metres >= 1000 ? `${(metres / 1000).toFixed(1)} km` : `${Math.round(metres)} m`;

export const ROUTING_LABEL = {
  AUTO_ACCEPT: "Auto-accept",
  DESKTOP_REVIEW: "Desktop review",
  PHYSICAL_VALUATION: "Physical valuation",
} as const;
