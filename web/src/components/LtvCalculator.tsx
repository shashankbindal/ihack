import { useState } from "react";
import { formatCompactInr, formatInr, formatPct } from "../lib/format";
import type { Valuation } from "../lib/types";
import { Badge } from "./ui/Badge";
import { MoneyField } from "./ui/Field";

export function LtvCalculator({ valuation, initialLoan }: { valuation: Valuation; initialLoan: number | null }) {
  const [loan, setLoan] = useState<number | null>(initialLoan);
  const { lending, value } = valuation;

  const verdict =
    loan === null
      ? null
      : loan <= lending.max_eligible_loan_on_low_inr
        ? { tone: "ok" as const, text: "Within the cap on both fair and low-end value" }
        : loan <= lending.max_eligible_loan_inr
          ? { tone: "warn" as const, text: "Within the cap on fair value, above it on low-end value" }
          : { tone: "bad" as const, text: "Above the maximum eligible loan" };

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-line p-3">
          <dt className="text-xs text-muted">Max eligible loan, fair value</dt>
          <dd className="num mt-1 text-lg font-semibold">{formatCompactInr(lending.max_eligible_loan_inr)}</dd>
        </div>
        <div className="rounded-md border border-line p-3">
          <dt className="text-xs text-muted">Max eligible loan, low-end value</dt>
          <dd className="num mt-1 text-lg font-semibold">{formatCompactInr(lending.max_eligible_loan_on_low_inr)}</dd>
        </div>
      </dl>

      <MoneyField label="Loan amount to test" value={loan} onChange={setLoan} />

      {loan !== null && verdict && (
        <div className="space-y-2 rounded-md bg-canvas p-3 text-sm">
          <Badge tone={verdict.tone}>{verdict.text}</Badge>
          <p className="num text-ink">
            LTV on fair value {formatPct((loan / value.point_inr) * 100)}
            <span className="text-muted"> ({formatInr(loan)} / {formatInr(value.point_inr)})</span>
          </p>
          <p className="num text-ink">LTV on low-end value {formatPct((loan / value.low_inr) * 100)}</p>
        </div>
      )}

      {lending.ltv_cap_for_requested_loan !== null && (
        <p className="text-xs text-muted">
          LTV cap for the loan sent with this request:{" "}
          <span className="num text-ink">{formatPct(lending.ltv_cap_for_requested_loan * 100, 0)}</span>
        </p>
      )}
      <p className="text-xs leading-relaxed text-muted">{lending.policy_note}</p>
    </div>
  );
}
