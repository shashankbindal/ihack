import { ArrowRight, Loader2, Play } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LtvCalculator } from "../components/LtvCalculator";
import { RangeGauge } from "../components/RangeGauge";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { DataState } from "../components/ui/DataState";
import { CONTROL_CLASS, Field, MoneyField, NumberInput } from "../components/ui/Field";
import { Notice } from "../components/ui/Notice";
import { PageHeader } from "../components/ui/PageHeader";
import { useStaticData } from "../hooks/useStaticData";
import { API_URL, requestValuation, ServiceUnreachableError, ValuationRejectedError } from "../lib/api";
import { amenityLabel } from "../lib/amenities";
import { formatCompactInr, formatRate, ROUTING_LABEL } from "../lib/format";
import { GRADE_TONE, ROUTING_TONE } from "../lib/risk";
import { saveReport } from "../lib/store";
import type { FormLocality, ReportRecord, Valuation, ValuationRequest } from "../lib/types";

const DISABLED_FIELDS = ["RERA ID", "Circle rate", "Facing", "Title status", "Furnishing"];

type RunState =
  | { phase: "idle" }
  | { phase: "running"; waking: boolean }
  | { phase: "done"; record: ReportRecord }
  | { phase: "error"; kind: "unreachable" | "rejected"; message: string };

interface FormState {
  city: string;
  locality: string;
  areaSqft: number;
  bhk: number;
  resale: boolean;
  amenities: Set<string>;
  loan: number | null;
  quotedPrice: number | null;
  floor: string;
  age: string;
}

const INITIAL_FORM: FormState = {
  city: "Bangalore",
  locality: "",
  areaSqft: 1200,
  bhk: 2,
  resale: true,
  amenities: new Set(),
  loan: null,
  quotedPrice: null,
  floor: "",
  age: "",
};

export function Evaluate() {
  const localities = useStaticData<FormLocality[]>("form_localities.json");
  const amenities = useStaticData<string[]>("amenities.json");

  return (
    <>
      <PageHeader
        title="New property valuation"
        description="Enter the fields the model uses and run a live request against the valuation service."
      />
      <DataState data={localities.data && amenities.data ? { localities: localities.data, amenities: amenities.data } : null} error={localities.error ?? amenities.error}>
        {(data) => <EvaluateWorkspace localities={data.localities} amenityKeys={data.amenities} />}
      </DataState>
    </>
  );
}

