"""
In-memory mock data store for Bookly.

This stands in for the Supabase database during Phases 1-4 so the whole agent
can be built and tested with NO cloud, NO API keys, and NO network calls.
In Phase 5 we replace THIS module with real Supabase queries - the tool
functions that call it won't have to change, because they only depend on the
function signatures below (get_order, get_customer, save_return, ...).

Think of this as the "source of truth" the deterministic guards check against.
A hallucinated order id or a forged email dies here, because this is the only
place that knows what's actually real.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy


def _days_ago(n: int) -> str:
    """Return an ISO timestamp n days in the past (UTC).

    We seed dates RELATIVE to 'now' so the return-window test cases stay valid
    no matter when you run them - an order 'delivered 5 days ago' is always
    inside a 30-day window; '45 days ago' is always outside it.
    """
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
# Each order is crafted to exercise one branch of the refund guard:
#
#   ORD-1001  delivered  5d ago  $24  -> eligible, auto-refund (under $50)
#   ORD-1002  delivered 10d ago  $89  -> eligible BUT over $50 -> human approval
#   ORD-1003  delivered 45d ago  $30  -> OUTSIDE the 30-day return window
#   ORD-1004  shipped (in transit) $18 -> not delivered -> not returnable yet
#   ORD-1005  processing          $55 -> not shipped yet -> order-status demo
# ---------------------------------------------------------------------------

_SEED_CUSTOMERS = {
    "jane@email.com": {"name": "Jane Doe", "email": "jane@email.com"},
    "carlos@email.com": {"name": "Carlos Ruiz", "email": "carlos@email.com"},
}

_SEED_ORDERS = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "email": "jane@email.com",
        "status": "delivered",
        "delivered_at": _days_ago(5),
        "total": 24.00,
        "items": ["The Midnight Library"],
        "tracking": "1Z-JANE-1001",
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "email": "jane@email.com",
        "status": "delivered",
        "delivered_at": _days_ago(10),
        "total": 89.00,
        "items": ["Sapiens (Hardcover)", "Educated"],
        "tracking": "1Z-JANE-1002",
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "email": "carlos@email.com",
        "status": "delivered",
        "delivered_at": _days_ago(45),
        "total": 30.00,
        "items": ["Atomic Habits"],
        "tracking": "1Z-CARL-1003",
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "email": "carlos@email.com",
        "status": "shipped",
        "delivered_at": None,
        "total": 18.00,
        "items": ["Project Hail Mary"],
        "tracking": "1Z-CARL-1004",
    },
    "ORD-1005": {
        "order_id": "ORD-1005",
        "email": "jane@email.com",
        "status": "processing",
        "delivered_at": None,
        "total": 55.00,
        "items": ["The Creative Act"],
        "tracking": None,
    },
}

# Mutable runtime copies (so side effects like create_return don't corrupt seeds).
_customers: dict = {}
_orders: dict = {}
_returns: dict = {}
_escalations: dict = {}


def reset() -> None:
    """Restore the store to its seeded state. Call this at the start of tests."""
    global _customers, _orders, _returns, _escalations
    _customers = deepcopy(_SEED_CUSTOMERS)
    _orders = deepcopy(_SEED_ORDERS)
    _returns = {}
    _escalations = {}


# Initialize on import.
reset()


# ---------------------------------------------------------------------------
# Read access (the "SELECT" layer)
# ---------------------------------------------------------------------------
def get_order(order_id: str) -> dict | None:
    """Return the order dict, or None if no such order exists."""
    if not order_id:
        return None
    return _orders.get(order_id.strip().upper())


def get_customer(email: str) -> dict | None:
    if not email:
        return None
    return _customers.get(email.strip().lower())


# ---------------------------------------------------------------------------
# Write access (the "side effect" layer) - only the guards should reach here
# ---------------------------------------------------------------------------
def save_return(order_id: str, reason: str, amount: float, state: str) -> dict:
    """Record a return/refund row and return it. `state` is e.g.
    'refunded'."""
    ret = {
        "return_id": f"RET-{len(_returns) + 1:04d}",
        "order_id": order_id,
        "reason": reason,
        "amount": amount,
        "state": state,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _returns[ret["return_id"]] = ret
    return ret


def set_order_status(order_id: str, status: str) -> None:
    order = _orders.get(order_id.strip().upper())
    if order:
        order["status"] = status


def save_escalation(order_id: str | None, summary: str) -> dict:
    """Open a ticket for a human specialist and return it."""
    esc = {
        "ticket_id": f"ESC-{len(_escalations) + 1:04d}",
        "order_id": order_id,
        "summary": summary,
        "state": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _escalations[esc["ticket_id"]] = esc
    return deepcopy(esc)


def all_escalations() -> dict:
    """Test/debug helper: snapshot of escalation tickets."""
    return deepcopy(_escalations)


def all_returns() -> dict:
    """Test/debug helper: snapshot of recorded returns."""
    return deepcopy(_returns)
