"""
Supabase (Postgres) data store - the real "source of truth" from Phase 5 on.

Same function signatures and return shapes as mock_store.py, so the tools and
guards above it didn't change. That's the point of building mock-first: the
deterministic core was proven before any database existed.

Connects with the SERVICE ROLE key, server-side only. The storefront's browser
key (anon) can't read orders or write returns - RLS blocks it - so the agent
must never be configured with it. Schema: bookly-web/supabase/schema.sql plus
supabase/001_agent_phase5.sql (escalations, id sequences, reset_demo()).
"""

from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def _db() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "BOOKLY_DATA=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "in .env (the anon key can't read orders - by design).")
    return create_client(url, key)


def _order(row: dict) -> dict:
    # numeric -> float, matching the mock store's types.
    return {**row, "total": float(row["total"])}


def _return(row: dict) -> dict:
    return {**row, "amount": float(row["amount"]) if row["amount"] is not None else None}


def reset() -> None:
    """Restore the demo seed (dates relative to now). Call at test start."""
    _db().rpc("reset_demo").execute()


# ---------------------------------------------------------------------------
# Read access
# ---------------------------------------------------------------------------
def get_order(order_id: str) -> dict | None:
    if not order_id:
        return None
    rows = (_db().table("orders").select("*")
            .eq("order_id", order_id.strip().upper()).execute().data)
    return _order(rows[0]) if rows else None


def get_customer(email: str) -> dict | None:
    if not email:
        return None
    rows = (_db().table("customers").select("*")
            .eq("email", email.strip().lower()).execute().data)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Write access - only the guards should reach here
# ---------------------------------------------------------------------------
def save_return(order_id: str, reason: str, amount: float, state: str) -> dict:
    """Insert a return row; the database assigns return_id (RET-0001...)."""
    row = (_db().table("returns")
           .insert({"order_id": order_id.strip().upper(), "reason": reason,
                    "amount": amount, "state": state})
           .execute().data[0])
    return _return(row)


def set_order_status(order_id: str, status: str) -> None:
    (_db().table("orders").update({"status": status})
     .eq("order_id", order_id.strip().upper()).execute())


def save_escalation(order_id: str | None, summary: str) -> dict:
    """Insert a ticket; the database assigns ticket_id (ESC-0001...)."""
    return (_db().table("escalations")
            .insert({"order_id": order_id, "summary": summary})
            .execute().data[0])


def all_escalations() -> dict:
    rows = _db().table("escalations").select("*").execute().data
    return {r["ticket_id"]: r for r in rows}


def all_returns() -> dict:
    rows = _db().table("returns").select("*").execute().data
    return {r["return_id"]: _return(r) for r in rows}
