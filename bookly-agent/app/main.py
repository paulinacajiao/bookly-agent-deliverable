"""
HTTP API for the Bookly support agent (FastAPI).

    uvicorn app.main:app --reload            # local
    GET  /health                             liveness (Render health check)
    POST /chat          {message, conversation_id?} -> {reply, conversation_id}
    POST /chat/stream   same body -> Server-Sent Events:
         event: token   {"text": "..."}       append to the bubble
         event: status  {"label": "..."}      a tool is running: clear the
                                              bubble, show the label
         event: done    {"reply", "conversation_id"}  authoritative final text
         event: error   {"message": "..."}

One conversation_id = one LangGraph thread (checkpointer memory). The browser
never sees the Anthropic or Supabase keys - they live only on this server.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections import defaultdict
from typing import Any, Iterator

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import config
from app.agent.graph import build_graph

FAILED_REPLY = ("Sorry, I'm having trouble right now. Please try again in a "
                "moment, or ask to talk to a person.")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def create_app(client: Any | None = None) -> FastAPI:
    """Build the app. Tests pass a fake client; production builds a real one
    lazily, on the first chat, so /health works even before keys are set."""
    app = FastAPI(title="Bookly support agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        # Vercel preview deployments get unique URLs; allow them by pattern.
        allow_origin_regex=os.getenv("ALLOWED_ORIGIN_REGEX") or None,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    graph_holder: dict[str, Any] = {}
    graph_init = threading.Lock()
    # One turn at a time per conversation: two concurrent turns on the same
    # thread would race on its checkpoint.
    thread_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)

    def graph():
        with graph_init:
            if "g" not in graph_holder:
                if client is None:
                    config.require_api_key()
                graph_holder["g"] = build_graph(client or anthropic.Anthropic())
            return graph_holder["g"]

    def run_config(conversation_id: str) -> dict:
        return {"configurable": {"thread_id": conversation_id}}

    def acquire(conversation_id: str) -> threading.Lock:
        lock = thread_locks[conversation_id]
        if not lock.acquire(blocking=False):
            raise HTTPException(409, "This conversation is already answering a message.")
        return lock

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": config.MODEL,
                "data": os.getenv("BOOKLY_DATA", "mock")}

    @app.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        cid = req.conversation_id or str(uuid.uuid4())
        lock = acquire(cid)
        try:
            state = graph().invoke({"user_input": req.message}, run_config(cid))
            return ChatResponse(reply=state["reply"], conversation_id=cid)
        except anthropic.APIError as exc:
            raise HTTPException(502, f"Model error: {type(exc).__name__}") from exc
        finally:
            lock.release()

    @app.post("/chat/stream")
    def chat_stream(req: ChatRequest) -> StreamingResponse:
        cid = req.conversation_id or str(uuid.uuid4())
        lock = acquire(cid)

        def events() -> Iterator[str]:
            try:
                final: dict = {}
                for mode, payload in graph().stream(
                        {"user_input": req.message}, run_config(cid),
                        stream_mode=["custom", "values"]):
                    if mode == "custom":
                        yield _sse(payload["type"], {k: v for k, v in payload.items()
                                                     if k != "type"})
                    else:
                        final = payload
                yield _sse("done", {"reply": final.get("reply") or FAILED_REPLY,
                                    "conversation_id": cid})
            except Exception as exc:  # stream already started: report in-band
                yield _sse("error", {"message": FAILED_REPLY,
                                     "detail": type(exc).__name__})
            finally:
                lock.release()

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    return app


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


app = create_app()
