"""FastAPI service for the intake pipeline.

Whole pipeline:  POST /webhook/lead   (auth → RAG → triage → CRM row → JSON reply)
Individual step: POST /triage          (auth → RAG + triage only, for n8n orchestration)
Reporting:       GET  /digest, GET /leads.csv
Liveness:        GET  /healthz          (no auth, for uptime probes)

Bearer token (env `WEBHOOK_TOKEN`) guards every non-healthz route.
"""
from __future__ import annotations

import hmac
import os
import pathlib

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, field_validator

from . import crm, digest, triage
from .llm import get_llm
from .rag import Knowledge

app = FastAPI(title="lead-qual-agent", version="1.0")

_KNOWLEDGE_DIR = os.environ.get("KNOWLEDGE_DIR", str(pathlib.Path(__file__).parent.parent / "knowledge"))
_knowledge: Knowledge | None = None
_sink: crm.Sink | None = None


def knowledge() -> Knowledge:
    global _knowledge
    if _knowledge is None:
        _knowledge = Knowledge(_KNOWLEDGE_DIR)
    return _knowledge


def sink() -> crm.Sink:
    global _sink
    if _sink is None:
        _sink = crm.make_sink()
    return _sink


class Lead(BaseModel):
    customer: str = ""
    email: str = ""
    message: str
    source: str = ""

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message is required")
        return v

    @field_validator("email")
    @classmethod
    def _shape(cls, v: str) -> str:
        if v and ("@" not in v or "." not in v.split("@")[-1]):
            raise ValueError("email is malformed")
        return v


def require_token(authorization: str = Header(default="")) -> None:
    expected = os.environ.get("WEBHOOK_TOKEN", "dev-token")
    provided = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid token")


@app.get("/healthz")
def healthz():
    return {"ok": True, "documents": knowledge().count}


@app.post("/triage", dependencies=[Depends(require_token)])
def triage_only(lead: Lead):
    context = knowledge().context_block(lead.message)
    result = triage.triage(get_llm(), lead.message, context)
    return result | {"context_used": bool(context)}


@app.post("/webhook/lead", dependencies=[Depends(require_token)])
def webhook_lead(lead: Lead):
    context = knowledge().context_block(lead.message)
    result = triage.triage(get_llm(), lead.message, context)
    row = {
        "received_at": _now(), "customer": lead.customer, "email": lead.email,
        "message": lead.message, "source": lead.source, **result,
    }
    sink().append({k: row.get(k, "") for k in crm.COLUMNS})
    return {"result": result, "grounded": bool(context), "row_written": True}


@app.get("/digest", dependencies=[Depends(require_token)], response_class=PlainTextResponse)
def get_digest():
    return digest.weekly_digest(sink().rows())


@app.get("/leads.csv", dependencies=[Depends(require_token)])
def leads_csv():
    target = sink()
    if not isinstance(target, crm.CsvSink):
        raise HTTPException(status_code=400, detail="CRM backend is not a local CSV")
    return FileResponse(target.path, media_type="text/csv", filename="leads.csv")


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
