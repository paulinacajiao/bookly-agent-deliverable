"""
Offline mock model for `python -m app.cli --mock`.

Lets you run the agent with NO ANTHROPIC_API_KEY: a scripted stand-in plays the
role of Claude. It is deliberately simple — it pattern-matches the documented
demo scenarios (order status, refund, FAQ, clarify, identity mismatch), calls
the REAL tools (so the real deterministic guards run on the mock data), and
narrates the result. It does NOT improvise on off-script input; for open-ended
chat use a real API key or the hosted demo.

It mimics only the slice of the Anthropic SDK the agent uses:
  client.beta.messages.create(...)  -> the router  (returns {intent, confidence})
  client.beta.messages.stream(...)  -> the loop    (returns text or a tool_use)
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.agent.prompts import SKILL_PROMPTS

_ORDER_RE = re.compile(r"ORD-\d+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


# --- tiny stand-ins for the SDK's response objects ------------------------

class _Block:
    def __init__(self, type: str, **kw: Any):
        self.type = type
        self.__dict__.update(kw)

    def to_dict(self, **_: Any) -> dict:
        if self.type == "text":
            return {"type": "text", "text": self.text}
        return {"type": "tool_use", "id": self.id, "name": self.name,
                "input": self.input}


class _Message:
    def __init__(self, content: list[_Block], stop_reason: str):
        self.content = content
        self.stop_reason = stop_reason


class _Stream:
    def __init__(self, message: _Message, text: str):
        self._message = message
        self._text = text

    def __enter__(self): return self
    def __exit__(self, *a): return False

    @property
    def text_stream(self):
        if self._text:
            yield self._text

    def get_final_message(self) -> _Message:
        return self._message


def _say(text: str) -> _Message:
    return _Message([_Block("text", text=text)], "end_turn")


def _call(name: str, args: dict) -> _Message:
    block = _Block("tool_use", id=f"mock_{uuid.uuid4().hex[:8]}", name=name,
                   input=args)
    return _Message([block], "tool_use")


# --- the demo "brain" -----------------------------------------------------

def _active_skill(messages: list[dict]) -> str | None:
    """Which skill has the floor — detected from the appended system prompt."""
    for m in reversed(messages):
        if m.get("role") == "system":
            for name, prompt in SKILL_PROMPTS.items():
                if m.get("content") == prompt:
                    return name
    return None


def _user_texts(messages: list[dict]) -> list[str]:
    return [m["content"] for m in messages
            if m.get("role") == "user" and isinstance(m.get("content"), str)]


def _extract(messages: list[dict]) -> tuple[str | None, str | None, str | None]:
    """Pull an order id, email and a free-text reason from the whole transcript."""
    order_id = email = reason = None
    for text in _user_texts(messages):
        if (m := _ORDER_RE.search(text)):
            order_id = m.group(0).upper()
        if (e := _EMAIL_RE.search(text)):
            email = e.group(0)
    for text in _user_texts(messages):
        stripped = _ORDER_RE.sub("", _EMAIL_RE.sub("", text)).strip(" ,.-")
        if len(stripped) > 3:
            reason = stripped
            break
    return order_id, email, reason


def _route(rendered: str) -> dict:
    t = rendered.lower()
    if any(w in t for w in ("return", "refund", "money back")):
        return {"intent": "refund", "confidence": 0.9}
    if any(w in t for w in ("shipping", "deliver", "how long", "policy",
                            "password", "reset", "cancel")):
        return {"intent": "faq", "confidence": 0.85}
    if any(w in t for w in ("where", "status", "track", "order", "arriv")):
        return {"intent": "order_status", "confidence": 0.9}
    return {"intent": "unclear", "confidence": 0.3}


def _narrate_one(data: dict) -> str:
    status = data.get("status")
    if status == "ok" and "order_status" in data:
        bits = [f"Your order {data.get('order_id')} is {data['order_status']}."]
        if data.get("items"):
            bits.append(f"Item(s): {', '.join(data['items'])}.")
        if data.get("tracking"):
            bits.append(f"Tracking: {data['tracking']}.")
        return " ".join(bits)
    if status == "identity_mismatch":
        return ("Those details don't match our records — please double-check the "
                "email on the order.")
    if status == "not_found":
        return "I couldn't find an order with that number. Could you re-check it?"
    if status == "refunded":
        return (f"All set — your refund of ${data.get('amount')} is on its way "
                f"(reference {data.get('return_id')}).")
    if status == "refused":
        reasons = {
            "outside_window": "that order is past our 30-day return window",
            "not_delivered": "that order hasn't been delivered yet",
            "already_returned": "that order has already been returned",
            "identity_mismatch": "the email doesn't match the order",
            "not_found": "I couldn't find that order",
        }
        return ("I'm sorry, I can't process that refund — "
                f"{reasons.get(data.get('reason'), 'it is not eligible')}.")
    if status == "ok" and data.get("snippets"):
        return " ".join(data["snippets"])
    if status == "no_match":
        return ("I can help with Bookly orders, returns, and store policies — "
                "could you rephrase?")
    if status == "escalated":
        return (f"I've connected you with a specialist (ticket "
                f"{data.get('ticket_id')}) who'll follow up.")
    return ""


def _narrate(tool_results: list[dict]) -> _Message:
    parts = []
    for block in tool_results:
        try:
            parts.append(_narrate_one(json.loads(block["content"])))
        except (ValueError, KeyError, TypeError):
            continue
    text = " ".join(p for p in parts if p) or \
        "Done. Is there anything else I can help with?"
    return _say(text)


def _ask_missing(order_id: str | None, email: str | None) -> str:
    if not order_id and not email:
        return ("Happy to help — what's your order number (like ORD-1004) and the "
                "email on the order?")
    if not order_id:
        return "Thanks — and what's the order number (like ORD-1004)?"
    return "Thanks — and what's the email address on that order?"


_CLARIFY = ("I can help with order status, returns and refunds, or questions "
            "about Bookly's policies. Which one can I help you with?")


def _respond(messages: list[dict]) -> _Message:
    last = messages[-1] if messages else {}
    content = last.get("content")
    if (last.get("role") == "user" and isinstance(content, list) and content
            and content[0].get("type") == "tool_result"):
        return _narrate(content)

    skill = _active_skill(messages)
    order_id, email, reason = _extract(messages)
    texts = _user_texts(messages)
    latest = texts[-1] if texts else ""
    route = _route(latest)
    desired, conf = route["intent"], route["confidence"]
    has_info = bool(_ORDER_RE.search(latest) or _EMAIL_RE.search(latest))
    topics = ("order_status", "refund", "faq")

    # Customer changed topic inside a locked thread -> hand off (bounded to once
    # by the graph, same as the real agent).
    if skill in topics and desired in topics and desired != skill and conf >= 0.85:
        return _call("switch_topic", {"topic": desired})

    # Only act when THIS message is relevant: it brought info (an id/email), or
    # it's clearly the same topic. A vague aside doesn't re-trigger a tool.
    relevant = has_info or (desired == skill and conf >= 0.85)

    if skill == "faq":
        return _call("search_policies", {"query": latest})
    if skill == "order_status":
        if not relevant:
            return _say(_CLARIFY)
        if order_id and email:
            return _call("get_order_status",
                         {"order_id": order_id, "email": email})
        return _say(_ask_missing(order_id, email))
    if skill == "refund":
        if not relevant:
            return _say(_CLARIFY)
        if order_id and email:
            return _call("create_return", {"order_id": order_id, "email": email,
                                           "reason": reason or "customer request"})
        return _say(_ask_missing(order_id, email))
    # clarify (or unknown): ask, never guess
    return _say(_CLARIFY)


# --- the SDK-shaped client -----------------------------------------------

class _Messages:
    def create(self, **kw: Any) -> _Message:
        msgs = kw.get("messages", [])
        rendered = msgs[-1]["content"] if msgs and isinstance(
            msgs[-1].get("content"), str) else ""
        return _Message([_Block("text", text=json.dumps(_route(rendered)))],
                        "end_turn")

    def stream(self, **kw: Any) -> _Stream:
        message = _respond(kw.get("messages", []))
        text = next((b.text for b in message.content if b.type == "text"), "")
        return _Stream(message, text)


class _Beta:
    def __init__(self):
        self.messages = _Messages()


class MockClient:
    """A keyless stand-in for anthropic.Anthropic, for `--mock` demos."""

    def __init__(self):
        self.beta = _Beta()
