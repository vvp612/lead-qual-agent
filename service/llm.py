"""LLM layer: one tiny interface, two providers (mock is fully offline)."""
from __future__ import annotations

import json
import os
import re


class LLMError(RuntimeError):
    pass


class MockLLM:
    """Keyword-scored stand-in so triage behaves realistically offline.

    It scores from the prompt's `Message:` line (the inbound text), classifies intent
    by keyword, and copies the first knowledge-doc title it finds as the grounded
    source — enough for the whole pipeline and its tests to run without an API key.
    """

    HOT_WORDS = ("pricing", "quote", "bulk", "enterprise", "demo", "integration", "api", "partner")
    COMPLAINT_WORDS = ("refund", "broken", "not working", "attorney", "lawyer", "angry", "terrible", "scam", "cancel")
    QUESTION_WORDS = ("how", "what", "when", "where", "why", "does", "can i", "do you")

    def complete(self, system: str, prompt: str) -> str:
        msg = self._message(prompt)
        low = msg.lower()
        tokens = low.split()
        hot_signals = sum(w in low for w in self.HOT_WORDS)
        score = 15
        score += 12 * hot_signals
        if hot_signals >= 2:
            score += 10  # multiple buying signals compound
        score += 6 * sum(w in low for w in self.COMPLAINT_WORDS)
        score += min(len(tokens), 12)  # longer, substantive messages score a bit higher
        if sum(w in low for w in self.COMPLAINT_WORDS) >= 2:
            intent = "complaint"
        elif any(w in low for w in self.HOT_WORDS):
            intent = "demo_request" if "demo" in low else "sales"
        elif any(w in low for w in self.QUESTION_WORDS):
            intent = "support"
        elif len(tokens) < 6:
            intent = "spam"
            score = min(score, 8)
        else:
            intent = "other"
        needs_human = intent == "complaint" or score >= 85
        source = self._source(prompt)
        reply = self._reply(intent, low, source)
        return json.dumps({"score": score, "intent": intent, "needs_human": needs_human, "reply_draft": reply})

    @staticmethod
    def _message(prompt: str) -> str:
        for line in prompt.splitlines():
            if line.startswith("Message:"):
                return line[len("Message:"):].strip()
        return ""

    @staticmethod
    def _source(prompt: str) -> str:
        match = re.search(r'Source: "([^"]+)"', prompt)
        return match.group(1) if match else ""

    @staticmethod
    def _reply(intent: str, low: str, source: str) -> str:
        cite = f" (per our {source})" if source else ""
        if intent == "complaint":
            return f"I'm really sorry about this{cite}. I've flagged a teammate to make it right today."
        if intent in ("demo_request", "sales"):
            return f"Great to hear you're interested{cite}! Could we book a short call this week?"
        if intent == "support":
            return f"Happy to help{cite} — here's how that works."
        return "Thanks for reaching out — we'll get back to you shortly."


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        from anthropic import Anthropic  # lazy: mock mode needs no provider dep

        self.client = Anthropic(api_key=api_key)
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def complete(self, system: str, prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model, max_tokens=1000, system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise LLMError(f"Anthropic call failed: {exc}") from exc
        return "".join(b.text for b in response.content if b.type == "text")


def get_llm(prefer: str | None = None):
    choice = prefer or os.environ.get("TRIAGE_LLM", "")
    if choice == "mock":
        return MockLLM()
    if choice == "anthropic" or os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicLLM()
    return MockLLM()
