import { ArrowDown, ArrowUp } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { LocalityMap, type MapPoint } from "../components/LocalityMap";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { DataState } from "../components/ui/DataState";
import { CONTROL_CLASS, Field, NumberInput } from "../components/ui/Field";
import { Notice, NotBuilt } from "../components/ui/Notice";
import { PageHeader } from "../components/ui/PageHeader";
import { Table, Td, Th } from "../components/ui/Table";
import { useStaticData } from "../hooks/useStaticData";
import { formatCount, formatInr, formatPct, formatSignedPct } from "../lib/format";
import { median, percentileRank, quantile, sortAscending } from "../lib/stats";
import type { ListingTable, LocalityStat, Metrics } from "../lib/types";

interface Filters {
  city: string;
  bhk: string;
  sale: string;
}

interface LocalityRow {
  key: string;
  city: string;
  locality: string;
  lat: number;
  lon: number;
  asking: number[];
  p25: number;
  median: number;
  p75: number;
  modelMedian: number;
}

type SortKey = "locality" | "listings" | "median" | "spread" | "model" | "gap";

const MAX_ROWS = 20;

const matchesBhk = (bhk: number, filter: string) => filter === "all" || (filter === "4" ? bhk >= 4 : bhk === Number(filter));
const matchesSale = (resale: number, filter: string) => filter === "all" || (filter === "resale") === (resale === 1);

function buildRows(table: ListingTable, coordinates: Map<string, LocalityStat>, filters: Filters): LocalityRow[] {
  const groups = new Map<number, { asking: number[]; model: number[] }>();
  for (let i = 0; i < table.locality.length; i++) {
    const cityName = table.cities[table.city[i]];
    if (filters.city !== "all" && cityName !== filters.city) continue;
    if (!matchesBhk(table.bhk[i], filters.bhk) || !matchesSale(table.resale[i], filters.sale)) continue;
    const group = groups.get(table.locality[i]) ?? { asking: [], model: [] };
    group.asking.push(table.asking_ppsf[i]);
    group.model.push(table.model_ppsf[i]);
    groups.set(table.locality[i], group);
  }

  const rows: LocalityRow[] = [];
  for (const [index, group] of groups) {
    const { city, name } = table.localities[index];
    const place = coordinates.get(`${city}|${name}`);
    if (!place) continue;
    const sorted = sortAscending(group.asking);
    rows.push({
      key: `${city}|${name}`,
      city,
      locality: name,
      lat: place.lat,
      lon: place.lon,
      asking: sorted,
      p25: quantile(sorted, 0.25),
      median: quantile(sorted, 0.5),
      p75: quantile(sorted, 0.75),
      modelMedian: median(group.model),
    });
  }
  return rows;
}

export function MarketExplorer() {
  const table = useStaticData<ListingTable>("listings.json");
  const localities = useStaticData<LocalityStat[]>("localities.json");
  const metrics = useStaticData<Metrics>("metrics.json");
  const ready = table.data && localities.data && metrics.data ? { table: table.data, localities: localities.data, metrics: metrics.data } : null;

  return (
    <>
      <PageHeader
        title="Market explorer"
        description="Asking rates by micro-market from the cleaned listings, with the model's estimate alongside."
      />
      <DataState data={ready} error={table.error ?? localities.error ?? metrics.error}>
        {(data) => <Explorer table={data.table} localities={data.localities} metrics={data.metrics} />}
      </DataState>
    </>
  );
}

