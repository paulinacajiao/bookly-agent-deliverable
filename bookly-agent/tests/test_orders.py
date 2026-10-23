"""
Tests for order lookup / status tools, including the identity guard.
"""

import pytest

from app.data import store
from app.tools.orders import lookup_order, get_order_status
from app.tools.knowledge import search_policies


@pytest.fixture(autouse=True)
def _fresh_store():
    store.reset()
    yield
    store.reset()


def test_lookup_existing_order():
    result = lookup_order("ORD-1005")
    assert result["status"] == "ok"
    assert result["order"]["items"] == ["The Creative Act"]


def test_lookup_is_case_insensitive():
    # Customers won't always type the id in caps.
    result = lookup_order("ord-1005")
    assert result["status"] == "ok"


def test_lookup_missing_order():
    assert lookup_order("ORD-0000")["status"] == "not_found"


def test_status_requires_matching_email():
    # Right order, wrong person -> do not reveal details.
    result = get_order_status("ORD-1005", "carlos@email.com")
    assert result["status"] == "identity_mismatch"
    assert "items" not in result


def test_status_happy_path():
    result = get_order_status("ORD-1004", "carlos@email.com")
    assert result["status"] == "ok"
    assert result["order_status"] == "shipped"
    assert result["tracking"] == "1Z-CARL-1004"


# --- Knowledge tool grounding -------------------------------------------------
def test_policy_search_finds_shipping():
    result = search_policies("how long does shipping take?")
    assert result["status"] == "ok"
    assert any("3-5 business days" in s for s in result["snippets"])


def test_policy_search_no_match_is_explicit():
    # Out-of-scope question -> no_match, so the agent knows NOT to invent.
    result = search_policies("what is the meaning of life?")
    assert result["status"] == "no_match"
