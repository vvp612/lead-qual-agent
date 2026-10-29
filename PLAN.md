# PLAN — lead-qual-agent

Engineering plan behind the project: what is being built, in which order, and how each
part is verified.

## 1. Goals
- A **lead/support intake pipeline** that an operations team can run unattended:
  a webhook receives an inbound message, an LLM qualifies it against the company's own
  knowledge base (RAG), the result lands in the CRM (Google Sheets, local CSV fallback),
  a human is pinged only when needed, and a **weekly digest** summarizes the week.
- **Two run modes, one brain**: the FastAPI service can run the whole pipeline itself
  (`POST /webhook/lead`), or expose the steps (`/triage`, `/digest`) so an n8n workflow
  orchestrates with native Slack/Sheets nodes — `n8n/lead-qual-flow.json` ships the flow.
- The LLM is a one-method interface with a **deterministic mock** — everything is
  testable and demoable without an API key.

## 2. Scope
| Layer | Module | What ships |
|---|---|---|
| LLM | `service/llm.py` | `complete()` interface; `AnthropicLLM` (Claude) and keyword-scored `MockLLM`; provider chosen by env, mock when no key. |
| RAG | `service/rag.py` | SQLite **FTS5** index over `knowledge/*.md` (BM25-ranked snippets); query sanitising; the snippets are injected into the triage prompt so replies are grounded in real policy docs. |
| Triage | `service/triage.py` | strict JSON contract: `score` (0–100), `intent`, `needs_human`, `reply_draft`; validating parser, status banding (hot/warm/cold/spam). |
| CRM | `service/crm.py` | sink abstraction: **Google Sheets** (gspread, service account) or **local CSV** with identical row shape; `CRM_BACKEND=auto` picks sheets when configured, else CSV. |
| Digest | `service/digest.py` | weekly markdown digest from CRM rows: volumes, status mix, human-escalation breakdown, top leads. |
| API | `service/main.py` | FastAPI: bearer-token webhook, `/triage`, `/digest`, `/leads.csv`, `/healthz`. |
| n8n | `n8n/lead-qual-flow.json` | importable workflow: webhook → triage → IF → Slack escalation + Sheets append; scheduled digest branch. |

The demo vertical is **ShopDesk support triage** (fictional e-commerce): inbound emails
are scored for value, classified (demo_request / billing / complaint / question / spam),
answered with a policy-grounded draft, and escalated when human-touch is needed.
The pipeline is vertical-agnostic — the knowledge folder, prompts and intent set are
what a client would swap for their own domain.

## 3. Milestones
- **M1 — RAG**: FTS5 index + ranked snippets. *Done when:* tests retrieve the refund
  policy for a refund question and rank it above unrelated docs.
- **M2 — triage**: contract, validation, mock scoring. *Done when:* tests cover spam,
  complaint escalation and clamping of out-of-range scores.
- **M3 — CRM + digest**: CSV/Sheets sinks, weekly digest. *Done when:* row shape is
  asserted; digest counts match seeded rows.
- **M4 — API + n8n**: webhook auth, endpoints, importable flow JSON. *Done when:* an
  end-to-end TestClient run produces a triaged CRM row; flow JSON parses.
- **M5 — demo + docs**: scripted demo, sample digest, README.

## 4. Test strategy (pytest + TestClient, offline)
- `MockLLM` everywhere — deterministic, no network.
- RAG: seeding a temp knowledge dir, ranking, query sanitising (`" OR "` must not
  break FTS5).
- Triage: malformed JSON / bad intent rejected; score clamped; needs_human rules.
- CRM: CSV sink row shape and re-read; sink selection respects `CRM_BACKEND`.
- Webhook: auth 401/OK, full pipeline writes one well-shaped CRM row, digest reflects it.

## 5. Demo & docs
- `python demo/run_demo.py`: boots the service in-process, posts six realistic leads
  (two hot, one complaint, one billing, one spam, one question) and prints the produced
  weekly digest — output committed at `docs/digest-sample.md`.
- README shows both run modes with the n8n import walkthrough.

## 6. Roadmap (client-specific work, intentionally not bundled)
- Two-way CRM sync (HubSpot/Pipedrive), SLA timers, re-engagement follow-ups.
- Embeddings-based retrieval to replace keyword FTS5 once the corpus is large or
  multilingual; hybrid ranking.
- Per-tenant knowledge bases and intent schemas behind one deployment.

## 7. Definition of Done
`pytest` green; scripted demo reproduces the committed digest sample; n8n flow JSON
imports; clean commit history.
