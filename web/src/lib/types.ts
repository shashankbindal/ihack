export type Routing = "AUTO_ACCEPT" | "DESKTOP_REVIEW" | "PHYSICAL_VALUATION";
export type Grade = "A" | "B" | "C" | "D";

export interface ValuationRequest {
  lat: number;
  lon: number;
  type: "apartment";
  area_sqft: number;
  bhk: number;
  floor: number | null;
  age: number | null;
  resale: boolean;
  amenities: Record<string, boolean>;
  loan_amount_inr: number | null;
}

export interface Factor {
  feature: string;
  effect_inr_per_sqft: number;
  effect_pct: number;
  direction: "+" | "-";
  plain_text: string;
}

export interface Comparable {
  id: string;
  locality: string;
  lat: number;
  lon: number;
  distance_m: number;
  similarity: number;
  area_sqft: number;
  bhk: number;
  listed_price_per_sqft: number;
  adj_price_per_sqft: number;
}

export interface Valuation {
  valuation_id: string;
  request: ValuationRequest;
  model_version: string;
  city: string;
  value: { point_inr: number; per_sqft_inr: number; low_inr: number; high_inr: number; interval_level: number };
  confidence: {
    grade: Grade;
    score: number;
    interval_width_pct: number;
    n_comparables: number;
    data_freshness_days: number;
  };
  top_factors: Factor[];
  comparables: Comparable[];
  routing: Routing;
  routing_reasons: string[];
  lending: {
    max_eligible_loan_inr: number;
    max_eligible_loan_on_low_inr: number;
    ltv_cap_for_requested_loan: number | null;
    policy_note: string;
  };
  inputs_not_used: string[];
  data_lineage: { source: string; licence: string; fetched_at: string }[];
  disclaimer: string;
}

export interface ReportRecord {
  id: string;
  city: string;
  locality: string;
  quotedPriceInr: number | null;
  source: "precomputed" | "live";
  valuation: Valuation;
}

export interface QueueRow {
  listing_id: string;
  city: string;
  locality: string;
  bhk: number;
  area_sqft: number;
  resale: boolean;
  asking_price_inr: number;
  asking_ppsf: number;
  estimate_inr: number;
  estimate_ppsf: number;
  variance_pct: number;
  grade: Grade;
  routing: Routing;
}

export interface CityStat {
  city: string;
  n_listings: number;
  n_localities: number;
  median_asking_ppsf: number;
  median_model_ppsf: number;
  asking_p25_ppsf: number;
  asking_p75_ppsf: number;
}

export interface LocalityStat {
  city: string;
  locality: string;
  lat: number;
  lon: number;
  n_listings: number;
  asking_p10: number;
  asking_p25: number;
  asking_p50: number;
  asking_p75: number;
  asking_p90: number;
  median_model_ppsf: number;
}

export interface FormLocality {
  city: string;
  locality: string;
  lat: number;
  lon: number;
  n_listings: number;
}

export interface ListingTable {
  cities: string[];
  localities: { city: string; name: string }[];
  city: number[];
  locality: number[];
  bhk: number[];
  resale: number[];
  area_sqft: number[];
  asking_ppsf: number[];
  model_ppsf: number[];
}

export interface PrecomputedValuation {
  listing_id: string;
  locality: string;
  city: string;
  asking_price_inr: number;
  valuation: Valuation;
}

export interface ModelMetrics {
  n: number;
  mdape: number;
  mape: number;
  ppe10: number;
  ppe20: number;
  rmse_log: number;
  bias: number;
  overval20: number;
  cod: number;
  prd: number;
}

export type ModelName = "B0" | "B1" | "B2" | "B3" | "M+";
export type ModelTable = Record<ModelName, ModelMetrics>;

export interface Significance {
  delta_mdape: number;
  relative_reduction_pct: number;
  ci95: [number, number];
  ci_excludes_zero: boolean;
  n_clusters: number;
  n_boot: number;
  method: string;
}

export interface CoverageCell {
  coverage: number;
  median_width_pct: number;
  n: number;
}

export interface CoverageBlock {
  overall: CoverageCell;
  per_city: Record<string, CoverageCell>;
  per_price_band: Record<string, CoverageCell>;
}

export interface GradeBlock {
  by_grade: Record<Grade, { share: number; n: number; mdape?: number; ppe10?: number; overval20?: number }>;
  routing_share: Record<Routing, number>;
  thresholds_half_width: Record<string, number>;
}

export interface Protocol {
  models: ModelTable;
  per_city: Record<string, ModelTable>;
  per_price_band: Record<string, ModelTable>;
  significance: Record<string, Significance>;
}

export interface Metrics extends Protocol {
  n_test: number;
  dataset: string;
  ground_truth: string;
  model_descriptions: Record<ModelName, string>;
  price_band_edges_inr: number[];
  seen_locality: Protocol & { note: string; share_test_localities_seen_in_training: number };
  coverage_80: CoverageBlock & { method: string; seen_locality: CoverageBlock };
  grades: GradeBlock;
  grades_seen_locality: GradeBlock;
  latency: { n_requests: number; p50_ms: number; p95_ms: number; hardware: string; method: string };
  data: {
    row_counts_by_step: Record<string, Record<string, number>>;
    amenity_missing_evidence: Record<
      string,
      { share_all_missing: number; log_ppsf_spread_complete: number; log_ppsf_spread_all_missing: number }
    >;
  };
  not_run: Record<string, string>;
  interval_width_median: number;
  worst_subgroup: { dimension: string; group: string; mdape: number; n: number };
}
