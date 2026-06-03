from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .pipeline import build_default_pipeline, load_json, CONFIG_PATH


class ScoreRequest(BaseModel):
    transaction_id: str
    transaction_timestamp: str
    sender_id: str
    receiver_id: str
    amount: float = Field(ge=0)
    transaction_location: str
    transaction_type: str
    currency: str | None = None
    channel: str | None = None
    raw_attributes: dict[str, Any] | None = None


class FeedbackRequest(BaseModel):
    transaction_id: str
    analyst_override: str
    confirmed_label: int | None = None
    reviewed_timestamp: str


app = FastAPI(title="Fraud Detection API", version="1.0.0")
pipeline = build_default_pipeline()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def config() -> dict[str, Any]:
    return load_json(CONFIG_PATH)


@app.post("/score")
def score(request: ScoreRequest) -> dict[str, Any]:
    try:
        return pipeline.score_transaction(request.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/feedback")
def feedback(request: FeedbackRequest) -> dict[str, str]:
    pipeline.record_feedback(**request.model_dump())
    return {"status": "recorded"}
