import pytest


@pytest.fixture
def knowledge_dir(tmp_path):
    """A tiny knowledge base mirroring the real one, for isolated retrieval tests."""
    docs = tmp_path / "knowledge"
    docs.mkdir()
    (docs / "refunds.md").write_text(
        "# Refund policy\nRefunds are processed within 5 business days to the original payment method.\n"
    )
    (docs / "shipping.md").write_text(
        "# Shipping\nStandard delivery is three to five business days; express is next day.\n"
    )
    return docs


@pytest.fixture
def client(tmp_path, knowledge_dir, monkeypatch):
    """TestClient wired to a temp CSV sink and the tiny knowledge base, with the
    service's module-level caches cleared so tests don't leak into each other."""
    monkeypatch.setenv("WEBHOOK_TOKEN", "test-token")
    monkeypatch.setenv("CRM_BACKEND", "csv")
    monkeypatch.setenv("LEADS_CSV", str(tmp_path / "leads.csv"))
    monkeypatch.setenv("KNOWLEDGE_DIR", str(knowledge_dir))
    monkeypatch.setenv("TRIAGE_LLM", "mock")

    from service import main

    main._sink = None
    main._knowledge = None
    monkeypatch.setattr(main, "_KNOWLEDGE_DIR", str(knowledge_dir))
    from fastapi.testclient import TestClient

    yield TestClient(main.app)
    main._sink = None
    main._knowledge = None
