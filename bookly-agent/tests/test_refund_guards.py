"""
Tests for the deterministic refund guards.

Read these as the SPEC for the AOP: each test is one business rule the agent
can never violate, no matter what the model decides. If all of these pass, the
money-touching logic is correct independent of any LLM.
"""

import pytest

from app.data import store
from app.tools.refunds import check_refund_eligibility, create_return
from app.tools import policies


@pytest.fixture(autouse=True)
def _fresh_store():
    """Reset the in-memory store before every test so side effects don't leak."""
    store.reset()
    yield
    store.reset()


# --- GATE 1: existence --------------------------------------------------------
def test_hallucinated_order_is_not_found():
    result = create_return("ORD-9999", "jane@email.com", "changed mind")
    assert result["status"] == "refused"
    assert result["reason"] == "not_found"


# --- GATE 2: identity ---------------------------------------------------------
def test_wrong_email_is_rejected():
    # ORD-1001 belongs to jane, not carlos.
    result = create_return("ORD-1001", "carlos@email.com", "changed mind")
    assert result["status"] == "refused"
    assert result["reason"] == "identity_mismatch"


# --- GATE 4: order state ------------------------------------------------------
def test_not_delivered_order_cannot_be_returned():
    # ORD-1004 is still 'shipped'.
    result = create_return("ORD-1004", "carlos@email.com", "changed mind")
    assert result["status"] == "refused"
    assert result["reason"] == "not_delivered"


# --- GATE 5: return window ----------------------------------------------------
def test_outside_window_is_refused():
    # ORD-1003 was delivered 45 days ago (> 30-day window).
    result = create_return("ORD-1003", "carlos@email.com", "changed mind")
    assert result["status"] == "refused"
    assert result["reason"] == "outside_window"


# --- No money threshold: any eligible order refunds automatically -----------
def test_large_eligible_order_is_refunded_automatically():
    # ORD-1002 ($89, multi-item, within window) refunds with no human step.
    result = create_return("ORD-1002", "jane@email.com", "damaged")
    assert result["status"] == "refunded"
    assert result["amount"] == 89.00
    recorded = store.all_returns()[result["return_id"]]
    assert recorded["state"] == "refunded"


# --- Happy path: eligible auto-refund ----------------------------------------
def test_eligible_order_is_refunded():
    # ORD-1001: delivered 5 days ago, $24.
    result = create_return("ORD-1001", "jane@email.com", "changed mind")
    assert result["status"] == "refunded"
    assert result["amount"] == 24.00
    assert result["return_id"].startswith("RET-")


# --- GATE 3: idempotency ------------------------------------------------------
def test_cannot_refund_the_same_order_twice():
    first = create_return("ORD-1001", "jane@email.com", "changed mind")
    assert first["status"] == "refunded"
    # Second attempt must be refused - the order is now in a returned state.
    second = create_return("ORD-1001", "jane@email.com", "changed mind")
    assert second["status"] == "refused"
    assert second["reason"] == "already_returned"


# --- Read-only check never moves money ---------------------------------------
def test_eligibility_check_has_no_side_effects():
    before = store.all_returns()
    check = check_refund_eligibility("ORD-1001", "jane@email.com")
    assert check["status"] == "eligible"
    # No return record was created by a read-only check.
    assert store.all_returns() == before


def test_policy_constants_are_sane():
    assert policies.RETURN_WINDOW_DAYS == 30
    assert not hasattr(policies, "AUTO_APPROVE_LIMIT")  # removed: no approval step
