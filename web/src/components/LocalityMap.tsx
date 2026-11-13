import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { formatInr } from "../lib/format";

export interface MapPoint {
  key: string;
  locality: string;
  city: string;
  lat: number;
  lon: number;
  listings: number;
  medianAsking: number;
}

const BANDS = ["#cbd5e1", "#94a3b8", "#64748b", "#334155", "#0f172a"];

const bandColour = (value: number, edges: number[]): string => {
  const index = edges.findIndex((edge) => value <= edge);
  return BANDS[index === -1 ? BANDS.length - 1 : index];
};

function FitToPoints({ points }: { points: MapPoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    map.fitBounds(
      points.map((p) => [p.lat, p.lon] as [number, number]),
      { padding: [24, 24], maxZoom: 12 },
    );
  }, [map, points]);
  return null;
}

interface LocalityMapProps {
  points: MapPoint[];
  edges: number[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}

export function LocalityMap({ points, edges, selectedKey, onSelect }: LocalityMapProps) {
  return (
    <div>
      <MapContainer center={[16, 77]} zoom={5} scrollWheelZoom={false} className="h-[420px] w-full rounded-md border border-line">
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ODbL'
          maxZoom={18}
        />
        <FitToPoints points={points} />
        {points.map((point) => {
          const selected = point.key === selectedKey;
          return (
            <CircleMarker
              key={point.key}
              center={[point.lat, point.lon]}
              radius={Math.min(5 + Math.sqrt(point.listings) * 1.4, 16)}
              pathOptions={{
                color: selected ? "#e41e26" : "#ffffff",
                weight: selected ? 3 : 1,
                fillColor: bandColour(point.medianAsking, edges),
                fillOpacity: 0.85,
              }}
              eventHandlers={{ click: () => onSelect(point.key) }}
            >
              <Tooltip>
                <strong>{point.locality}</strong>, {point.city}
                <br />
                {formatInr(point.medianAsking)}/sq.ft median asking, {point.listings} listings
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span>Median asking rate, by quintile of the localities shown:</span>
        <span className="flex items-center gap-1">
          {BANDS.map((colour) => (
            <span key={colour} className="size-3 rounded-full border border-white" style={{ background: colour }} />
          ))}
          <span className="ml-1">lower to higher</span>
        </span>
        <span>Circle size: listing count</span>
      </div>
    </div>
  );
}
