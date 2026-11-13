"""Measure end-to-end /valuate latency against a local uvicorn server."""

import os
import platform
import subprocess
import sys
import time

import httpx
import numpy as np
import pandas as pd

from src import config
from src.features import FEATURES_PATH
from src.metrics import update_metrics

PORT = 8765
N_REQUESTS = 200
WARMUP = 5


def sample_requests(n: int) -> list[dict]:
    rows = pd.read_parquet(FEATURES_PATH).sample(n + WARMUP, random_state=config.SEED)
    rng = np.random.default_rng(config.SEED)
    jitter = rng.normal(0, 0.003, size=(len(rows), 2))
    return [
        {"lat": r.lat + dy, "lon": r.lon + dx, "area_sqft": float(r.area_sqft), "bhk": int(r.bhk),
         "resale": bool(r.resale)}
        for r, (dy, dx) in zip(rows.itertuples(), jitter)
    ]


def wait_until_ready(client: httpx.Client, timeout_s: float = 120) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if client.get("/health").json().get("ready"):
                return
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    raise TimeoutError("API did not become ready")


def cpu_name() -> str:
    if sys.platform == "win32":
        import winreg

        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return platform.processor() or platform.machine()


def hardware() -> str:
    return (f"{cpu_name()} ({os.cpu_count()} logical cores); {platform.system()} {platform.release()}; "
            f"Python {platform.python_version()}; single uvicorn worker")


def main() -> dict:
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api:app", "--port", str(PORT), "--log-level", "warning"],
        cwd=config.ROOT,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{PORT}", timeout=30) as client:
            wait_until_ready(client)
            payloads = sample_requests(N_REQUESTS)
            latencies, statuses = [], []
            for i, payload in enumerate(payloads):
                start = time.perf_counter()
                response = client.post("/valuate", json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000
                if i >= WARMUP:
                    latencies.append(elapsed_ms)
                    statuses.append(response.status_code)
    finally:
        server.terminate()
        server.wait()
    latencies = np.array(latencies)
    result = {
        "n_requests": len(latencies),
        "warmup_requests_excluded": WARMUP,
        "status_counts": pd.Series(statuses).value_counts().to_dict(),
        "p50_ms": float(np.percentile(latencies, 50)),
        "p95_ms": float(np.percentile(latencies, 95)),
        "max_ms": float(latencies.max()),
        "hardware": hardware(),
        "method": "sequential HTTP requests to localhost, client-side wall time, includes SHAP and comparables",
    }
    update_metrics(latency=result)
    return result


if __name__ == "__main__":
    main()
