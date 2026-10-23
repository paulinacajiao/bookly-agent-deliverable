"""
Knowledge tool: search_policies.

For Phase 1 this is a tiny keyword-matched FAQ - enough to demonstrate the
"general question" use case (shipping, returns policy, password reset) and the
grounding contract: the agent answers policy questions from THIS text, not from
the model's training memory.

In a later phase this becomes real retrieval (Supabase pgvector) over a policy
doc. The tool's shape - query in, snippets out - stays the same.
"""

from __future__ import annotations

# A compact, auditable policy base. Each entry is (keywords, answer).
_POLICIES = [
    (
        {"return", "refund", "window", "policy"},
        "Bookly accepts returns within 30 days of delivery for a full refund. "
        "Items must be in original condition.",
    ),
    (
        {"shipping", "ship", "delivery", "deliver", "arrive", "how long"},
        "Standard shipping is 3-5 business days. Express is 1-2 business days. "
        "Shipping is free on orders over $35.",
    ),
    (
        {"password", "reset", "login", "sign in", "account"},
        "To reset your password, go to bookly.com/account and click 'Forgot "
        "password'. You'll get a reset link by email within a few minutes.",
    ),
    (
        {"cancel", "cancellation"},
        "Orders can be cancelled free of charge any time before they ship. "
        "Once shipped, treat it as a return.",
    ),
]


def search_policies(query: str) -> dict:
    """Return the best-matching policy snippets for a free-text query.

    Returns {"status": "ok", "snippets": [...]} or {"status": "no_match"} so the
    agent knows when it genuinely has no grounded answer (and should say so or
    escalate) instead of inventing one.
    """
    q = (query or "").lower()
    hits = []
    for keywords, answer in _POLICIES:
        score = sum(1 for kw in keywords if kw in q)
        if score > 0:
            hits.append((score, answer))

    if not hits:
        return {"status": "no_match", "query": query}

    hits.sort(key=lambda h: h[0], reverse=True)
    return {"status": "ok", "snippets": [answer for _, answer in hits[:2]]}
