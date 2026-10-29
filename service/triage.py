"""Triage: score + classify an inbound message, grounded in the knowledge base.

One strict JSON contract. The parser is the trust boundary: it rejects non-JSON and
unknown intents, clamps the score, and derives the hot/warm/cold/spam band so the
CRM row is always internally consistent no matter what the model returns.
"""
from __future__ import annotations

import json
import re

INTENTS = {"sales", "demo_request", "support", "complaint", "other", "spam"}
CONTRACT = (
    "Return ONLY JSON: "
    '{"score": integer 0-100 (lead value), "intent": one of '
    '"sales|demo_request|support|complaint|other|spam", '
    '"needs_human": boolean, "reply_draft": string (1-2 sentences, cite the source doc)}'
)


class TriageError(ValueError):
    pass


def build_prompt(message: str, context: str) -> str:
    grounding = f"Relevant knowledge:\n{context}\n\n" if context else ""
    return f"{grounding}Message: {message}\n\n{CONTRACT}"


def system_prompt() -> str:
    return (
        "You triage inbound lead/support emails for an e-commerce operations team. "
        "Ground any factual claim in the provided sources; if none apply, say nothing invented. " + CONTRACT
    )


def band(score: int) -> str:
    return "hot" if score >= 70 else "warm" if score >= 40 else "cold" if score > 10 else "spam"


def triage(llm, message: str, context: str = "") -> dict:
    message = message.strip()
    if not message:
        raise TriageError("empty message")
    raw = llm.complete(system_prompt(), build_prompt(message, context))
    return parse(raw)


def parse(raw: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TriageError(f"model did not return JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TriageError("triage output must be a JSON object")

    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError) as exc:
        raise TriageError("score must be an integer") from exc
    score = max(0, min(100, score))  # clamp — models occasionally overshoot

    intent = str(data.get("intent", "other")).lower().strip()
    if intent not in INTENTS:
        raise TriageError(f"unknown intent: {intent}")

    return {
        "score": score,
        "intent": intent,
        "needs_human": bool(data.get("needs_human")) or intent == "complaint",
        "reply_draft": str(data.get("reply_draft", "")).strip(),
        "status": band(score),
    }
