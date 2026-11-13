import { Check, Flag, Printer } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { RangeGauge } from "../components/RangeGauge";
import { Waterfall } from "../components/Waterfall";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Notice } from "../components/ui/Notice";
import { PageHeader } from "../components/ui/PageHeader";
import { useStaticData } from "../hooks/useStaticData";
import { amenityLabel } from "../lib/amenities";
import {
  formatCompactInr,
  formatCount,
  formatDate,
  formatDistance,
  formatInr,
  formatPct,
  formatRate,
  formatSignedPct,
  ROUTING_LABEL,
} from "../lib/format";
import { GRADE_TONE, ROUTING_TONE, varianceTone } from "../lib/risk";
import { findStoredReport, readDecision, saveDecision, type Decision } from "../lib/store";
import type { PrecomputedValuation, ReportRecord } from "../lib/types";

export function Report() {
  const { id = "" } = useParams();
  const precomputed = useStaticData<Record<string, PrecomputedValuation>>("valuations.json");

  const record = useMemo<ReportRecord | null>(() => {
    const stored = findStoredReport(id);
    if (stored) return stored;
    const sample = precomputed.data?.[id];
    if (!sample) return null;
    return {
      id,
      city: sample.city,
      locality: sample.locality,
      quotedPriceInr: sample.asking_price_inr,
      source: "precomputed",
      valuation: sample.valuation,
    };
  }, [id, precomputed.data]);

  if (record) return <ReportView key={record.id} record={record} />;
  if (!precomputed.data && !precomputed.error) {
    return (
      <div role="status" className="py-10 text-sm text-muted">
        Loading report
      </div>
    );
  }
  return (
    <>
      <PageHeader title="Report not found" description="No valuation with this ID is stored in this browser or in the sample set." />
      <Notice tone="warn">
        Reports from the evaluate page are kept in this browser only.{" "}
        <Link to="/dashboard" className="font-semibold underline">
          Return to the overview
        </Link>{" "}
        to open a sample report.
      </Notice>
    </>
  );
}

