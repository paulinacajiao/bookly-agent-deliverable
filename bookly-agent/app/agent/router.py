"""
The router: classify_intent.

A one-shot call with a CLOSED output schema - the model must pick one of four
intent labels and report a confidence. It cannot invent a topic, and it has no
tools, so it cannot act.

It is a separate request from the conversation (own system prompt, no tools)
and sees only a plain-text rendering of the transcript: no thinking blocks, no
tool payloads. That keeps the main transcript untouched and append-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app import config
from app.agent.loop import BETAS
from app.agent.prompts import ROUTER_PROMPT

INTENTS = ["order_status", "refund", "faq", "unclear"]

_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "confidence": {"type": "number"},
    },
    "required": ["intent", "confidence"],
    "additionalProperties": False,
}

# How much recent conversation the router sees, in lines.
_CONTEXT_LINES = 6


@dataclass
class Route:
    intent: str
    confidence: float


def render_transcript(messages: list[dict]) -> str:
    """Customer/agent text only - what a human triager would read."""
    lines = []
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], str):
            lines.append(f"Customer: {m['content']}")
        elif m["role"] == "assistant":
            text = "".join(b.get("text", "") for b in m["content"]
                           if b.get("type") == "text").strip()
            if text:
                lines.append(f"Agent: {text}")
    return "\n".join(lines[-_CONTEXT_LINES:])


def classify_intent(client: Any, messages: list[dict]) -> Route:
    response = client.beta.messages.create(
        model=config.ROUTER_MODEL,
        max_tokens=1024,
        system=ROUTER_PROMPT,
        messages=[{"role": "user", "content": render_transcript(messages)}],
        output_config={"effort": config.ROUTER_EFFORT,
                       "format": {"type": "json_schema", "schema": _SCHEMA}},
        betas=BETAS,
        fallbacks="default",
    )
    # Anything unexpected (refusal, malformed output) routes to clarify:
    # when in doubt, ask - never guess.
    if response.stop_reason == "refusal":
        return Route("unclear", 0.0)
    try:
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        intent = data["intent"] if data["intent"] in INTENTS else "unclear"
        return Route(intent, float(data["confidence"]))
    except (StopIteration, ValueError, KeyError, TypeError):
        return Route("unclear", 0.0)
