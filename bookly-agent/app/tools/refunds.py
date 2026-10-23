"""
Refund tools: check_refund_eligibility (read-only) and create_return (acts).

THIS IS THE DETERMINISTIC CORE - the "code disposes" half of "LLM proposes,
code disposes." The model may REQUEST a refund with any arguments it likes
(including hallucinated ones). It can never PERFORM one: the only code that
touches money is create_return, and it re-checks every rule against the store
before doing anything irreversible.

The guards run in order. The first failing gate short-circuits:

    GATE 1  existence         -> catches a hallucinated order id
    GATE 2  identity          -> code verifies the email, not the model
    GATE 3  already returned   -> idempotency; can't refund twice
    GATE 4  order state        -> can't return what wasn't delivered
    GATE 5  return window      -> deterministic policy, not a vibe

If every gate passes, the refund executes immediately - no human step. The
agent's job is to collect and verify the inputs (order id, email, reason);
code decides whether the refund is allowed.

Both functions share _evaluate() so the read-only check and the acting function
can never disagree about the rules.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.data import store
from app.tools import policies


def _days_since(iso_ts: str | None) -> float | None:
    """Whole/fractional days since an ISO timestamp, or None if not set."""
    if not iso_ts:
        return None
    then = datetime.fromisoformat(iso_ts)
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400.0


def _evaluate(order_id: str, email: str) -> dict:
    """Run every gate and return a decision dict. Pure, no side effects.

    Returns:
      {"decision": "eligible"|"ineligible", "code": <str>,
       "order": <order or None>, "amount": <float or None>}
    """
    order = store.get_order(order_id)

    # GATE 1 - existence
    if order is None:
        return {"decision": "ineligible", "code": "not_found",
                "order": None, "amount": None}

    # GATE 2 - identity (verify before you act)
    if order["email"].lower() != (email or "").strip().lower():
        return {"decision": "ineligible", "code": "identity_mismatch",
                "order": order, "amount": None}

    # GATE 3 - idempotency: already returned?
    if order["status"] in {"returned", "return_initiated"}:
        return {"decision": "ineligible", "code": "already_returned",
                "order": order, "amount": None}

    # GATE 4 - order must be in a returnable state (delivered)
    if order["status"] not in policies.RETURNABLE_STATUSES:
        return {"decision": "ineligible", "code": "not_delivered",
                "order": order, "amount": None}

    # GATE 5 - return window
    age = _days_since(order["delivered_at"])
    if age is None or age > policies.RETURN_WINDOW_DAYS:
        return {"decision": "ineligible", "code": "outside_window",
                "order": order, "amount": None}

    return {"decision": "eligible", "code": "ok",
            "order": order, "amount": order["total"]}


def check_refund_eligibility(order_id: str, email: str) -> dict:
    """Read-only: tells the agent whether a refund is possible and why.

    The agent can call this to decide what to say WITHOUT committing anything.
    No money moves here.
    """
    result = _evaluate(order_id, email)
    return {
        "status": result["decision"],   # eligible | ineligible
        "reason": result["code"],
        "order_id": order_id,
        "amount": result["amount"],
        "return_window_days": policies.RETURN_WINDOW_DAYS,
    }


def create_return(order_id: str, email: str, reason: str) -> dict:
    """Acts: the ONLY function that records a return / moves money.

    It re-runs the full evaluation itself - it does NOT trust an earlier
    check_refund_eligibility call, because state could have changed and because
    the model might call it directly. Code disposes.
    """
    result = _evaluate(order_id, email)
    decision = result["decision"]

    # Ineligible -> refuse, surface the specific reason for the agent to narrate.
    if decision == "ineligible":
        return {"status": "refused", "reason": result["code"],
                "order_id": order_id}

    # Eligible -> perform the side effect: record refund + flip order state.
    ticket = store.save_return(
        order_id, reason, result["amount"], state="refunded")
    store.set_order_status(order_id, "return_initiated")
    return {"status": "refunded", "amount": result["amount"],
            "return_id": ticket["return_id"], "order_id": order_id}

