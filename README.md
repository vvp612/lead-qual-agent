# lead-qual-agent

**An unattended lead & support intake pipeline.** An inbound message hits a webhook, an
LLM scores and classifies it **against the company's own knowledge base** (RAG), the
result lands in the CRM, a human is pinged only when it matters, and a weekly digest
summarises the week.

Runs two ways from the same brain — standalone (`POST /webhook/lead`), or orchestrated by
the included **n8n workflow** that calls the `/triage` and `/digest` steps and uses native
Slack/Sheets nodes. The LLM is a one-method interface with a **deterministic mock**, so the
whole thing is testable and demoable **with no API key**.

## Demo vertical — ShopDesk support triage

Six realistic inbound emails, triaged offline (`python demo/run_demo.py`):

```
hot  score=100 sales        🔺human  Jane Doe / Acme Retail
hot  score= 73 demo_request         Priya / Northwind
cold score= 27 support              Sam
warm score= 51 complaint    🔺human  Morgan / BigBox
spam score=  8 spam                  deals@spamzone.test
cold score= 25 support              Lee / City Cycles
```

…feeding a weekly digest ([committed sample](docs/digest-sample.md)) that counts the mix,
lists top leads, and quotes the **policy-grounded** reply drafts — e.g. “Great to hear
you're interested (per our **Plans & pricing**)!”

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn service.main:app            # offline (mock LLM, CSV CRM)
```

```bash
TOKEN=***
curl -X POST http://localhost:8000/webhook/lead \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"customer":"Acme","email":"jane@acme.test","message":"enterprise pricing quote for bulk seats and API integration"}'
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/digest
```

```bash
.venv/bin/python -m pytest -q     # 24 tests — offline (MockLLM)
.venv/bin/python demo/run_demo.py # scripted walkthrough → docs/digest-sample.md
```

Use Claude instead of the mock with `export ANTHROPIC_API_KEY=…`.

## How a message flows

```
              ┌── RAG: BM25 snippets from knowledge/*.md ──┐
webhook ──────┤                                            ├─▶ triage JSON ─┬─▶ CRM row (Sheets | CSV)
   (Bearer)   └────────────────────────────────────────────┘   score/intent  └─▶ needs_human → human
                                                                 reply_draft
```

| Module | Responsibility |
|---|---|
| `service/rag.py` | SQLite **FTS5** index over `knowledge/*.md`; query sanitising; prompt-ready context. |
| `service/triage.py` | strict JSON contract (`score`, `intent`, `needs_human`, `reply_draft`); validating parser clamps score, rejects bad intent, bands hot/warm/cold/spam. |
| `service/llm.py` | `complete()` interface; Claude + keyword-scored `MockLLM`; provider by env. |
| `service/crm.py` | sink abstraction — **Google Sheets** (gspread) or **CSV**, same row shape; `CRM_BACKEND=auto`. |
| `service/digest.py` | weekly markdown digest from the CRM rows. |
| `service/main.py` | FastAPI: bearer webhook, `/triage`, `/digest`, `/leads.csv`, `/healthz`. |

## Both run modes

**1 · Service runs the pipeline** — point your form/tool at `POST /webhook/lead`; the
service writes the CRM row itself.

**2 · n8n orchestrates** — import `n8n/shopdesk-triage-flow.json`:

```
Webhook → HTTP /triage → IF needs_human ─┬─▶ Slack escalation ─┐
                                          └─▶ Google Sheets ◀───┘
Schedule (Mon 08:00) → HTTP /digest → Slack
```

Set `LEAD_AGENT_URL` and `WEBHOOK_TOKEN` in n8n, connect Slack + Google Sheets
credentials, and activate. This keeps the logic in the service but lets ops edit routing,
channels and the CRM tab in the n8n UI.

## Re-targeting for another client

1. Drop the client's policy docs into `knowledge/` — the RAG picks them up automatically.
2. Edit the intents in `service/triage.py` (`INTENTS`) and the escalation rules.
3. Point `CRM_BACKEND=sheets` at their Google Sheet (set `GOOGLE_SHEET_ID` +
   `GOOGLE_CREDENTIALS`); no code change.

Deliberately **not** bundled (client-specific): two-way CRM sync, SLA timers, embeddings
retrieval for large/multilingual corpora, multi-tenant isolation — see `PLAN.md`.

## Config (env)

| Var | Default | Meaning |
|---|---|---|
| `WEBHOOK_TOKEN` | `dev-token` | bearer token guarding all non-healthz routes |
| `TRIAGE_LLM` | `mock` (auto `anthropic` with key) | `mock` \| `anthropic` |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | — | live Claude model |
| `CRM_BACKEND` | `auto` | `auto` \| `csv` \| `sheets` |
| `LEADS_CSV` | `data/leads.csv` | CSV sink path |
| `GOOGLE_SHEET_ID` / `GOOGLE_CREDENTIALS` | — | Sheets sink |
| `KNOWLEDGE_DIR` | `knowledge/` | Markdown knowledge base |

_Licence: MIT._
