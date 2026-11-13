"""FastAPI service. Run: uvicorn src.api:app --port 8000"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.schemas import Valuation, ValuationRequest
from src.valuate import OutOfCoverage, Valuer

DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["valuer"] = Valuer()
    yield
    state.clear()


app = FastAPI(title="Property valuation prototype", version="0.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ready": "valuer" in state}


@app.post("/valuate", response_model=Valuation)
def valuate(request: ValuationRequest) -> dict:
    try:
        return state["valuer"].valuate(request).contract
    except OutOfCoverage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
