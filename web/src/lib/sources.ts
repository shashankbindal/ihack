// Mirrors prototype/data/LICENCES.md.
export const DATA_SOURCES = [
  {
    name: "Housing Prices in Metropolitan Areas of India (Kaggle, ruchi798)",
    url: "https://www.kaggle.com/datasets/ruchi798/housing-prices-in-metropolitan-areas-of-india",
    usedFor: "Listing asking prices, area, BHK, resale flag and amenity flags",
    licence: "CC0: Public Domain (as stated on Kaggle)",
    note: "Scraped listings, 2020 snapshot. Ground truth is asking price, not transaction value.",
  },
  {
    name: "OpenStreetMap, Geofabrik India zone extracts",
    url: "https://download.geofabrik.de/asia/india.html",
    usedFor: "Points of interest and roads for distance and count features",
    licence: "ODbL 1.0, © OpenStreetMap contributors",
    note: "Western and southern zone extracts, dates recorded at download.",
  },
  {
    name: "Nominatim geocoding",
    url: "https://nominatim.openstreetmap.org",
    usedFor: "Locality name to centroid coordinates",
    licence: "ODbL 1.0 (OSM data)",
    note: "At most 1 request per second, every result cached.",
  },
] as const;

export const NOT_USED_SOURCES = [
  { name: "Sentinel-2 imagery", reason: "Not ingested, so the imagery model and its ablation were not run." },
  { name: "RBI RPPI and NHB RESIDEX price indices", reason: "Not ingested. The listings have no dates to deflate." },
  { name: "RERA registrations and state circle rates", reason: "Not integrated." },
  { name: "99acres, MagicBricks, Housing.com", reason: "Not scraped. Production access would be through licensed feeds." },
  { name: "PyPI india-housing-datasets", reason: "Its documentation states the data is synthetic." },
] as const;
