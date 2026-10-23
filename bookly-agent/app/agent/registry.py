"""
Tool registry: the JSON schemas the model sees + the dispatcher that runs them.

This is the seam between "LLM proposes" and "code disposes". The model can only
REQUEST a tool by name with arguments; dispatch() decides whether that tool is
allowed in the current skill and calls the real Python function. Unknown names,
out-of-skill tools and bad arguments come back as structured errors - nothing
the model emits is executed blindly.

Why every schema is sent on every request, even though each skill may use only
a few: Claude Sonnet 5.5 binds its reasoning to the exact `system` + `tools` it
saw, and rejects a conversation whose tool list changed mid-way. So the tool
list is frozen for the whole conversation and skill scoping is enforced HERE,
in code (SKILL_TOOLS). The prompt says which tools a skill may use; the
dispatcher makes it true.

Deliberately NOT exposed to the model: lookup_order. It returns a full order
(including the email on file) with no identity check, so it stays an internal
helper. Every model-facing order tool verifies the email first.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from app.tools.escalation import escalate_to_human
from app.tools.knowledge import search_policies
from app.tools.orders import get_order_status
from app.tools.refunds import check_refund_eligibility, create_return

# Topics a skill can hand the conversation to (see switch_topic).
TOPICS = ["order_status", "refund", "faq"]

_ORDER_ID = {
    "type": "string",
    "description": "Order number exactly as the customer gave it, e.g. ORD-1004.",
}
_EMAIL = {
    "type": "string",
    "description": "Email address the customer says is on the order.",
}


def _schema(name: str, description: str, properties: dict) -> dict:
    # Strict mode: the API guarantees inputs match the schema exactly.
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


TOOL_SCHEMAS: list[dict] = [
    _schema(
        "get_order_status",
        "Look up the current status of a customer's Bookly order: fulfilment "
        "status, items, tracking number, delivery date and total. Requires the "
        "order number AND the email on the order; the email is verified "
        "against our records before anything is returned. Only call this once "
        "the customer has given you both - never guess them. Returns JSON whose "
        "`status` is ok, not_found, or identity_mismatch.",
        {"order_id": _ORDER_ID, "email": _EMAIL},
    ),
    _schema(
        "check_refund_eligibility",
        "Read-only check of whether an order can be returned for a refund, and "
        "why not if it can't. Moves no money. Requires the order number and the "
        "email on the order (verified). Returns JSON whose `status` is "
        "eligible or ineligible, with a `reason` code, the refund `amount`, "
        "and `return_window_days`.",
        {"order_id": _ORDER_ID, "email": _EMAIL},
    ),
    _schema(
        "create_return",
        "Submit a return and refund request for an order. This is the ONLY way "
        "a refund happens. Call it only after the customer has given the order "
        "number, the email on the order, and a reason, and has asked to go "
        "ahead. All eligibility rules are re-checked on our side, and if they "
        "pass the refund is issued immediately. Returns JSON whose `status` "
        "is refunded (with amount and return_id) or refused (with a `reason` "
        "code).",
        {
            "order_id": _ORDER_ID,
            "email": _EMAIL,
            "reason": {
                "type": "string",
                "description": "The customer's reason for the return, in their words.",
            },
        },
    ),
    _schema(
        "search_policies",
        "Search Bookly's official policies (shipping, returns, password reset, "
        "cancellations). Returns JSON whose `status` is ok with `snippets` of "
        "policy text, or no_match when we have no policy on the topic.",
        {"query": {"type": "string",
                   "description": "The customer's question, in plain words."}},
    ),
    _schema(
        "escalate_to_human",
        "Hand the customer to a human specialist by opening a support ticket. "
        "Use when the customer asks for a person, is upset, or needs something "
        "you can't do (e.g. an exception to policy). Only call it after the "
        "customer agrees. Returns JSON with `status` escalated and a "
        "`ticket_id` to give the customer.",
        {
            "order_id": {
                "type": "string",
                "description": "The order this is about, or an empty string if none.",
            },
            "summary": {
                "type": "string",
                "description": "2-3 sentences for the specialist: what the customer "
                               "wants, what you checked, and the tool results, so "
                               "the customer doesn't have to repeat themselves.",
            },
        },
    ),
    _schema(
        "switch_topic",
        "Hand the conversation to a different topic when the customer's need "
        "has moved outside your current instructions (e.g. they were asking "
        "about delivery and now want a refund). Do not answer the new request "
        "yourself first.",
        {"topic": {"type": "string", "enum": TOPICS,
                   "description": "The topic the customer needs now."}},
    ),
]


def _switch_topic(topic: str) -> dict:
    # The graph does the actual re-routing; this just acknowledges it.
    return {"status": "ok", "switched_to": topic}


_FUNCTIONS: dict[str, Callable[..., dict]] = {
    "get_order_status": get_order_status,
    "check_refund_eligibility": check_refund_eligibility,
    "create_return": create_return,
    "search_policies": search_policies,
    "escalate_to_human": escalate_to_human,
    "switch_topic": _switch_topic,
}

# What a streaming chat UI shows while each tool runs.
STATUS_LABELS: dict[str, str] = {
    "get_order_status": "Looking up your order…",
    "check_refund_eligibility": "Checking return eligibility…",
    "create_return": "Processing your refund…",
    "search_policies": "Searching our policies…",
    "escalate_to_human": "Connecting you with a specialist…",
    "switch_topic": "One moment…",
}

# Which tools each skill may actually run. Enforced by dispatch().
SKILL_TOOLS: dict[str, frozenset[str]] = {
    "order_status": frozenset({"get_order_status", "escalate_to_human",
                               "switch_topic"}),
    "refund": frozenset({"check_refund_eligibility", "create_return",
                         "search_policies", "escalate_to_human", "switch_topic"}),
    "faq": frozenset({"search_policies", "escalate_to_human", "switch_topic"}),
    "clarify": frozenset(),
}


def dispatch(name: str, args: dict[str, Any],
             allowed: frozenset[str] | None = None) -> tuple[dict, bool]:
    """Run a tool the model requested. Returns (result_dict, is_error).

    `allowed` is the active skill's tool set; None means no restriction.
    Never raises: a failure becomes a structured error the model can narrate
    instead of crashing the conversation.
    """
    fn = _FUNCTIONS.get(name)
    if fn is None:
        return {"status": "error", "error": f"unknown tool: {name}"}, True
    if allowed is not None and name not in allowed:
        return {"status": "error",
                "error": f"{name} is not available for this request"}, True
    try:
        return fn(**args), False
    except TypeError as exc:  # wrong/missing arguments
        return {"status": "error", "error": f"bad arguments: {exc}"}, True
    except Exception as exc:  # tool bug - don't leak a stack trace to the model
        return {"status": "error", "error": type(exc).__name__}, True


def to_content(result: dict) -> str:
    """Serialize a tool result for a tool_result block (stable key order)."""
    return json.dumps(result, sort_keys=True, default=str)
