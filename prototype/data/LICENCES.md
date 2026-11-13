# Data sources and licences

| Source | Used for | URL | Licence | Notes |
|---|---|---|---|---|
| Housing Prices in Metropolitan Areas of India (Kaggle, user ruchi798) | Listing asking prices, area, BHK, resale flag, amenity flags for Mumbai (MMR), Bangalore, Hyderabad | https://www.kaggle.com/datasets/ruchi798/housing-prices-in-metropolitan-areas-of-india | CC0: Public Domain (as stated on Kaggle) | Described by its author as scraped listings (2020 snapshot). Downloaded through Kaggle's public download endpoint without credentials. Ground truth is asking price, not transaction value. |
| OpenStreetMap, Geofabrik extracts `asia/india/western-zone` and `asia/india/southern-zone` | POIs and roads for distance and count features | https://download.geofabrik.de/asia/india.html | ODbL 1.0, (c) OpenStreetMap contributors | Extract dates recorded in `data/raw/osm/source.json`. |
| Nominatim (OpenStreetMap geocoder) | Locality name to centroid coordinates | https://nominatim.openstreetmap.org | Results are OSM data, ODbL 1.0 | Used under the Nominatim usage policy: at most 1 request/s, generic User-Agent, every result cached in `data/interim/geocode_cache.json`. |

## Considered and not used

| Source | Why not |
|---|---|
| PyPI `india-housing-datasets` | Its documentation states the data is synthetically generated, so it cannot support accuracy claims. |
| Kaggle "House Price Prediction Challenge" (MachineHack, user anmolkumar) | Tagged GPL-2 on Kaggle, provenance is "various property aggregators", and its coordinates are noisy (latitude/longitude columns swapped, many points outside the stated city). |
| 99acres, MagicBricks, Housing.com | Not scraped, per the build rules. Production access would be through licensed feeds. |
| Overpass API | Public instances returned 502/504 during the build; Geofabrik extracts were used instead. |
| Sentinel-2 imagery, RBI RPPI / NHB RESIDEX, RERA (Brickplot), circle rates | Not ingested in this prototype; see `not_run` in `results/metrics.json`. |
