"""Download the open listing dataset (Kaggle, CC0) into data/raw/listings."""

import io
import json
import logging
import zipfile
from datetime import datetime, timezone

import requests

from src import config

LISTINGS_DIR = config.RAW / "listings"
SOURCE_FILE = LISTINGS_DIR / "source.json"

log = logging.getLogger(__name__)


def fetch_metadata() -> dict:
    response = requests.get(config.LISTINGS_META_URL, timeout=60)
    response.raise_for_status()
    meta = response.json()
    return {
        "dataset": config.LISTINGS_DATASET,
        "url": f"https://www.kaggle.com/datasets/{config.LISTINGS_DATASET}",
        "licence": meta.get("licenseName"),
        "last_updated": meta.get("lastUpdated"),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def download(force: bool = False) -> None:
    wanted = [f"{city}.csv" for city in config.CITIES]
    if not force and SOURCE_FILE.exists() and all((LISTINGS_DIR / f).exists() for f in wanted):
        log.info("listings already present")
        return
    LISTINGS_DIR.mkdir(parents=True, exist_ok=True)
    response = requests.get(config.LISTINGS_URL, timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for name in wanted:
            (LISTINGS_DIR / name).write_bytes(archive.read(name))
    SOURCE_FILE.write_text(json.dumps(fetch_metadata(), indent=2))
    log.info("downloaded %s", ", ".join(wanted))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    download()
