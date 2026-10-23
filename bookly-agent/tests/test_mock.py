"""
Tests for the offline --mock model: the agent runs end-to-end with NO API key,
and the REAL deterministic guards still fire on the mock data.
"""

import pytest

from app.agent.graph import Conversation
from app.data import store
from app.mock_model import MockClient


@pytest.fixture(autouse=True)
def _fresh_store():
    store.reset()
    yield
    store.reset()


def _reply(convo: Conversation, text: str) -> str:
    return convo.send(text)["reply"]


def test_order_status_is_grounded():
    c = Conversation(client=MockClient())
    reply = _reply(c, "Where is my order ORD-1004? email carlos@email.com")
    assert "shipped" in reply.lower()
    assert "Project Hail Mary" in reply


def test_identity_guard_reveals_nothing():
    # ORD-1004 belongs to carlos, not jane.
    c = Conversation(client=MockClient())
    reply = _reply(c, "Status of ORD-1004? email jane@email.com")
    assert "match" in reply.lower()
    assert "Project Hail Mary" not in reply


def test_refund_happy_path_executes():
    c = Conversation(client=MockClient())
    reply = _reply(c, "I want to return ORD-1001, jane@email.com, didn't like it")
    assert "refund" in reply.lower()
    assert "24" in reply


def test_refund_outside_window_is_refused():
    # ORD-1003 was delivered 45 days ago (> 30-day window).
    c = Conversation(client=MockClient())
    reply = _reply(c, "I want to return ORD-1003, carlos@email.com, changed mind")
    assert "window" in reply.lower()


def test_vague_request_asks_a_clarifying_question():
    c = Conversation(client=MockClient())
    reply = _reply(c, "Hi, I need help with something")
    assert "?" in reply


def test_multi_turn_collects_then_acts():
    c = Conversation(client=MockClient())
    first = _reply(c, "I want to return a book")
    assert "?" in first                       # asks for the missing info first
    second = _reply(c, "ORD-1001, jane@email.com")
    assert "refund" in second.lower()         # then acts once it has it


def test_faq_is_grounded():
    c = Conversation(client=MockClient())
    reply = _reply(c, "How long does shipping take?")
    assert "business days" in reply.lower()


def test_topic_switch_and_vague_aside_in_one_conversation():
    # All in ONE thread: status -> switch to refund -> a vague aside.
    c = Conversation(client=MockClient())
    _reply(c, "Where is my order ORD-1004? email carlos@email.com")
    r2 = _reply(c, "Actually I want to return ORD-1001, jane@email.com, no good")
    assert "refund" in r2.lower() and "24" in r2        # handed off to refund
    r3 = _reply(c, "hmm I need help with something")
    assert "?" in r3 and "refund of" not in r3.lower()  # clarifies, doesn't re-act
