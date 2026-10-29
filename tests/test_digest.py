from service.digest import weekly_digest


def _rows():
    return [
        {"email": "hot@x.test", "customer": "Big Co", "score": "92", "status": "hot", "intent": "sales", "needs_human": "False", "reply_draft": ""},
        {"email": "mad@x.test", "customer": "Angry Corp", "score": "66", "status": "warm", "intent": "complaint", "needs_human": "True", "reply_draft": "Sorry — a teammate will fix this today."},
        {"email": "meh@x.test", "customer": "Small", "score": "18", "status": "cold", "intent": "support", "needs_human": "False", "reply_draft": ""},
    ]


def test_digest_totals_and_status_mix():
    text = weekly_digest(_rows())
    assert "**3** inbound" in text
    assert "hot" in text and "warm" in text and "cold" in text


def test_digest_lists_top_lead_and_escalation():
    text = weekly_digest(_rows())
    assert "Big Co" in text                       # top leads section
    assert "**1** flagged for a human" in text
    assert "Angry Corp" in text and "draft reply" in text


def test_empty_week():
    text = weekly_digest([])
    assert "**0** inbound" in text
    assert "Top leads" not in text and "Needs a human" not in text
