"""
Order tools: lookup_order and get_order_status.

Every tool here returns a STRUCTURED dict with a 'status' field, never free
text. The agent's job later is to *narrate* these results - it must not invent
an order detail the tool didn't return. That's the anti-hallucination contract:
facts come from here, wording comes from the model.

Note the identity check in get_order_status: we don't reveal order details until
the email on file matches. Verify before you reveal.
"""

from __future__ import annotations

from app.data import store


def lookup_order(order_id: str) -> dict:
    """Low-level existence check. Returns the order or a not_found result.

    This is the gate that kills a hallucinated order id: if the model invents
    'ORD-9999', the store returns None and we report not_found instead of
    pretending the order exists.
    """
    order = store.get_order(order_id)
    if order is None:
        return {"status": "not_found", "order_id": order_id}
    return {"status": "ok", "order": order}


def get_order_status(order_id: str, email: str) -> dict:
    """Customer-facing status lookup. Requires identity verification.

    Returns one of:
      not_found          - no such order
      identity_mismatch  - order exists but email doesn't match (don't reveal!)
      ok                 - includes status, items, tracking, delivered_at
    """
    order = store.get_order(order_id)
    if order is None:
        return {"status": "not_found", "order_id": order_id}

    # Verify before you reveal: never expose order details to the wrong person.
    if order["email"].lower() != (email or "").strip().lower():
        return {"status": "identity_mismatch", "order_id": order_id}

    return {
        "status": "ok",
        "order_id": order["order_id"],
        "order_status": order["status"],
        "items": order["items"],
        "tracking": order["tracking"],
        "delivered_at": order["delivered_at"],
        "total": order["total"],
    }
