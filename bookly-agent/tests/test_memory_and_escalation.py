"""
Memory and escalation tests - offline.

  * a thread's state survives across turns via the checkpointer, and threads
    are isolated from each other
  * an eligible refund of any size completes in one turn - no human step
  * escalate_to_human opens a ticket
"""

import json

import pytest

from app.agent.graph import Conversation, build_graph
from app.data import store
from app.tools.escalation import escalate_to_human
from tests.fakes import FakeClient, reply, route, text, tool_use


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()


ORD_1002 = {"order_id": "ORD-1002", "email": "jane@email.com"}


def refund_1002_script(final_text):
    return FakeClient(
        router=[route("refund")],
        model=[
            reply("tool_use", tool_use("create_return",
                                       {**ORD_1002, "reason": "arrived damaged"})),
            reply("end_turn", text(final_text)),
        ],
    )


# --- memory ------------------------------------------------------------------

def test_memory_persists_across_turns_and_conversation_objects():
    client = FakeClient(
        router=[route("order_status")],
        model=[reply("end_turn", text("What's the order number?")),
               reply("end_turn", text("And the email?"))],
    )
    graph = build_graph(client)
    Conversation(graph=graph, thread_id="t-1").send("where's my order?")
    # A new Conversation object on the same thread picks up where it left off.
    state = Conversation(graph=graph, thread_id="t-1").send("ORD-1004")

    assert state["intent"] == "order_status"
    assert [m["content"] for m in state["messages"] if m["role"] == "user"] == \
        ["where's my order?", "ORD-1004"]
    assert len(client.router_requests) == 1


def test_threads_are_isolated():
    client = FakeClient(router=[route("faq"), route("refund")],
                        model=[reply("end_turn", text("a")), reply("end_turn", text("b"))])
    graph = build_graph(client)
    Conversation(graph=graph, thread_id="a").send("shipping?")
    state = Conversation(graph=graph, thread_id="b").send("return please")
    assert state["intent"] == "refund"
    assert len([m for m in state["messages"] if m["role"] == "user"]) == 1


def test_checkpointed_state_is_plain_json():
    convo = Conversation(refund_1002_script("Done."))
    convo.send("Return ORD-1002, jane@email.com, arrived damaged")
    json.dumps(convo.state)  # PostgresSaver-ready: no SDK objects in state


# --- refunds execute automatically -------------------------------------------

def test_large_refund_completes_in_one_turn_without_human_step():
    convo = Conversation(refund_1002_script("Done - $89.00 refunded."))
    state = convo.send("Return ORD-1002, jane@email.com, arrived damaged")

    assert state["reply"] == "Done - $89.00 refunded."
    assert state["tool_calls"][-1]["result"]["status"] == "refunded"
    assert store.get_order("ORD-1002")["status"] == "return_initiated"
    assert convo.graph.get_state(convo._config).next == ()  # not paused


# --- escalation --------------------------------------------------------------

def test_escalate_to_human_opens_ticket():
    result = escalate_to_human("ord-1003", "Wants a refund outside the window.")
    assert result == {"status": "escalated", "ticket_id": "ESC-0001"}
    assert store.all_escalations()["ESC-0001"]["order_id"] == "ORD-1003"


def test_escalate_with_unknown_order_still_opens_ticket():
    result = escalate_to_human("ORD-9999", "Asked for a person.")
    assert result["status"] == "escalated"
    ticket = store.all_escalations()[result["ticket_id"]]
    assert ticket["order_id"] is None and "ORD-9999" in ticket["summary"]


def test_escalate_requires_summary_and_allows_no_order():
    assert escalate_to_human("", "  ")["status"] == "error"
    assert escalate_to_human("", "Asked for a person.")["status"] == "escalated"


def test_skills_can_escalate_but_clarify_cannot():
    from app.agent.registry import SKILL_TOOLS
    for skill in ("order_status", "refund", "faq"):
        assert "escalate_to_human" in SKILL_TOOLS[skill]
    assert SKILL_TOOLS["clarify"] == frozenset()