function EvaluateWorkspace({ localities, amenityKeys }: { localities: FormLocality[]; amenityKeys: string[] }) {
  const cities = useMemo(() => [...new Set(localities.map((l) => l.city))], [localities]);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [run, setRun] = useState<RunState>({ phase: "idle" });
  const controller = useRef<AbortController | null>(null);

  const cityLocalities = useMemo(() => localities.filter((l) => l.city === form.city), [localities, form.city]);
  const selected = cityLocalities.find((l) => l.locality === form.locality) ?? null;
  const patch = (changes: Partial<FormState>) => setForm((current) => ({ ...current, ...changes }));
  const canRun = selected !== null && form.areaSqft > 0 && run.phase !== "running";

  const submit = async () => {
    if (!selected) return;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setRun({ phase: "running", waking: false });

    const request: ValuationRequest = {
      lat: selected.lat,
      lon: selected.lon,
      type: "apartment",
      area_sqft: form.areaSqft,
      bhk: form.bhk,
      floor: form.floor === "" ? null : Number(form.floor),
      age: form.age === "" ? null : Number(form.age),
      resale: form.resale,
      amenities: Object.fromEntries([...form.amenities].map((key) => [key, true])),
      loan_amount_inr: form.loan,
    };

    try {
      const valuation = await requestValuation(request, abort.signal, () =>
        setRun({ phase: "running", waking: true }),
      );
      const record: ReportRecord = {
        id: valuation.valuation_id,
        city: valuation.city,
        locality: selected.locality,
        quotedPriceInr: form.quotedPrice,
        source: "live",
        valuation,
      };
      saveReport(record);
      setRun({ phase: "done", record });
    } catch (error) {
      if (abort.signal.aborted) return;
      if (error instanceof ValuationRejectedError) {
        setRun({ phase: "error", kind: "rejected", message: error.message });
      } else {
        const message = error instanceof ServiceUnreachableError ? error.message : "Valuation service unreachable";
        setRun({ phase: "error", kind: "unreachable", message });
      }
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <div className="space-y-6">
        <Card title="Property" subtitle="Locality gives the coordinates the model uses (locality-level, not street-level).">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="City" htmlFor="city">
              <select
                id="city"
                className={CONTROL_CLASS}
                value={form.city}
                onChange={(event) => patch({ city: event.target.value, locality: "" })}
              >
                {cities.map((city) => (
                  <option key={city}>{city}</option>
                ))}
              </select>
            </Field>
            <Field label="Locality" htmlFor="locality" hint={selected ? `${selected.n_listings} listings in the data` : undefined}>
              <select
                id="locality"
                className={CONTROL_CLASS}
                value={form.locality}
                onChange={(event) => patch({ locality: event.target.value })}
              >
                <option value="">Select locality</option>
                {cityLocalities.map((l) => (
                  <option key={l.locality} value={l.locality}>
                    {l.locality}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Area (sq.ft, as listed)" htmlFor="area" hint="Carpet or built-up basis is not distinguished in the data.">
              <NumberInput
                id="area"
                min={1}
                value={form.areaSqft || ""}
                onChange={(event) => patch({ areaSqft: Number(event.target.value) })}
              />
            </Field>
            <Field label="BHK" htmlFor="bhk">
              <select
                id="bhk"
                className={CONTROL_CLASS}
                value={form.bhk}
                onChange={(event) => patch({ bhk: Number(event.target.value) })}
              >
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <option key={n} value={n}>
                    {n} BHK
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <fieldset className="mt-4">
            <legend className="mb-1.5 text-xs font-semibold text-ink">Sale type</legend>
            <div className="inline-flex rounded-md border border-line p-0.5">
              {[
                { label: "Resale", value: true },
                { label: "New", value: false },
              ].map((option) => (
                <button
                  key={option.label}
                  type="button"
                  aria-pressed={form.resale === option.value}
                  onClick={() => patch({ resale: option.value })}
                  className={`h-8 cursor-pointer rounded px-4 text-sm font-medium ${
                    form.resale === option.value ? "bg-ink text-white" : "text-muted hover:bg-hover"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </fieldset>
        </Card>

        <Card title="Amenities" subtitle="Selected amenities are sent as present. Unselected ones are sent as not stated.">
          <div className="flex flex-wrap gap-2">
            {amenityKeys.map((key) => {
              const on = form.amenities.has(key);
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={on}
                  onClick={() => {
                    const next = new Set(form.amenities);
                    if (on) next.delete(key);
                    else next.add(key);
                    patch({ amenities: next });
                  }}
                  className={`cursor-pointer rounded-md border px-2.5 py-1.5 text-xs font-medium ${
                    on ? "border-ink bg-ink text-white" : "border-line text-muted hover:bg-hover hover:text-ink"
                  }`}
                >
                  {amenityLabel(key)}
                </button>
              );
            })}
          </div>
        </Card>

        <Card title="Loan and quoted price" subtitle="Optional.">
          <div className="grid gap-4 sm:grid-cols-2">
            <MoneyField label="Loan amount" value={form.loan} onChange={(loan) => patch({ loan })} />
            <MoneyField
              label="Quoted price"
              value={form.quotedPrice}
              onChange={(quotedPrice) => patch({ quotedPrice })}
              tag="Not a model input"
              hint="Only used to compare against the estimate in the report."
            />
          </div>
        </Card>

        <Card title="Other fields" subtitle="The API accepts floor and age but the training data has neither, so the model ignores them.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Floor" htmlFor="floor" tag="Ignored by model">
              <NumberInput id="floor" value={form.floor} onChange={(event) => patch({ floor: event.target.value })} />
            </Field>
            <Field label="Property age (years)" htmlFor="age" tag="Ignored by model">
              <NumberInput id="age" value={form.age} onChange={(event) => patch({ age: event.target.value })} />
            </Field>
            {DISABLED_FIELDS.map((label) => (
              <Field key={label} label={label} htmlFor={`off-${label}`} tag="Not used by prototype">
                <input id={`off-${label}`} disabled className={CONTROL_CLASS} />
              </Field>
            ))}
          </div>
        </Card>
      </div>

      <div className="space-y-6 lg:sticky lg:top-20 lg:self-start">
        <Card
          title="Live appraisal preview"
          action={
            <Button variant="primary" disabled={!canRun} onClick={submit}>
              {run.phase === "running" ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Play aria-hidden className="size-4" />}
              {run.phase === "running" ? "Running" : "Run valuation"}
            </Button>
          }
        >
          <Preview run={run} form={form} onRetry={submit} />
        </Card>
        {run.phase === "done" && (
          <Card title="LTV eligibility calculator" subtitle="Uses the lending block of the response.">
            <LtvCalculator key={run.record.id} valuation={run.record.valuation} initialLoan={form.loan} />
          </Card>
        )}
      </div>
    </div>
  );
}

function Preview({ run, form, onRetry }: { run: RunState; form: FormState; onRetry: () => void }) {
  if (run.phase === "idle") {
    return (
      <p className="py-6 text-sm leading-relaxed text-muted">
        Choose a city and locality, then run the valuation. The result is the live response of the valuation API, with
        value range, confidence grade, routing and drivers.
      </p>
    );
  }
  if (run.phase === "running") return <Progress waking={run.waking} />;
  if (run.phase === "error") {
    return run.kind === "unreachable" ? (
      <Notice tone="warn" title="Valuation service unreachable">
        <p>
          No response from <span className="num">{API_URL}</span>. The service may be offline or still starting. No
          estimate is shown, because none was returned.
        </p>
        <Button className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      </Notice>
    ) : (
      <Notice tone="warn" title="Request rejected">
        {run.message}
      </Notice>
    );
  }
  return <Result record={run.record} quoted={form.quotedPrice} />;
}

function Progress({ waking }: { waking: boolean }) {
  return (
    <div role="status" className="py-4">
      <div className="relative h-1.5 overflow-hidden rounded-full bg-hover">
        <div className="absolute inset-y-0 w-1/3 rounded-full bg-ink" style={{ animation: "indeterminate 1.4s ease-in-out infinite" }} />
      </div>
      <p className="mt-3 text-sm text-ink">{waking ? "Waking the valuation service" : "Waiting for the valuation service"}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted">
        {waking
          ? "The free hosting tier sleeps when idle and can take 30 to 60 seconds to start. This page checks the service and retries once it is ready."
          : "The request is in flight. A warm service answers in well under a second."}
      </p>
    </div>
  );
}

function Result({ record, quoted }: { record: ReportRecord; quoted: number | null }) {
  const { valuation } = record;
  const { value, confidence } = valuation;
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-medium text-muted">AI fair value</p>
        <p className="num mt-1 text-3xl font-semibold">{formatCompactInr(value.point_inr)}</p>
        <p className="num text-sm text-muted">{formatRate(value.per_sqft_inr)}, asking-rate basis</p>
      </div>
      <RangeGauge
        low={value.low_inr}
        point={value.point_inr}
        high={value.high_inr}
        level={value.interval_level}
        marker={quoted ? { value: quoted, label: "Quoted" } : null}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={GRADE_TONE[confidence.grade]}>Grade {confidence.grade}</Badge>
        <Badge tone={ROUTING_TONE[valuation.routing]}>{ROUTING_LABEL[valuation.routing]}</Badge>
        <span className="num text-xs text-muted">
          range width {confidence.interval_width_pct}% of value, {confidence.n_comparables} listings within 1 km
        </span>
      </div>
      <IgnoredInputs valuation={valuation} />
      <Link
        to={`/report/${record.id}`}
        className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3.5 text-sm font-semibold text-ink hover:bg-hover"
      >
        Open full report
        <ArrowRight aria-hidden className="size-4" />
      </Link>
    </div>
  );
}

function IgnoredInputs({ valuation }: { valuation: Valuation }) {
  if (valuation.inputs_not_used.length === 0) return null;
  return (
    <p className="text-xs text-muted">
      Ignored by the model, as reported by the API:{" "}
      <span className="num text-ink">{valuation.inputs_not_used.join(", ")}</span>
    </p>
  );
}
