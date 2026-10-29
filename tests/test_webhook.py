AUTH = {"authorization": "Bearer test-token"}


def test_healthz_is_public(client):
    body = client.get("/healthz").json()
    assert body["ok"] is True and body["documents"] == 2


def test_webhook_requires_token(client):
    assert client.post("/webhook/lead", json={"message": "pricing?"}).status_code == 401
    assert client.post("/webhook/lead", json={"message": "pricing?"},
                       headers={"authorization": "Bearer wrong"}).status_code == 401


def test_message_is_required(client):
    assert client.post("/webhook/lead", json={"message": "  "}, headers=AUTH).status_code == 422


def test_full_pipeline_writes_one_grounded_row(client):
    response = client.post("/webhook/lead", headers=AUTH, json={
        "customer": "Acme", "email": "jane@acme.test", "source": "website",
        "message": "What is the enterprise pricing and can we get a quote for bulk seats?",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["status"] == "hot" and data["row_written"] is True

    csv_body = client.get("/leads.csv", headers=AUTH).text
    assert "jane@acme.test" in csv_body and "Acme" in csv_body
    assert csv_body.count("\n") == 2  # header + one row


def test_digest_endpoint_reflects_ingested_leads(client):
    client.post("/webhook/lead", headers=AUTH, json={
        "email": "mad@x.test", "message": "my refund is broken and this is a total scam"})
    digest = client.get("/digest", headers=AUTH).text
    assert "Weekly Lead & Support Digest" in digest
    assert "**1** inbound" in digest and "mad@x.test" in digest


def test_triage_endpoint_does_not_write(client):
    response = client.post("/triage", headers=AUTH, json={"message": "how do refunds work"})
    assert response.status_code == 200 and "context_used" in response.json()
    assert client.get("/leads.csv", headers=AUTH).text.count("\n") == 1  # header only
