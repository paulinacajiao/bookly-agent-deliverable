"""
Graph tests - routing policy and the required capabilities, offline.

  * low confidence / unclear -> clarify asks instead of answering
  * classify once per thread: a confident route locks the skill
  * switch_topic hands off mid-turn
  * the transcript is append-only and system/tools never change
    (Claude Sonnet 5.5 rejects edited histories)
"""

import pytest

from app import config
from app.agent.graph import Conversation
from app.agent.loop import REFUSAL_REPLY
from app.agent.prompts import SKILL_PROMPTS
from app.data import store
from tests.fakes import FakeClient, reply, route, text, tool_use


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()


def system_messages(messages):
    return [m["content"] for m in messages if m["role"] == "system"]


def test_unclear_request_goes_to_clarify_and_does_not_lock():
    client = FakeClient(router=[route("unclear", 0.4)],
                        model=[reply("end_turn", text("Is this about an order, a return, or something else?"))])
    convo = Conversation(client)
    state = convo.send("I need help with my thing")

    assert state["intent"] is None
    assert system_messages(state["messages"]) == [SKILL_PROMPTS["clarify"]]
    assert state["tool_calls"] == []


def test_low_confidence_known_intent_still_clarifies():
    client = FakeClient(router=[route("refund", config.ROUTER_CONFIDENCE_THRESHOLD - 0.1)],
                        model=[reply("end_turn", text("Do you want to return something?"))])
    state = Conversation(client).send("this book thing")
    assert state["intent"] is None
    assert system_messages(state["messages"]) == [SKILL_PROMPTS["clarify"]]


def test_router_runs_until_confident_then_thread_is_locked():
    client = FakeClient(
        router=[route("unclear", 0.3), route("refund")],
        model=[reply("end_turn", text("What can I help with?")),
               reply("end_turn", text("Sure - what's the order number and email?")),
               reply("end_turn", text("And the reason?"))],
    )
    convo = Conversation(client)
    convo.send("hi")
    convo.send("I want to return a book")
    state = convo.send("ORD-1001, jane@email.com")

    assert len(client.router_requests) == 2      # not called on turn 3
    assert state["intent"] == "refund"
    assert state["route"] is None
    # refund instructions appended exactly once
    assert system_messages(state["messages"]).count(SKILL_PROMPTS["refund"]) == 1


def test_full_refund_flow_issues_refund_via_tool():
    client = FakeClient(
        router=[route("refund")],
        model=[
            reply("tool_use", tool_use("check_refund_eligibility",
                                       {"order_id": "ORD-1001", "email": "jane@email.com"})),
            reply("tool_use", tool_use("create_return",
                                       {"order_id": "ORD-1001", "email": "jane@email.com",
                                        "reason": "didn't like it"}, id_="tu_2")),
            reply("end_turn", text("Done - $24 refunded.")),
        ],
    )
    state = Conversation(client).send(
        "Return ORD-1001, jane@email.com, didn't like it")
    assert [c["name"] for c in state["tool_calls"]] == ["check_refund_eligibility",
                                                        "create_return"]
    assert state["tool_calls"][-1]["result"]["status"] == "refunded"
    assert store.get_order("ORD-1001")["status"] == "return_initiated"


def test_switch_topic_hands_off_within_the_same_turn():
    client = FakeClient(
        router=[route("order_status")],
        model=[reply("tool_use", tool_use("switch_topic", {"topic": "refund"})),
               reply("end_turn", text("I can help with that return."))],
    )
    state = Conversation(client).send("Actually I want to return my order")

    assert state["intent"] == "refund" and state["active_skill"] == "refund"
    assert state["reply"] == "I can help with that return."
    # refund instructions follow the tool_result (a user message) - valid placement
    msgs = state["messages"]
    idx = next(i for i, m in enumerate(msgs) if m.get("content") == SKILL_PROMPTS["refund"])
    assert msgs[idx - 1]["role"] == "user"


def test_reroute_is_bounded_per_turn():
    client = FakeClient(
        router=[route("order_status")],
        model=[reply("tool_use", tool_use("switch_topic", {"topic": "refund"})),
               reply("tool_use", tool_use("switch_topic", {"topic": "order_status"}, id_="tu_2")),
               reply("end_turn", text("Let's sort out your return here."))],
    )
    state = Conversation(client).send("return? or status? both?")
    second = state["tool_calls"][-1]
    assert second["name"] == "switch_topic" and second["is_error"]
    assert state["active_skill"] == "refund"


def test_failed_turn_rolls_back_to_previous_state():
    client = FakeClient(
        router=[route("faq")],
        model=[reply("end_turn", text("Shipping is 3-5 business days.")),
               reply("refusal")],
    )
    convo = Conversation(client)
    before = convo.send("how long is shipping?")
    kept = list(before["messages"])
    state = convo.send("something off-limits")

    assert state["reply"] == REFUSAL_REPLY
    assert state["messages"] == kept
    assert state["intent"] == "faq"


def test_history_is_append_only_and_system_tools_frozen():
    client = FakeClient(
        router=[route("unclear", 0.2), route("order_status")],
        model=[
            reply("end_turn", text("How can I help?")),
            reply("tool_use", tool_use("get_order_status",
                                       {"order_id": "ORD-1004", "email": "carlos@email.com"})),
            reply("tool_use", tool_use("switch_topic", {"topic": "refund"}, id_="tu_2")),
            reply("end_turn", text("Let's start your return.")),
        ],
    )
    convo = Conversation(client)
    convo.send("hello")
    convo.send("where is ORD-1004, carlos@email.com? I might return it")

    reqs = client.model_requests
    assert len(reqs) == 4
    for prev, cur in zip(reqs, reqs[1:]):
        assert cur["system"] == prev["system"]
        assert cur["tools"] == prev["tools"]
        assert cur["messages"][:len(prev["messages"])] == prev["messages"]
