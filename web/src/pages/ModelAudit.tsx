import { useState } from "react";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { DataState } from "../components/ui/DataState";
import { Notice, NotBuilt } from "../components/ui/Notice";
import { PageHeader } from "../components/ui/PageHeader";
import { Table, Td, Th } from "../components/ui/Table";
import { useStaticData } from "../hooks/useStaticData";
import { formatCompactInr, formatCount, formatPct, formatSignedPct } from "../lib/format";
import { DATA_SOURCES, NOT_USED_SOURCES } from "../lib/sources";
import type { CoverageBlock, GradeBlock, Metrics, ModelName, Protocol } from "../lib/types";

const MODEL_ORDER: ModelName[] = ["B0", "B1", "B2", "B3", "M+"];
const PIPELINE_STEPS: { key: string; label: string; note: string }[] = [
  { key: "raw", label: "Raw listings", note: "Four city files from the Kaggle dataset" },
  { key: "valid", label: "Valid", note: "Price, area and BHK parse and fall in bounds" },
  { key: "amenities_stated", label: "Amenities stated", note: "Listings with no amenity information dropped" },
  { key: "deduplicated", label: "Deduplicated", note: "Near-identical listings removed" },
  { key: "outliers_removed", label: "Outliers removed", note: "Robust-z on log price per sq.ft, per city" },
  { key: "geocoded", label: "Geocoded", note: "Locality-level coordinates only" },
];

type ProtocolKey = "spatial" | "seen";

export function ModelAudit() {
  const metrics = useStaticData<Metrics>("metrics.json");
  return (
    <>
      <PageHeader
        title="Model governance and data sources"
        description="Everything on this page is read from the evaluation output of the prototype run. Nothing is typed in by hand."
      />
      <DataState data={metrics.data} error={metrics.error}>
        {(m) => <Audit metrics={m} />}
      </DataState>
    </>
  );
}

