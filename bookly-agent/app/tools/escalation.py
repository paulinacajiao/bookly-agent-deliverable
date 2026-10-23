"""
Escalation tool: escalate_to_human.

Opens a ticket for a human specialist with a summary of the conversation, so
the customer never has to repeat themselves. It reveals nothing and moves no
money, so it needs no identity check - the specialist verifies the customer.
"""

from __future__ import annotations

from app.data import store


def escalate_to_human(order_id: str, summary: str) -> dict:
    """Returns {"status": "escalated", "ticket_id": ...}.

    `order_id` may be empty when the request isn't about a specific order. An
    order number we don't recognise is kept in the summary rather than linked,
    so the ticket still opens (a customer asking for a human shouldn't be
    blocked by a typo).
    """
    summary = (summary or "").strip()
    if not summary:
        return {"status": "error", "error": "summary is required"}

    order_id = (order_id or "").strip().upper() or None
    if order_id and store.get_order(order_id) is None:
        summary = f"[customer cited unknown order {order_id}] {summary}"
        order_id = None

    ticket = store.save_escalation(order_id, summary)
    return {"status": "escalated", "ticket_id": ticket["ticket_id"]}
