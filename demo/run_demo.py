"""Scripted walkthrough of the whole pipeline, mock LLM, no network.

    python demo/run_demo.py

Boots the service in-process, posts six realistic ShopDesk inbound emails,
prints each triage verdict, then fetches the weekly digest and writes it to
`docs/digest-sample.md` (the committed sample the README shows).
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os

os.environ.setdefault("TRIAGE_LLM", "mock")
os.environ.setdefault("WEBHOOK_TOKEN", "demo-token")
os.environ["CRM_BACKEND"] = "csv"
os.environ["LEADS_CSV"] = str(ROOT / "data" / "demo-leads.csv")
pathlib.Path(os.environ["LEADS_CSV"]).unlink(missing_ok=True)  # fresh demo every run

from fastapi.testclient import TestClient  # noqa: E402
from service import main  # noqa: E402

main._sink = None
main._knowledge = None
client = TestClient(main.app)
AUTH = {"authorization": "Bearer demo-token"}

LEADS = [
    {"customer": "Jane Doe / Acme Retail", "email": "jane@acme.test", "source": "website",
     "message": "What is your enterprise pricing? We need a quote for bulk seats and an API integration."},
    {"customer": "Priya / Northwind", "email": "priya@northwind.test", "source": "email",
     "message": "Can we book a demo to see the inventory API before we partner with you?"},
    {"customer": "Sam", "email": "sam@smallshop.test", "source": "website",
     "message": "How do I export my orders to CSV and what are the delivery times?"},
    {"customer": "Morgan / BigBox", "email": "morgan@bigbox.test", "source": "email",
     "message": "My refund is still broken after two weeks, this service is terrible and I want a lawyer."},
    {"customer": "", "email": "deals@spamzone.test", "source": "website",
     "message": "buy followers cheap now"},
    {"customer": "Lee / City Cycles", "email": "lee@citycycles.test", "source": "webform",
     "message": "Where is my package? Tracking email never arrived after shipping."},
]

print(f"{main.knowledge().count} knowledge docs indexed\n")
for lead in LEADS:
    result = client.post("/webhook/lead", json=lead, headers=AUTH).json()["result"]
    flag = " 🔺human" if result["needs_human"] else ""
    print(f"{result['status']:<4} score={result['score']:>3} {result['intent']:<12}{flag}  {lead['customer'] or lead['email']}")

digest = client.get("/digest", headers=AUTH).text
out = ROOT / "docs" / "digest-sample.md"
out.parent.mkdir(exist_ok=True)
out.write_text(digest + "\n")
print(f"\n{'-' * 60}\n{digest}\n\ndigest sample written to {out.relative_to(ROOT)}")
