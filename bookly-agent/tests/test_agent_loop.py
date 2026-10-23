"""
Tool-loop tests - run OFFLINE with a scripted fake model (no API key).

These pin down the loop's mechanics, not the model's wording:
  * a tool the model requests is executed by our code, and its real result is
    fed back (the model never sees invented data),
  * code bounds the loop and enforces each skill's tool scope,
  * refusals and unknown tools degrade gracefully.
"""

import json

import pytest

from app import config
from app.agent.loop import REFUSAL_REPLY, STUCK_REPLY, run_tool_loop
from app.agent.registry import SKILL_TOOLS, dispatch
from app.data import store
from tests.fakes import FakeClient, reply, text, tool_use


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()


def run(client, skill="order_status", user="hi"):
    messages = [{"role": "user", "content": user}]
    result = run_tool_loop(client, messages, skill=skill,
                           allowed=SKILL_TOOLS[skill])
    return result, messages


def test_tool_request_is_executed_and_real_result_fed_back():
    client = FakeClient(model=[
        reply("tool_use", tool_use("get_order_status",
                                   {"order_id": "ORD-1004", "email": "carlos@email.com"})),
        reply("end_turn", text("Your order has shipped.")),
    ])
    result, _ = run(client)

    assert result.reply == "Your order has shipped."
    assert [c.name for c in result.tool_calls] == ["get_order_status"]
    # The second request carries the REAL tool output from store.
    tool_result = client.model_requests[1]["messages"][-1]["content"][0]
    payload = json.loads(tool_result["content"])
    assert payload["order_status"] == "shipped"
    assert payload["tracking"] == "1Z-CARL-1004"
    assert tool_result["tool_use_id"] == "tu_1"


def test_requests_use_configured_model_and_fallbacks():
    client = FakeClient(model=[reply("end_turn", text("Hi!"))])
    run(client)
    req = client.model_requests[0]
    assert req["model"] == config.MODEL
    assert req["fallbacks"] == "default"
    assert "tool_choice" not in req  # forced tool choice 400s on Sonnet 5.5


def test_identity_mismatch_reaches_model_without_order_details():
    client = FakeClient(model=[
        reply("tool_use", tool_use("get_order_status",
                                   {"order_id": "ORD-1004", "email": "jane@email.com"})),
        reply("end_turn", text("Those details don't match.")),
    ])
    result, _ = run(client)
    assert result.tool_calls[0].result == {"status": "identity_mismatch",
                                           "order_id": "ORD-1004"}


def test_skill_cannot_run_tools_outside_its_scope():
    # The order-status skill tries to issue a refund: code refuses, no money moves.
    client = FakeClient(model=[
        reply("tool_use", tool_use("create_return",
                                   {"order_id": "ORD-1001", "email": "jane@email.com",
                                    "reason": "x"})),
        reply("end_turn", text("I can't do that here.")),
    ])
    result, _ = run(client, skill="order_status")
    assert result.tool_calls[0].is_error
    assert "not available" in result.tool_calls[0].result["error"]
    assert store.all_returns() == {}


def test_switch_topic_stops_loop_and_requests_reroute():
    client = FakeClient(model=[
        reply("tool_use", tool_use("switch_topic", {"topic": "refund"})),
    ])
    result, messages = run(client, skill="order_status")
    assert result.ok and result.reroute_to == "refund"
    assert messages[-1]["role"] == "user"  # tool_result appended; valid to continue


def test_switch_to_current_topic_is_rejected():
    client = FakeClient(model=[
        reply("tool_use", tool_use("switch_topic", {"topic": "faq"})),
        reply("end_turn", text("Shipping takes 3-5 days.")),
    ])
    result, _ = run(client, skill="faq")
    assert result.reroute_to is None
    assert result.tool_calls[0].is_error


def test_refusal_returns_safe_reply_and_flags_rollback():
    result, _ = run(FakeClient(model=[reply("refusal")]))
    assert result.reply == REFUSAL_REPLY and not result.ok


def test_round_cap_stops_runaway_loop():
    looping = [reply("tool_use", tool_use("get_order_status",
                                          {"order_id": "ORD-1", "email": "x@y.z"}))
               for _ in range(config.MAX_TOOL_ROUNDS)]
    result, _ = run(FakeClient(model=looping))
    assert result.reply == STUCK_REPLY
    assert result.stop_reason == "max_tool_rounds" and not result.ok


def test_dispatch_rejects_unknown_tool_and_bad_args():
    result, is_error = dispatch("lookup_order", {"order_id": "ORD-1001"})
    assert is_error and "unknown tool" in result["error"]  # not model-facing
    result, is_error = dispatch("get_order_status", {"order_id": "ORD-1001"})
    assert is_error and "bad arguments" in result["error"]
