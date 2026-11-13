import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { DataState } from "../components/ui/DataState";
import { Notice } from "../components/ui/Notice";
import { PageHeader } from "../components/ui/PageHeader";
import { Stat } from "../components/ui/Stat";
import { Table, Td, Th } from "../components/ui/Table";
import { useStaticData } from "../hooks/useStaticData";
import { formatCompactInr, formatCount, formatInr, formatPct, formatSignedPct } from "../lib/format";
import { GRADE_TONE, ROUTING_RISK, ROUTING_TONE, varianceTone } from "../lib/risk";
import type { CityStat, Metrics, QueueRow } from "../lib/types";

const ASKING_COLOUR = "#94a3b8";
const MODEL_COLOUR = "#1e293b";

export function Dashboard() {
  const metrics = useStaticData<Metrics>("metrics.json");
  const queue = useStaticData<QueueRow[]>("queue.json");
  const cities = useStaticData<CityStat[]>("cities.json");

  return (
    <>
      <PageHeader
        title="Executive overview"
        description="Held-out model performance and a sample of valuations the engine had not seen, built from public listing data."
      />

      <div className="space-y-6">
        <DataState data={metrics.data} error={metrics.error}>
          {(m) => <KpiRow metrics={m} />}
        </DataState>

        <Card
          title="Sample valuation queue"
          subtitle="Twelve listings from areas the production engine was not trained on. Asking price versus model estimate."
          flush
        >
          <DataState data={queue.data} error={queue.error}>
            {(rows) => <QueueTable rows={rows} />}
          </DataState>
        </Card>

        <Card
          title="Median asking rate against median model estimate, by city"
          subtitle="Rupees per sq.ft. Model estimates are out-of-fold predictions for every cleaned listing in the city."
        >
          <DataState data={cities.data} error={cities.error}>
            {(stats) => <RegionalChart stats={stats} />}
          </DataState>
          <p className="mt-3 text-xs text-muted">
            No circle rates are in the prototype data, so asking rates are compared with the model estimate rather
            than an official reference rate.
          </p>
        </Card>

        <Notice title="What the numbers measure">
          Accuracy is measured against listing asking prices from a 2020 snapshot, not registered transaction values.
          Errors are percentage of asking price, on neighbourhoods held out of training.
        </Notice>
      </div>
    </>
  );
}

function KpiRow({ metrics }: { metrics: Metrics }) {
  const mplus = metrics.models["M+"];
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Held-out listings evaluated"
          value={formatCount(metrics.n_test)}
          caption="Cleaned listings in Mumbai, Bengaluru, Hyderabad and Chennai, each predicted by a model that never saw its H3 cell."
        />
        <Stat
          label="Median error, unseen neighbourhoods"
          value={formatPct(mplus.mdape)}
          caption={`MdAPE of the M+ model against asking price. ${formatPct(metrics.seen_locality.models["M+"].mdape)} when the locality is seen but the project is not.`}
        />
        <Stat
          label="80% range coverage"
          value={formatPct(metrics.coverage_80.overall.coverage)}
          caption={`Share of asking prices inside the stated range. Median range width is ${formatPct(metrics.coverage_80.overall.median_width_pct)} of value.`}
        />
        <Stat
          label="Routed to physical valuation"
          value={formatPct(metrics.grades.routing_share.PHYSICAL_VALUATION)}
          caption={`Grade D on unseen neighbourhoods. ${formatPct(metrics.grades.routing_share.DESKTOP_REVIEW)} go to desktop review and ${formatPct(metrics.grades.routing_share.AUTO_ACCEPT)} to auto-accept.`}
        />
      </div>
      <p className="text-xs text-muted">
        API latency on a laptop, single worker, {metrics.latency.n_requests} sequential requests:{" "}
        <span className="num text-ink">p50 {Math.round(metrics.latency.p50_ms)} ms</span>,{" "}
        <span className="num text-ink">p95 {Math.round(metrics.latency.p95_ms)} ms</span>.
      </p>
    </div>
  );
}

function QueueTable({ rows }: { rows: QueueRow[] }) {
  return (
    <Table label="Sample valuation queue">
      <thead>
        <tr>
          <Th>Listing ID</Th>
          <Th>Property</Th>
          <Th>Locality</Th>
          <Th numeric>Asking rate</Th>
          <Th numeric>Model fair value</Th>
          <Th numeric>Variance</Th>
          <Th>Risk</Th>
          <Th>
            <span className="sr-only">Action</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.listing_id} className="hover:bg-canvas">
            <Td className="num whitespace-nowrap font-medium">{row.listing_id}</Td>
            <Td className="whitespace-nowrap">
              {row.bhk} BHK, {row.resale ? "resale" : "new"}
              <span className="num block text-xs text-muted">{formatCount(row.area_sqft)} sq.ft</span>
            </Td>
            <Td>
              {row.locality}
              <span className="block text-xs text-muted">{row.city}</span>
            </Td>
            <Td numeric>
              {formatInr(row.asking_ppsf)}
              <span className="block text-xs text-muted">{formatCompactInr(row.asking_price_inr)}</span>
            </Td>
            <Td numeric>
              {formatInr(row.estimate_ppsf)}
              <span className="block text-xs text-muted">{formatCompactInr(row.estimate_inr)}</span>
            </Td>
            <Td numeric>
              <Badge tone={varianceTone(row.variance_pct)}>{formatSignedPct(row.variance_pct)}</Badge>
            </Td>
            <Td>
              <div className="flex flex-wrap gap-1.5">
                <Badge tone={ROUTING_TONE[row.routing]}>{ROUTING_RISK[row.routing]}</Badge>
                <Badge tone={GRADE_TONE[row.grade]}>Grade {row.grade}</Badge>
              </div>
            </Td>
            <Td>
              <Link
                to={`/report/${row.listing_id}`}
                className="inline-flex h-8 items-center gap-1 whitespace-nowrap rounded-md border border-line px-2.5 text-xs font-semibold text-ink hover:bg-hover"
              >
                Inspect report
                <ArrowUpRight aria-hidden className="size-3.5" />
              </Link>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function RegionalChart({ stats }: { stats: CityStat[] }) {
  const data = stats.map((s) => ({
    city: s.city,
    "Median asking rate": s.median_asking_ppsf,
    "Median model estimate": s.median_model_ppsf,
  }));
  return (
    <div className="h-72" role="img" aria-label="Median asking rate and median model estimate per sq.ft by city">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={4}>
          <CartesianGrid vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="city" tickLine={false} axisLine={{ stroke: "#e2e8f0" }} tick={{ fill: "#64748b", fontSize: 12 }} />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={56}
            tick={{ fill: "#64748b", fontSize: 12 }}
            tickFormatter={(value: number) => `${formatCount(value / 1000)}k`}
          />
          <Tooltip
            cursor={{ fill: "#f1f5f9" }}
            formatter={(value) => `${formatInr(Number(value))}/sq.ft`}
            contentStyle={{ border: "1px solid #e2e8f0", borderRadius: 6, boxShadow: "none", fontSize: 12 }}
          />
          <Legend iconType="square" wrapperStyle={{ fontSize: 12, color: "#64748b" }} />
          <Bar dataKey="Median asking rate" fill={ASKING_COLOUR} radius={[2, 2, 0, 0]} maxBarSize={44} isAnimationActive={false} />
          <Bar dataKey="Median model estimate" fill={MODEL_COLOUR} radius={[2, 2, 0, 0]} maxBarSize={44} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
