"""
HTTP API tests - offline, through FastAPI's TestClient with a fake model.

  * /chat keeps the storefront widget's contract: {reply, conversation_id}
  * a conversation_id threads memory across requests
  * /chat/stream emits status -> token -> done, and done carries the reply
  * CORS allows the storefront origin only
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.data import store
from app.main import create_app
from tests.fakes import FakeClient, reply, route, text, tool_use


@pytest.fixture(autouse=True)
def fresh_store():
    store.reset()


def api(client):
    return TestClient(create_app(client))


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for chunk in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in chunk.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_health():
    r = api(FakeClient()).get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_chat_matches_widget_contract_and_assigns_id():
    c = api(FakeClient(router=[route("faq")],
                       model=[reply("end_turn", text("Shipping takes **3-5** days."))]))
    r = c.post("/chat", json={"message": "how long is shipping?"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "Shipping takes **3-5** days."
    assert body["conversation_id"]


def test_conversation_id_threads_memory():
    fake = FakeClient(router=[route("order_status")],
                      model=[reply("end_turn", text("Order number?")),
                             reply("end_turn", text("And the email?"))])
    c = api(fake)
    c.post("/chat", json={"message": "where's my order?", "conversation_id": "abc"})
    c.post("/chat", json={"message": "ORD-1004", "conversation_id": "abc"})
    second = fake.model_requests[1]["messages"]
    users = [m["content"] for m in second if m["role"] == "user"]
    assert users == ["where's my order?", "ORD-1004"]
    assert len(fake.router_requests) == 1  # thread remembered its intent


def test_stream_emits_status_tokens_and_done():
    fake = FakeClient(
        router=[route("order_status")],
        model=[reply("tool_use", text("Let me check."),
                     tool_use("get_order_status",
                              {"order_id": "ORD-1004", "email": "carlos@email.com"})),
               reply("end_turn", text("It has **shipped**."))],
    )
    r = api(fake).post("/chat/stream", json={"message": "ORD-1004, carlos@email.com",
                                             "conversation_id": "s1"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    kinds = [e for e, _ in events]
    # pre-tool chatter streams, then a status line clears it, then the answer
    assert kinds == ["token", "status", "token", "done"]
    assert events[1][1]["label"] == "Looking up your order…"
    assert events[-1][1] == {"reply": "It has **shipped**.", "conversation_id": "s1"}


def test_stream_reports_failure_in_band():
    class Boom(FakeClient):
        def _create(self, **kwargs):
            raise RuntimeError("down")
    events = parse_sse(api(Boom()).post("/chat/stream", json={"message": "hi"}).text)
    assert events[-1][0] == "error"


def test_empty_message_rejected():
    assert api(FakeClient()).post("/chat", json={"message": ""}).status_code == 422


def test_cors_allows_storefront_origin_only():
    c = api(FakeClient())
    ok = c.options("/chat", headers={"Origin": "http://localhost:3000",
                                     "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = c.options("/chat", headers={"Origin": "https://evil.example",
                                      "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
