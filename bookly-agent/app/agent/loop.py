"""
The tool loop - the engine inside every skill.

    model thinks -> maybe requests a tool -> OUR code runs it -> model sees the
    result -> thinks again -> eventually answers.

LangGraph (app/agent/graph.py) decides WHICH skill runs; this loop is what a
skill does once it has the floor. It is plain code on purpose, so the
mechanics stay visible.

Memory is just the `messages` list: the model is stateless, so every call
re-sends the full transcript. The loop only ever APPENDS to it, and appends the
assistant's content exactly as returned (including thinking blocks) - Claude
Sonnet 5.5 rejects a transcript whose earlier turns were edited. Blocks are
stored as plain dicts so the transcript can be checkpointed (Phase 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app import config
from app.agent import registry
from app.agent.prompts import GLOBAL_PROMPT

# Server-side refusal fallback: if a safety classifier declines a request, the
# API re-runs it on Anthropic's recommended fallback model inside the same call.
BETAS = ["server-side-fallback-2026-07-01"]

REFUSAL_REPLY = (
    "Sorry, I can't help with that one. I can help with order status, returns "
    "and refunds, or questions about Bookly's policies."
)
STUCK_REPLY = (
    "Sorry, I wasn't able to finish that. Could you rephrase, or would you "
    "like me to connect you with a human specialist?"
)


@dataclass
class ToolCall:
    """One tool invocation, recorded for the CLI trace and for tests."""
    skill: str
    name: str
    args: dict[str, Any]
    result: dict
    is_error: bool


@dataclass
class LoopResult:
    reply: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    ok: bool = True                 # False -> the caller rolls the turn back
    reroute_to: str | None = None   # set when the model called switch_topic


def _as_param(block: Any) -> dict:
    """SDK content block -> plain dict, unchanged in substance (thinking
    blocks keep their signature), so it can be checkpointed and re-sent."""
    if isinstance(block, dict):
        return block
    return block.to_dict(mode="json", exclude_none=True)


Emit = Callable[[dict], None]


def _no_emit(_: dict) -> None:
    pass


def call_model(client: Any, messages: list[dict], emit: Emit = _no_emit):
    """One request to the conversation model. system + tools never vary.

    Always streamed: text is forwarded to `emit` as it arrives (the web chat
    shows it live; the CLI ignores it), and the complete message is returned.
    Tools deliberately don't set eager_input_streaming: their inputs are a few
    short strings, and leaving it off keeps strict-mode schema validation and
    an identical tool list for every request.
    """
    with client.beta.messages.stream(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=GLOBAL_PROMPT,
        tools=registry.TOOL_SCHEMAS,
        messages=messages,
        output_config={"effort": config.EFFORT},
        betas=BETAS,
        fallbacks="default",
    ) as stream:
        for text in stream.text_stream:
            emit({"type": "token", "text": text})
        return stream.get_final_message()


def run_tool_loop(client: Any, messages: list[dict], *, skill: str,
                  allowed: frozenset[str], emit: Emit = _no_emit) -> LoopResult:
    """Run the model until it answers, hands off, or code stops it.

    Appends to `messages` in place. On ok=False the caller is responsible for
    truncating the turn (it knows where the turn started).

    `emit` receives live events for streaming UIs:
      {"type": "token", "text"}    model text as it's written
      {"type": "status", "label"}  a tool is running; discard streamed text
                                   (pre-tool chatter isn't part of the reply)
    """
    calls: list[ToolCall] = []

    for _ in range(config.MAX_TOOL_ROUNDS):
        response = call_model(client, messages, emit)

        if response.stop_reason == "refusal":
            return LoopResult(REFUSAL_REPLY, calls, "refusal", ok=False)

        messages.append({"role": "assistant",
                         "content": [_as_param(b) for b in response.content]})

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content
                           if b.type == "text").strip()
            if not text:  # e.g. max_tokens hit before any answer
                return LoopResult(STUCK_REPLY, calls, response.stop_reason, ok=False)
            return LoopResult(text, calls, response.stop_reason)

        # The model REQUESTED tools; our code decides and executes.
        # All results go back in ONE user message.
        results, reroute_to = [], None
        for block in response.content:
            if block.type != "tool_use":
                continue
            emit({"type": "status", "label": registry.STATUS_LABELS.get(
                block.name, "Working on it…")})
            args = dict(block.input)
            if block.name == "switch_topic" and args.get("topic") == skill:
                result, is_error = {"status": "error",
                                    "error": f"already handling {skill}"}, True
            else:
                result, is_error = registry.dispatch(block.name, args, allowed)
            if block.name == "switch_topic" and not is_error:
                reroute_to = args["topic"]
            calls.append(ToolCall(skill, block.name, args, result, is_error))
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": registry.to_content(result),
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": results})

        if reroute_to:
            return LoopResult("", calls, "reroute", reroute_to=reroute_to)

    # Round cap hit: code stops the loop, not the model.
    return LoopResult(STUCK_REPLY, calls, "max_tool_rounds", ok=False)
