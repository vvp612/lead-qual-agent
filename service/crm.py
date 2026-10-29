"""CRM sink abstraction: Google Sheets when configured, otherwise a local CSV file.

Both sinks share one row shape, so the API and digest are backend-agnostic.
`CRM_BACKEND=auto` picks Sheets when credentials + sheet id are present, else CSV —
so the service runs with zero cloud setup and upgrades to Sheets with two env vars.
"""
from __future__ import annotations

import csv
import os
import pathlib

COLUMNS = [
    "received_at", "customer", "email", "message",
    "score", "intent", "status", "needs_human", "reply_draft", "source",
]


class Sink:
    def append(self, row: dict) -> None: ...
    def rows(self) -> list[dict]: ...


class CsvSink:
    def __init__(self, path: str):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(COLUMNS)

    def append(self, row: dict) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=COLUMNS).writerow(row)

    def rows(self) -> list[dict]:
        with self.path.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))


class SheetsSink:
    """Backed by a shared Google Sheet (service-account auth via gspread)."""

    def __init__(self, sheet_id: str, tab: str = "leads"):
        import gspread  # lazy: only needed when actually using Sheets

        creds_path = os.environ.get("GOOGLE_CREDENTIALS", "")
        client = gspread.service_account(filename=creds_path or None)
        self.worksheet = client.open_by_key(sheet_id).worksheet(tab)

    def append(self, row: dict) -> None:
        self.worksheet.append_row([row.get(c, "") for c in COLUMNS], value_input_option="USER_ENTERED")

    def rows(self) -> list[dict]:
        return self.worksheet.get_all_records()


def sheets_configured() -> bool:
    return bool(os.environ.get("GOOGLE_SHEET_ID") and (os.environ.get("GOOGLE_CREDENTIALS") or os.path.exists(pathlib.Path.home() / ".config/gspread/service_account.json")))


def make_sink() -> Sink:
    backend = os.environ.get("CRM_BACKEND", "auto").lower()
    if backend == "sheets" or (backend == "auto" and sheets_configured()):
        return SheetsSink(os.environ["GOOGLE_SHEET_ID"])
    return CsvSink(os.environ.get("LEADS_CSV", "data/leads.csv"))
