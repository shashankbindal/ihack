"""FastAPI service. Run: uvicorn src.api:app --port 8000"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.schemas import Valuation, ValuationRequest
from src.valuate import OutOfCoverage, Valuer

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["valuer"] = Valuer()
    yield
    state.clear()


app = FastAPI(title="Property valuation prototype", version="0.1", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ready": "valuer" in state}


@app.post("/valuate", response_model=Valuation)
def valuate(request: ValuationRequest) -> dict:
    try:
        return state["valuer"].valuate(request).contract
    except OutOfCoverage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
