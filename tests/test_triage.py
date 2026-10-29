import pytest
from service.llm import MockLLM
from service.triage import TriageError, band, parse, triage


def test_pricing_question_scores_hot_and_cites_source():
    result = triage(MockLLM(), "What is your enterprise pricing and can we get a quote?",
                    context='- Source: "Plans & pricing" — three plans, enterprise has SSO')
    assert result["status"] == "hot"
    assert result["intent"] == "sales"
    assert "Plans & pricing" in result["reply_draft"]


def test_angry_refund_becomes_escalated_complaint():
    result = triage(MockLLM(), "This refund has been broken for a week, totally terrible scam service")
    assert result["intent"] == "complaint"
    assert result["needs_human"] is True


def test_short_junk_is_spam():
    assert triage(MockLLM(), "buy clik")["intent"] == "spam"


def test_empty_message_rejected():
    with pytest.raises(TriageError):
        triage(MockLLM(), "   ")


def test_bands():
    assert (band(95), band(50), band(25), band(5)) == ("hot", "warm", "cold", "spam")


def test_parse_clamps_score_and_rejects_bad_intent():
    assert parse('{"score": 140, "intent": "sales"}')["score"] == 100
    assert parse('{"score": -5, "intent": "other"}')["score"] == 0
    with pytest.raises(TriageError):
        parse('{"score": 10, "intent": "bitcoin"}')


def test_parse_rejects_non_json_and_forces_human_on_complaint():
    with pytest.raises(TriageError):
        parse("I think this lead looks promising")
    assert parse('{"score": 40, "intent": "complaint", "needs_human": false}')["needs_human"] is True
