"""
The LangGraph graph: router + skills + memory.

LangGraph is the plumbing, not the brain. Each node is a plain function that
takes the state and returns updates; the edges below are the whole routing
policy, readable in one screen:

    START -> ingest --(intent locked?)--> <skill>
                    \\--(no)--> classify_intent --(confident?)--> <skill>
                                              \\--(no / unclear)--> clarify
    <skill> --(switch_topic?)--> <other skill>
            \\--> END

Routing policy (AGENT_DESIGN.md §4): classify ONCE per thread. The first
confident classification locks the thread's skill; the router doesn't run
again. If the customer changes topic, the active skill hands off with
switch_topic (bounded by MAX_REROUTES_PER_TURN). "unclear" or low confidence
never locks - the clarify node asks, and the router runs again next turn.

Memory: a checkpointer saves the whole state after every step, keyed by
thread_id. One graph invocation = one customer turn. State holds only plain
JSON-able data, so the in-memory saver can become PostgresSaver unchanged.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app import config
from app.agent import registry
from app.agent.loop import run_tool_loop
from app.agent.prompts import SKILL_PROMPTS
from app.agent.router import classify_intent

SKILLS = ["order_status", "refund", "faq", "clarify"]


class AgentState(TypedDict, total=False):
    # Persist across turns
    messages: list[dict]        # the transcript, append-only
    intent: str | None          # locked skill for this thread, or None
    active_skill: str | None    # skill whose system message is in effect
    # Per turn
    user_input: str
    reply: str
    route: dict | None          # {"intent", "confidence"} (None if skipped)
    tool_calls: list[dict]
    reroute_to: str | None
    reroutes: int
    checkpoint: dict            # state at turn start, for rollback


def build_graph(client: Any, checkpointer: Any | None = None):
    """Compile the graph. `client` is an anthropic.Anthropic (or a test fake)."""

    def ingest(state: AgentState) -> dict:
        messages = list(state.get("messages", []))
        checkpoint = {"length": len(messages),
                      "intent": state.get("intent"),
                      "active_skill": state.get("active_skill")}
        messages.append({"role": "user", "content": state["user_input"]})
        return {"messages": messages, "checkpoint": checkpoint, "route": None,
                "tool_calls": [], "reroute_to": None, "reroutes": 0,
                "reply": ""}

    def classify(state: AgentState) -> dict:
        route = classify_intent(client, state["messages"])
        confident = (route.intent != "unclear" and
                     route.confidence >= config.ROUTER_CONFIDENCE_THRESHOLD)
        return {"route": asdict(route),
                "intent": route.intent if confident else None}

    def make_skill(name: str):
        def skill(state: AgentState) -> dict:
            messages = list(state["messages"])
            if state.get("active_skill") != name:
                # Scoped instructions arrive as an appended system message,
                # keeping the transcript append-only.
                messages.append({"role": "system", "content": SKILL_PROMPTS[name]})

            allowed = registry.SKILL_TOOLS[name]
            if state.get("reroutes", 0) >= config.MAX_REROUTES_PER_TURN:
                allowed = allowed - {"switch_topic"}

            # Live events for streaming callers; a no-op under plain invoke().
            emit = get_stream_writer()
            result = run_tool_loop(client, messages, skill=name, allowed=allowed,
                                   emit=emit)
            calls = state.get("tool_calls", []) + [asdict(c) for c in result.tool_calls]

            if not result.ok:
                # Roll the whole turn back: no half-finished exchange survives.
                cp = state["checkpoint"]
                return {"messages": messages[:cp["length"]],
                        "intent": cp["intent"], "active_skill": cp["active_skill"],
                        "reply": result.reply, "tool_calls": calls,
                        "reroute_to": None}

            update = {"messages": messages, "active_skill": name,
                      "reply": result.reply, "tool_calls": calls,
                      "reroute_to": result.reroute_to}
            if result.reroute_to:
                update["intent"] = result.reroute_to
                update["reroutes"] = state.get("reroutes", 0) + 1
            return update
        return skill

    def after_ingest(state: AgentState) -> str:
        return state["intent"] if state.get("intent") else "classify_intent"

    def after_classify(state: AgentState) -> str:
        return state["intent"] or "clarify"

    def after_skill(state: AgentState) -> str:
        return state.get("reroute_to") or END

    g = StateGraph(AgentState)
    g.add_node("ingest", ingest)
    g.add_node("classify_intent", classify)
    for name in SKILLS:
        g.add_node(name, make_skill(name))

    g.add_edge(START, "ingest")
    g.add_conditional_edges("ingest", after_ingest,
                            ["classify_intent", *SKILLS])
    g.add_conditional_edges("classify_intent", after_classify, SKILLS)
    for name in SKILLS:
        g.add_conditional_edges(name, after_skill, [*SKILLS, END])
    return g.compile(checkpointer=checkpointer or InMemorySaver())


class Conversation:
    """One customer conversation (a LangGraph thread)."""

    def __init__(self, client: Any | None = None, thread_id: str | None = None,
                 graph: Any | None = None):
        if graph is None:
            if client is None:
                import anthropic
                client = anthropic.Anthropic()
            graph = build_graph(client)
        self.graph = graph
        self.thread_id = thread_id or str(uuid.uuid4())
        self._config = {"configurable": {"thread_id": self.thread_id}}

    @property
    def state(self) -> AgentState:
        return self.graph.get_state(self._config).values

    def send(self, text: str) -> AgentState:
        return self.graph.invoke({"user_input": text}, self._config)
