from service import crm


def _row(**over):
    row = dict.fromkeys(crm.COLUMNS, "")
    row |= {"email": "a@b.test", "score": "72", "status": "hot", **over}
    return row


def test_csv_sink_writes_and_rereads_full_row_shape(tmp_path):
    sink = crm.CsvSink(tmp_path / "leads.csv")
    sink.append(_row(customer="Acme"))
    rows = sink.rows()
    assert len(rows) == 1
    assert set(rows[0].keys()) == set(crm.COLUMNS)
    assert rows[0]["customer"] == "Acme"


def test_sink_defaults_to_csv_without_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    monkeypatch.setenv("CRM_BACKEND", "auto")
    assert isinstance(crm.make_sink(), crm.CsvSink)


def test_explicit_sheets_backend_requires_sheet_id(monkeypatch):
    monkeypatch.setenv("CRM_BACKEND", "sheets")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet-123")
    monkeypatch.setattr(crm, "SheetsSink", lambda sheet_id: "sheets-stub")
    assert crm.make_sink() == "sheets-stub"
