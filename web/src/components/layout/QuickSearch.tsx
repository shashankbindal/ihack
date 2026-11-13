import { FileText, MapPin, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStaticData } from "../../hooks/useStaticData";
import type { FormLocality, QueueRow } from "../../lib/types";

interface Hit {
  key: string;
  label: string;
  detail: string;
  to: string;
  kind: "report" | "locality";
}

const MAX_HITS = 7;

export function QuickSearch() {
  const queue = useStaticData<QueueRow[]>("queue.json").data;
  const localities = useStaticData<FormLocality[]>("form_localities.json").data;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const hits = useMemo<Hit[]>(() => {
    const needle = query.trim().toLowerCase();
    if (needle.length < 2) return [];
    const reports = (queue ?? [])
      .filter((row) => `${row.listing_id} ${row.locality} ${row.city}`.toLowerCase().includes(needle))
      .map<Hit>((row) => ({
        key: row.listing_id,
        label: row.listing_id,
        detail: `${row.locality}, ${row.city}`,
        to: `/report/${row.listing_id}`,
        kind: "report",
      }));
    const places = (localities ?? [])
      .filter((place) => place.locality.toLowerCase().includes(needle))
      .map<Hit>((place) => ({
        key: `${place.city}-${place.locality}`,
        label: place.locality,
        detail: `${place.city}, ${place.n_listings} listings`,
        to: `/market-explorer?city=${encodeURIComponent(place.city)}&locality=${encodeURIComponent(place.locality)}`,
        kind: "locality",
      }));
    return [...reports, ...places].slice(0, MAX_HITS);
  }, [query, queue, localities]);

  const go = (hit: Hit) => {
    setOpen(false);
    setQuery("");
    navigate(hit.to);
  };

  return (
    <div
      className="relative w-full max-w-md"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <label className="relative block">
        <span className="sr-only">Search reports and localities</span>
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <input
          type="search"
          value={query}
          placeholder="Search report ID or locality"
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
            if (event.key === "Enter" && hits[0]) go(hits[0]);
          }}
          className="h-9 w-full rounded-md border border-line bg-canvas pl-9 pr-3 text-sm text-ink placeholder:text-muted focus:bg-surface"
        />
      </label>
      {open && query.trim().length >= 2 && (
        <ul className="absolute left-0 right-0 top-11 z-50 overflow-hidden rounded-md border border-line bg-surface">
          {hits.length === 0 && <li className="px-3 py-2.5 text-sm text-muted">No matching report or locality</li>}
          {hits.map((hit) => (
            <li key={hit.key}>
              <button
                onClick={() => go(hit)}
                className="flex w-full cursor-pointer items-center gap-3 px-3 py-2 text-left hover:bg-hover"
              >
                {hit.kind === "report" ? (
                  <FileText aria-hidden className="size-4 shrink-0 text-muted" />
                ) : (
                  <MapPin aria-hidden className="size-4 shrink-0 text-muted" />
                )}
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink">{hit.label}</span>
                  <span className="block truncate text-xs text-muted">{hit.detail}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