function Audit({ metrics }: { metrics: Metrics }) {
  const [protocolKey, setProtocolKey] = useState<ProtocolKey>("spatial");
  const protocol: Protocol = protocolKey === "spatial" ? metrics : metrics.seen_locality;
  const coverage: CoverageBlock = protocolKey === "spatial" ? metrics.coverage_80 : metrics.coverage_80.seen_locality;
  const grades: GradeBlock = protocolKey === "spatial" ? metrics.grades : metrics.grades_seen_locality;
  const sample = Object.values(protocol.significance)[0];
  const indistinct = Object.entries(protocol.significance)
    .filter(([, test]) => !test.ci_excludes_zero)
    .map(([name]) => name);

  return (
    <div className="space-y-6">
      <Notice title="Ground truth is asking price">
        All errors are measured against listing asking prices from a 2020 snapshot, not registered transactions or bank
        valuations. They show the method working on public data, not the accuracy a lender would see on its own
        collateral data.
      </Notice>

      <Card title="Data pipeline" subtitle="Rows surviving each cleaning step, applied before any train and test split.">
        <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          {PIPELINE_STEPS.map((step) => {
            const counts = metrics.data.row_counts_by_step[step.key];
            return (
              <li key={step.key} className="rounded-md border border-line p-3.5">
                <p className="text-xs font-semibold text-ink">{step.label}</p>
                <p className="num mt-1.5 text-2xl font-semibold">{formatCount(counts.total)}</p>
                <p className="mt-1.5 text-xs leading-snug text-muted">{step.note}</p>
              </li>
            );
          })}
        </ol>
        <p className="mt-4 text-xs leading-relaxed text-muted">
          Listings with every amenity coded as not mentioned were dropped because their price spread around the
          locality median is three to four times that of complete listings. Share of such listings: Bangalore{" "}
          {formatPct(metrics.data.amenity_missing_evidence.Bangalore.share_all_missing, 0)}, Chennai{" "}
          {formatPct(metrics.data.amenity_missing_evidence.Chennai.share_all_missing, 0)}, Hyderabad{" "}
          {formatPct(metrics.data.amenity_missing_evidence.Hyderabad.share_all_missing, 0)}, Mumbai{" "}
          {formatPct(metrics.data.amenity_missing_evidence.Mumbai.share_all_missing, 0)}.
        </p>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">Evaluation protocol</h2>
        <div className="inline-flex rounded-md border border-line bg-surface p-0.5" role="group" aria-label="Evaluation protocol">
          {[
            { key: "spatial" as const, label: "Unseen neighbourhood (primary)" },
            { key: "seen" as const, label: "Seen locality, unseen project" },
          ].map((option) => (
            <button
              key={option.key}
              aria-pressed={protocolKey === option.key}
              onClick={() => setProtocolKey(option.key)}
              className={`h-8 cursor-pointer rounded px-3 text-sm font-medium ${
                protocolKey === option.key ? "bg-ink text-white" : "text-muted hover:bg-hover"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <Card
        title="Accuracy by segment, M+ model"
        subtitle={
          protocolKey === "spatial"
            ? "Five-fold CV with whole H3 res-7 cells held out. Errors are percent of asking price."
            : metrics.seen_locality.note
        }
        flush
      >
        <SegmentTable metrics={metrics} protocol={protocol} coverage={coverage} />
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Ablation ladder" subtitle="Each model adds one layer. All rows on the same held-out listings." flush>
          <Table label="Ablation ladder">
            <thead>
              <tr>
                <Th>Model</Th>
                <Th numeric>MdAPE</Th>
                <Th numeric>MAPE</Th>
                <Th numeric>PPE10</Th>
                <Th numeric>COD</Th>
                <Th numeric>PRD</Th>
              </tr>
            </thead>
            <tbody>
              {MODEL_ORDER.map((name) => {
                const row = protocol.models[name];
                return (
                  <tr key={name}>
                    <Td>
                      <span className="num font-semibold">{name}</span>
                      <span className="block max-w-xs text-xs text-muted">{metrics.model_descriptions[name]}</span>
                    </Td>
                    <Td numeric>{formatPct(row.mdape)}</Td>
                    <Td numeric>{formatPct(row.mape)}</Td>
                    <Td numeric>{formatPct(row.ppe10)}</Td>
                    <Td numeric>{row.cod.toFixed(1)}</Td>
                    <Td numeric>{row.prd.toFixed(3)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </Card>

        <Card title="Significance of M+" subtitle="Paired bootstrap of the MdAPE difference, resampling whole H3 cells." flush>
          <Table label="Significance of M+ against each baseline">
            <thead>
              <tr>
                <Th>Comparison</Th>
                <Th numeric>Change in MdAPE</Th>
                <Th numeric>95% interval</Th>
                <Th>Excludes zero</Th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(protocol.significance).map(([name, test]) => (
                <tr key={name}>
                  <Td className="num">{name.replace("_vs_", " vs ")}</Td>
                  <Td numeric>{formatSignedPct(test.delta_mdape, 2)}</Td>
                  <Td numeric>
                    {test.ci95[0].toFixed(2)} to {test.ci95[1].toFixed(2)}
                  </Td>
                  <Td>
                    <Badge tone={test.ci_excludes_zero ? "ok" : "neutral"}>{test.ci_excludes_zero ? "Yes" : "No"}</Badge>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <p className="border-t border-line p-4 text-xs leading-relaxed text-muted">
            {sample.n_clusters} clusters, {formatCount(sample.n_boot)} draws.{" "}
            {indistinct.length
              ? `Not distinguishable from zero: ${indistinct.map((name) => name.replace("_vs_", " vs ")).join(", ")}.`
              : "Every difference excludes zero."}
          </p>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Interval coverage, nominal 80%" subtitle={coverage === metrics.coverage_80 ? metrics.coverage_80.method : "Same method, seen-locality protocol"} flush>
          <Table label="Interval coverage by city and price band">
            <thead>
              <tr>
                <Th>Segment</Th>
                <Th numeric>Listings</Th>
                <Th numeric>Coverage</Th>
                <Th numeric>Median width</Th>
              </tr>
            </thead>
            <tbody>
              <CoverageRow name="All listings" cell={coverage.overall} />
              {Object.entries(coverage.per_city).map(([name, cell]) => (
                <CoverageRow key={name} name={name} cell={cell} />
              ))}
              {Object.entries(coverage.per_price_band).map(([band, cell]) => (
                <CoverageRow key={band} name={bandLabel(band, metrics.price_band_edges_inr)} cell={cell} />
              ))}
            </tbody>
          </Table>
        </Card>

        <Card
          title="Confidence grades and routing"
          subtitle={`Grade from interval half-width: A up to ${formatPct(grades.thresholds_half_width.A * 100, 0)}, B up to ${formatPct(grades.thresholds_half_width.B * 100, 0)}, C up to ${formatPct(grades.thresholds_half_width.C * 100, 0)}, else D.`}
          flush
        >
          <Table label="Confidence grades">
            <thead>
              <tr>
                <Th>Grade</Th>
                <Th numeric>Share</Th>
                <Th numeric>Listings</Th>
                <Th numeric>MdAPE</Th>
                <Th numeric>Over-valued by 20% or more</Th>
              </tr>
            </thead>
            <tbody>
              {(Object.entries(grades.by_grade) as [string, GradeBlock["by_grade"]["A"]][]).map(([grade, row]) => (
                <tr key={grade}>
                  <Td className="font-semibold">Grade {grade}</Td>
                  <Td numeric>{formatPct(row.share)}</Td>
                  <Td numeric>{formatCount(row.n)}</Td>
                  <Td numeric>{row.mdape === undefined ? "n/a" : formatPct(row.mdape)}</Td>
                  <Td numeric>{row.overval20 === undefined ? "n/a" : formatPct(row.overval20)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <p className="border-t border-line p-4 text-xs leading-relaxed text-muted">
            Most unseen-neighbourhood cases land in grade D because the calibrated 80% range is wide (median{" "}
            {formatPct(metrics.interval_width_median, 0)} of value). The prototype does not claim a safe auto-accept
            share on unseen neighbourhoods: its operating-point rule found no threshold that meets the target.
          </p>
        </Card>
      </div>

      <Card title="Data sources and licences" subtitle="Status refers to this prototype, not to a production deployment." flush>
        <Table label="Data sources">
          <thead>
            <tr>
              <Th>Source</Th>
              <Th>Used for</Th>
              <Th>Licence</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {DATA_SOURCES.map((source) => (
              <tr key={source.name}>
                <Td>
                  <a href={source.url} target="_blank" rel="noreferrer" className="font-medium underline-offset-2 hover:underline">
                    {source.name}
                  </a>
                  <span className="block max-w-md text-xs text-muted">{source.note}</span>
                </Td>
                <Td className="max-w-xs text-muted">{source.usedFor}</Td>
                <Td className="text-muted">{source.licence}</Td>
                <Td>
                  <Badge tone="ok">Used in prototype</Badge>
                </Td>
              </tr>
            ))}
            {NOT_USED_SOURCES.map((source) => (
              <tr key={source.name}>
                <Td>
                  <span className="font-medium">{source.name}</span>
                </Td>
                <Td className="max-w-xs text-muted">{source.reason}</Td>
                <Td className="text-muted">n/a</Td>
                <Td>
                  <Badge>Not used</Badge>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Not run in this prototype" subtitle="Quoted from the evaluation output, with the reason for each.">
          <dl className="space-y-3">
            {Object.entries(metrics.not_run).map(([key, reason]) => (
              <div key={key}>
                <dt className="num text-xs font-semibold text-ink">{key}</dt>
                <dd className="mt-0.5 text-sm leading-relaxed text-muted">{reason}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <div className="space-y-6">
          <Card title="Drift monitoring">
            <NotBuilt title="Designed for production, not built">
              No drift statistics are computed or shown. The prototype is trained once on a static 2020 snapshot with no
              listing dates, so there is no stream to monitor. A production version would track input and error
              distributions against a held-back reference.
            </NotBuilt>
          </Card>
          <Card title="Service performance">
            <p className="num text-sm text-ink">
              p50 {Math.round(metrics.latency.p50_ms)} ms, p95 {Math.round(metrics.latency.p95_ms)} ms
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">
              {metrics.latency.n_requests} sequential requests. {metrics.latency.method}. {metrics.latency.hardware}.
              Hosted free-tier latency will differ.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}

const bandLabel = (band: string, edges: number[]): string => {
  const index = Number(band.slice(1)) - 1;
  return `Price band ${band} (${formatCompactInr(edges[index])} to ${formatCompactInr(edges[index + 1])})`;
};

function CoverageRow({ name, cell }: { name: string; cell: CoverageBlock["overall"] }) {
  return (
    <tr>
      <Td>{name}</Td>
      <Td numeric>{formatCount(cell.n)}</Td>
      <Td numeric>{formatPct(cell.coverage)}</Td>
      <Td numeric>{formatPct(cell.median_width_pct)}</Td>
    </tr>
  );
}

function SegmentTable({ metrics, protocol, coverage }: { metrics: Metrics; protocol: Protocol; coverage: CoverageBlock }) {
  const rows = [
    { name: "All listings", model: protocol.models["M+"], cover: coverage.overall },
    ...Object.entries(protocol.per_city).map(([name, models]) => ({ name, model: models["M+"], cover: coverage.per_city[name] })),
    ...Object.entries(protocol.per_price_band).map(([band, models]) => ({
      name: bandLabel(band, metrics.price_band_edges_inr),
      model: models["M+"],
      cover: coverage.per_price_band[band],
    })),
  ];
  return (
    <Table label="Accuracy by segment">
      <thead>
        <tr>
          <Th>Segment</Th>
          <Th numeric>Listings</Th>
          <Th numeric>MdAPE</Th>
          <Th numeric>MAPE</Th>
          <Th numeric>PPE10</Th>
          <Th numeric>COD</Th>
          <Th numeric>PRD</Th>
          <Th numeric>Bias</Th>
          <Th numeric>80% coverage</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ name, model, cover }) => (
          <tr key={name}>
            <Td className="whitespace-nowrap">{name}</Td>
            <Td numeric>{formatCount(model.n)}</Td>
            <Td numeric>{formatPct(model.mdape)}</Td>
            <Td numeric>{formatPct(model.mape)}</Td>
            <Td numeric>{formatPct(model.ppe10)}</Td>
            <Td numeric>{model.cod.toFixed(1)}</Td>
            <Td numeric>{model.prd.toFixed(3)}</Td>
            <Td numeric>{formatSignedPct(model.bias)}</Td>
            <Td numeric>{formatPct(cover.coverage)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