function Explorer({ table, localities, metrics }: { table: ListingTable; localities: LocalityStat[]; metrics: Metrics }) {
  const [params, setParams] = useSearchParams();
  const [bhk, setBhk] = useState("all");
  const [sale, setSale] = useState("all");
  const [minListings, setMinListings] = useState(3);
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean }>({ key: "listings", descending: true });
  const [limit, setLimit] = useState(MAX_ROWS);

  const city = params.get("city") ?? "all";
  const selectedKey = params.get("locality") && city !== "all" ? `${city}|${params.get("locality")}` : null;
  const coordinates = useMemo(() => new Map(localities.map((l) => [`${l.city}|${l.locality}`, l])), [localities]);
  const rows = useMemo(() => buildRows(table, coordinates, { city, bhk, sale }), [table, coordinates, city, bhk, sale]);
  const eligible = useMemo(() => rows.filter((r) => r.asking.length >= minListings), [rows, minListings]);

  const sorted = useMemo(() => {
    const value = (r: LocalityRow): number | string => {
      switch (sort.key) {
        case "locality": return r.locality;
        case "listings": return r.asking.length;
        case "median": return r.median;
        case "spread": return (r.p75 - r.p25) / r.median;
        case "model": return r.modelMedian;
        case "gap": return r.modelMedian / r.median - 1;
      }
    };
    const direction = sort.descending ? -1 : 1;
    return [...eligible].sort((a, b) => {
      const [x, y] = [value(a), value(b)];
      return (typeof x === "string" ? x.localeCompare(y as string) : (x as number) - (y as number)) * direction;
    });
  }, [eligible, sort]);

  const points = useMemo<MapPoint[]>(
    () => eligible.map((r) => ({ key: r.key, locality: r.locality, city: r.city, lat: r.lat, lon: r.lon, listings: r.asking.length, medianAsking: r.median })),
    [eligible],
  );
  const edges = useMemo(() => {
    const medians = sortAscending(eligible.map((r) => r.median));
    return [0.2, 0.4, 0.6, 0.8].map((q) => quantile(medians, q));
  }, [eligible]);

  const allAsking = useMemo(() => sortAscending(rows.flatMap((r) => r.asking)), [rows]);
  const selected = rows.find((r) => r.key === selectedKey) ?? null;
  const select = (key: string) => {
    const [selectedCity, name] = key.split("|");
    setParams({ city: selectedCity, locality: name });
  };
  const toggleSort = (key: SortKey) =>
    setSort((current) => ({ key, descending: current.key === key ? !current.descending : key !== "locality" }));

  return (
    <div className="space-y-6">
      <Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="City" htmlFor="filter-city">
            <select
              id="filter-city"
              className={CONTROL_CLASS}
              value={city}
              onChange={(event) => setParams(event.target.value === "all" ? {} : { city: event.target.value })}
            >
              <option value="all">All four cities</option>
              {table.cities.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </Field>
          <Field label="BHK" htmlFor="filter-bhk">
            <select id="filter-bhk" className={CONTROL_CLASS} value={bhk} onChange={(event) => setBhk(event.target.value)}>
              <option value="all">All sizes</option>
              <option value="1">1 BHK</option>
              <option value="2">2 BHK</option>
              <option value="3">3 BHK</option>
              <option value="4">4 BHK and above</option>
            </select>
          </Field>
          <Field label="Sale type" htmlFor="filter-sale">
            <select id="filter-sale" className={CONTROL_CLASS} value={sale} onChange={(event) => setSale(event.target.value)}>
              <option value="all">Resale and new</option>
              <option value="resale">Resale</option>
              <option value="new">New</option>
            </select>
          </Field>
          <Field label="Minimum listings per locality" htmlFor="filter-min">
            <select id="filter-min" className={CONTROL_CLASS} value={minListings} onChange={(event) => setMinListings(Number(event.target.value))}>
              {[1, 3, 5, 10].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <dl className="num mt-5 grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm sm:grid-cols-4">
          <Summary label="Listings in view" value={formatCount(allAsking.length)} />
          <Summary label="Localities in view" value={`${formatCount(eligible.length)} of ${formatCount(rows.length)}`} />
          <Summary label="Median asking rate" value={allAsking.length ? `${formatInr(quantile(allAsking, 0.5))}/sq.ft` : "None"} />
          <Summary label="Asking rate, 25th to 75th" value={allAsking.length ? `${formatInr(quantile(allAsking, 0.25))} to ${formatInr(quantile(allAsking, 0.75))}` : "None"} />
        </dl>
      </Card>

      <Card title="Micro-market map" subtitle="Each circle is a locality centroid. Select one to load it into the gap analyser.">
        {points.length ? (
          <LocalityMap points={points} edges={edges} selectedKey={selectedKey} onSelect={select} />
        ) : (
          <p className="py-10 text-center text-sm text-muted">No locality meets the current filters.</p>
        )}
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card title="Micro-market price grid" subtitle="Median listing asking rate per locality, with the model's median estimate for the same listings." flush>
          <Table label="Micro-market price grid">
            <thead>
              <tr>
                <SortHeader label="Locality" active={sort} column="locality" onSort={toggleSort} />
                <SortHeader label="Listings" numeric active={sort} column="listings" onSort={toggleSort} />
                <SortHeader label="Median asking" numeric active={sort} column="median" onSort={toggleSort} />
                <SortHeader label="Spread (IQR)" numeric active={sort} column="spread" onSort={toggleSort} />
                <SortHeader label="Model median" numeric active={sort} column="model" onSort={toggleSort} />
                <SortHeader label="Model vs asking" numeric active={sort} column="gap" onSort={toggleSort} />
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, limit).map((row) => (
                <tr
                  key={row.key}
                  onClick={() => select(row.key)}
                  className={`cursor-pointer hover:bg-canvas ${row.key === selectedKey ? "bg-hover" : ""}`}
                >
                  <Td>
                    <button
                      className="cursor-pointer text-left font-medium hover:underline"
                      onClick={(event) => {
                        event.stopPropagation();
                        select(row.key);
                      }}
                    >
                      {row.locality}
                    </button>
                    <span className="block text-xs text-muted">{row.city}</span>
                  </Td>
                  <Td numeric>{row.asking.length}</Td>
                  <Td numeric>{formatInr(row.median)}</Td>
                  <Td numeric className="text-muted">{formatPct(((row.p75 - row.p25) / row.median) * 100, 0)}</Td>
                  <Td numeric>{formatInr(row.modelMedian)}</Td>
                  <Td numeric>{formatSignedPct((row.modelMedian / row.median - 1) * 100)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          {sorted.length > limit && (
            <div className="border-t border-line p-3 text-center">
              <button className="cursor-pointer text-sm font-semibold text-ink hover:underline" onClick={() => setLimit((n) => n + MAX_ROWS)}>
                Show more ({sorted.length - limit} remaining)
              </button>
            </div>
          )}
          {sorted.length === 0 && <p className="p-6 text-center text-sm text-muted">No locality meets the current filters.</p>}
        </Card>

        <GapAnalyser selected={selected} key={selected?.key ?? "none"} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Model error by city" subtitle="M+ model on unseen neighbourhoods, error against asking price." flush>
          <Table label="Model error by city">
            <thead>
              <tr>
                <Th>City</Th>
                <Th numeric>Listings</Th>
                <Th numeric>MdAPE</Th>
                <Th numeric>Bias</Th>
                <Th numeric>80% coverage</Th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.per_city).map(([name, models]) => (
                <tr key={name}>
                  <Td>{name}</Td>
                  <Td numeric>{formatCount(models["M+"].n)}</Td>
                  <Td numeric>{formatPct(models["M+"].mdape)}</Td>
                  <Td numeric>{formatSignedPct(models["M+"].bias)}</Td>
                  <Td numeric>{formatPct(metrics.coverage_80.per_city[name].coverage)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <div className="space-y-3">
          <NotBuilt title="Price growth (CAGR)">Not in prototype data. The listings carry no dates, so no time series exists.</NotBuilt>
          <NotBuilt title="Rental yield">Not in prototype data. No rent data was ingested.</NotBuilt>
          <NotBuilt title="Infrastructure or growth index">
            Not in prototype data. The model uses OpenStreetMap distances and counts, not a composite index.
          </NotBuilt>
        </div>
      </div>

      <Notice>
        Rates are listing asking prices from a 2020 snapshot. All listings in a locality share one centroid, so the map
        shows localities, not addresses. Map tiles and data by OpenStreetMap contributors.
      </Notice>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-sans text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  );
}

interface SortHeaderProps {
  label: string;
  column: SortKey;
  active: { key: SortKey; descending: boolean };
  numeric?: boolean;
  onSort: (key: SortKey) => void;
}

function SortHeader({ label, column, active, numeric = false, onSort }: SortHeaderProps) {
  const on = active.key === column;
  const Arrow = active.descending ? ArrowDown : ArrowUp;
  return (
    <Th numeric={numeric}>
      <button
        onClick={() => onSort(column)}
        aria-label={`Sort by ${label}`}
        className={`inline-flex cursor-pointer items-center gap-1 ${on ? "text-ink" : ""} ${numeric ? "flex-row-reverse" : ""}`}
      >
        {label}
        {on && <Arrow aria-hidden className="size-3" />}
      </button>
    </Th>
  );
}

function GapAnalyser({ selected }: { selected: LocalityRow | null }) {
  const [quoted, setQuoted] = useState("");
  const rate = Number(quoted);

  return (
    <Card title="Gap analyser" subtitle="Compare a quoted asking rate with the locality's listings and the model.">
      {!selected ? (
        <p className="text-sm leading-relaxed text-muted">Select a locality from the map or the grid.</p>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold">{selected.locality}</p>
            <p className="text-xs text-muted">
              {selected.city}, <span className="num">{selected.asking.length}</span> listings after filters
            </p>
          </div>
          <Field label="Quoted asking rate (₹/sq.ft)" htmlFor="gap-rate">
            <NumberInput id="gap-rate" min={1} value={quoted} placeholder="e.g. 9500" onChange={(event) => setQuoted(event.target.value)} />
          </Field>
          {rate > 0 ? (
            <dl className="num space-y-2 rounded-md bg-canvas p-3 text-sm">
              <Row label="Locality median asking" value={formatInr(selected.median)} />
              <Row label="Quoted vs locality median" value={formatSignedPct((rate / selected.median - 1) * 100)} />
              <Row label="Percentile among listings" value={`${percentileRank(selected.asking, rate).toFixed(0)}th`} />
              <Row label="Model median estimate" value={formatInr(selected.modelMedian)} />
              <Row label="Quoted vs model median" value={formatSignedPct((rate / selected.modelMedian - 1) * 100)} />
            </dl>
          ) : (
            <p className="text-sm text-muted">Enter a rate to see where it sits.</p>
          )}
          {selected.asking.length < 5 && <Badge tone="warn">Thin sample, under 5 listings</Badge>}
          <p className="text-xs leading-relaxed text-muted">
            The percentile is among asking rates of this locality in the data, not transactions. Interquartile range{" "}
            <span className="num text-ink">{formatInr(selected.p25)} to {formatInr(selected.p75)}</span>.
          </p>
        </div>
      )}
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="font-sans text-muted">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