function ReportView({ record }: { record: ReportRecord }) {
  const { valuation } = record;
  const { value, confidence, request } = valuation;
  const quoted = record.quotedPriceInr;
  const variance = quoted ? (quoted / value.point_inr - 1) * 100 : null;
  const stated = Object.entries(request.amenities).filter(([, present]) => present).map(([key]) => key);

  return (
    <article className="space-y-6">
      <PageHeader
        title={`${record.locality}, ${record.city}`}
        description="GharMoolya valuation report. Indicative, not a statutory valuation."
        actions={
          <Button onClick={() => window.print()}>
            <Printer aria-hidden className="size-4" />
            Export PDF
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-line bg-surface px-5 py-3 text-sm">
        <Meta label="Report ID" value={record.id} mono />
        <Meta
          label="Property"
          value={`${request.bhk} BHK apartment, ${request.resale ? "resale" : "new"}, ${formatCount(request.area_sqft)} sq.ft`}
        />
        <Meta label="Location basis" value="Locality centroid" />
        <Meta label="Model" value={valuation.model_version} mono />
        <Meta label="Source" value={record.source === "live" ? "Live API response" : "Pre-computed from a held-out listing"} />
        <div className="no-print ml-auto">
          <DecisionToggle id={record.id} routing={valuation.routing} />
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card title="Verdict" subtitle="Quoted price against the model's fair value" className="avoid-break">
          <div className="grid gap-5 sm:grid-cols-3">
            <Figure label={record.source === "live" ? "Quoted price" : "Asking price in listing"} value={quoted ? formatCompactInr(quoted) : "Not supplied"} detail={quoted ? formatRate(quoted / request.area_sqft) : undefined} />
            <Figure label="AI fair value" value={formatCompactInr(value.point_inr)} detail={formatRate(value.per_sqft_inr)} strong />
            <div>
              <p className="text-xs font-medium text-muted">Variance</p>
              {variance === null ? (
                <p className="mt-2 text-sm text-muted">Needs a quoted price</p>
              ) : (
                <>
                  <p className="num mt-1 text-2xl font-semibold">{formatSignedPct(variance)}</p>
                  <div className="mt-1.5">
                    <Badge tone={varianceTone(variance)}>
                      {variance > 0 ? "Asking above estimate" : "Asking below estimate"}
                    </Badge>
                  </div>
                </>
              )}
            </div>
          </div>
          <div className="mt-6">
            <RangeGauge
              low={value.low_inr}
              point={value.point_inr}
              high={value.high_inr}
              level={value.interval_level}
              marker={quoted ? { value: quoted, label: "Quoted" } : null}
            />
          </div>
          {quoted && (
            <p className="mt-3 text-sm text-ink">
              {quoted >= value.low_inr && quoted <= value.high_inr
                ? "The quoted price falls inside the model range."
                : "The quoted price falls outside the model range."}
            </p>
          )}
        </Card>

        <Card title="Confidence and routing" className="avoid-break">
          <div className="flex flex-wrap gap-2">
            <Badge tone={GRADE_TONE[confidence.grade]}>Grade {confidence.grade}</Badge>
            <Badge tone={ROUTING_TONE[valuation.routing]}>{ROUTING_LABEL[valuation.routing]}</Badge>
          </div>
          <dl className="num mt-4 grid grid-cols-2 gap-3 text-sm">
            <Detail label="Confidence score" value={confidence.score.toFixed(2)} />
            <Detail label="Range width" value={formatPct(confidence.interval_width_pct)} />
            <Detail label="Listings within 1 km" value={String(confidence.n_comparables)} />
            <Detail label="Data snapshot age" value={`${formatCount(confidence.data_freshness_days)} days`} />
          </dl>
          <p className="mt-4 text-xs font-semibold text-ink">Routing reasons</p>
          <ul className="mt-1.5 list-disc space-y-1 pl-4 text-sm text-muted">
            {valuation.routing_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </Card>
      </div>

      <Card
        title="What drives the estimate"
        subtitle="Top factors from the response, in rupees per sq.ft, applied largest first. Smaller factors and the model baseline are not part of the response."
        className="avoid-break"
      >
        <Waterfall factors={valuation.top_factors} />
      </Card>

      <Card
        title="Nearby listings used as comparables"
        subtitle="Training-set asking prices, adjusted by the model to this property. Locality-level coordinates, not transactions."
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {valuation.comparables.map((comp) => (
            <div key={comp.id} className="avoid-break rounded-md border border-line p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold">{comp.locality}</p>
                  <p className="num text-xs text-muted">{comp.id}</p>
                </div>
                <span className="num text-xs text-muted">{formatDistance(comp.distance_m)}</span>
              </div>
              <div className="mt-3">
                <div className="flex justify-between text-xs text-muted">
                  <span>Similarity</span>
                  <span className="num text-ink">{comp.similarity.toFixed(2)}</span>
                </div>
                <div className="mt-1 h-1 rounded-full bg-hover">
                  <div className="h-1 rounded-full bg-ink" style={{ width: `${Math.min(comp.similarity, 1) * 100}%` }} />
                </div>
              </div>
              <dl className="num mt-3 grid grid-cols-2 gap-y-1 text-xs">
                <dt className="font-sans text-muted">Size</dt>
                <dd className="text-right">{comp.bhk} BHK, {formatCount(comp.area_sqft)} sq.ft</dd>
                <dt className="font-sans text-muted">Listed rate</dt>
                <dd className="text-right">{formatInr(comp.listed_price_per_sqft)}</dd>
                <dt className="font-sans text-muted">Adjusted rate</dt>
                <dd className="text-right font-semibold">{formatInr(comp.adj_price_per_sqft)}</dd>
              </dl>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Lending view" className="avoid-break">
          <dl className="grid grid-cols-2 gap-3">
            <div className="rounded-md border border-line p-3">
              <dt className="text-xs text-muted">Max eligible loan, fair value</dt>
              <dd className="num mt-1 text-lg font-semibold">{formatCompactInr(valuation.lending.max_eligible_loan_inr)}</dd>
            </div>
            <div className="rounded-md border border-line p-3">
              <dt className="text-xs text-muted">Max eligible loan, low-end value</dt>
              <dd className="num mt-1 text-lg font-semibold">{formatCompactInr(valuation.lending.max_eligible_loan_on_low_inr)}</dd>
            </div>
          </dl>
          {request.loan_amount_inr !== null && valuation.lending.ltv_cap_for_requested_loan !== null && (
            <p className="mt-3 text-sm text-muted">
              Requested {formatCompactInr(request.loan_amount_inr)}: LTV cap{" "}
              <span className="num text-ink">{formatPct(valuation.lending.ltv_cap_for_requested_loan * 100, 0)}</span>.
            </p>
          )}
          <p className="mt-3 text-xs leading-relaxed text-muted">{valuation.lending.policy_note}</p>
        </Card>

        <Card title="Inputs and data lineage" className="avoid-break">
          <p className="text-xs font-semibold text-ink">Amenities stated as present</p>
          <p className="mt-1 text-sm text-muted">
            {stated.length ? stated.map(amenityLabel).join(", ") : "None stated as present"}
          </p>
          {valuation.inputs_not_used.length > 0 && (
            <p className="mt-3 text-sm text-muted">
              Supplied but not used by the model: <span className="num text-ink">{valuation.inputs_not_used.join(", ")}</span>
            </p>
          )}
          <ul className="mt-4 space-y-2 border-t border-line pt-3 text-xs text-muted">
            {valuation.data_lineage.map((item) => (
              <li key={item.source}>
                <span className="text-ink">{item.source}</span>. {item.licence}, fetched {formatDate(item.fetched_at)}.
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <p className="text-xs leading-relaxed text-muted">{valuation.disclaimer}</p>
    </article>
  );
}

function DecisionToggle({ id, routing }: { id: string; routing: ReportRecord["valuation"]["routing"] }) {
  const [decision, setDecision] = useState<Decision | null>(() => readDecision(id));
  const choose = (next: Decision) => {
    saveDecision(id, next);
    setDecision(next);
  };
  const options: { value: Decision; label: string; icon: typeof Check }[] = [
    { value: "approve", label: "Approve", icon: Check },
    { value: "flag", label: "Flag for inspection", icon: Flag },
  ];
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="inline-flex rounded-md border border-line p-0.5" role="group" aria-label="Reviewer decision">
        {options.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            aria-pressed={decision === value}
            onClick={() => choose(value)}
            className={`inline-flex h-8 cursor-pointer items-center gap-1.5 rounded px-3 text-sm font-medium ${
              decision === value ? (value === "approve" ? "bg-ok text-white" : "bg-bad text-white") : "text-muted hover:bg-hover"
            }`}
          >
            <Icon aria-hidden className="size-3.5" />
            {label}
          </button>
        ))}
      </div>
      <p className="text-[11px] text-muted">
        {routing === "PHYSICAL_VALUATION" ? "Model routing: physical valuation. " : ""}Kept in this browser only.
      </p>
    </div>
  );
}

function Meta({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-[11px] font-medium text-muted">{label}</p>
      <p className={`text-sm text-ink ${mono ? "num" : ""}`}>{value}</p>
    </div>
  );
}

function Figure({ label, value, detail, strong = false }: { label: string; value: string; detail?: string; strong?: boolean }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className={`num mt-1 text-2xl ${strong ? "font-semibold" : "font-medium"}`}>{value}</p>
      {detail && <p className="num text-xs text-muted">{detail}</p>}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-sans text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  );
}
