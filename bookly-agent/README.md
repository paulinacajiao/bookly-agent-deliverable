# Bookly Support Agent

A customer-support agent for *Bookly*, a fictional online bookstore. Handles
order-status questions, return/refund requests, and general policy questions.

Built **without** an all-in-one agent platform so the mechanics are visible:
the orchestration loop, the tool schemas, the routing, and the guardrails are
all code you can read and test.

## Core idea

> **LLM proposes, code disposes.** The model owns the conversation and the
> intent. Every consequential decision - identity, refund eligibility, money -
> is enforced by deterministic code the model cannot talk its way around.

## Build phases (each is human-tested before the next starts)

| Phase | What | New dependency |
|-------|------|----------------|
| 1. Deterministic core ✅ | Mock data + tools + refund/identity guards | none |
| 2. Model connection ✅ | Minimal agent loop, system prompt | `ANTHROPIC_API_KEY` |
| 3. Router + skills ✅ | `classify_intent` + refund/order/faq/clarify nodes (LangGraph) | — |
| 4. Memory + escalation ✅ | Checkpointer + escalate_to_human | — |
| 5. Real data ✅ | Swap mock store → Supabase | `SUPABASE_URL/KEY` |
| **6. API** ← *you are here* | FastAPI `/chat` | — |
| 7. Deploy | Next.js storefront + hosted agent | Vercel + Render |
| 8. Polish | Observability + demo script | optional |

## Project layout

```
app/
  config.py              model, effort, thresholds, loop limits - one place
  main.py                FastAPI: /health, /chat (JSON), /chat/stream (SSE)
  cli.py                 interactive chat (python -m app.cli --trace)
  agent/
    graph.py             LangGraph: ingest -> router -> skill -> (handoff) ->
                         end; checkpointer memory
    router.py            classify_intent: closed-set intent + confidence
    loop.py              the tool loop each skill runs (model <-> tools)
    registry.py          tool schemas + dispatcher + per-skill tool scope
    prompts.py           global prompt + per-skill prompts + router prompt
  data/
    store.py             picks the backend: BOOKLY_DATA=mock | supabase
    supabase_store.py    real Postgres (same functions as the mock)
    mock_store.py     in-memory "database" (replaced by Supabase in Phase 5)
  tools/
    policies.py          business rules (return window, $ limit) in ONE place
    orders.py            lookup_order, get_order_status (identity-gated)
    refunds.py           check_refund_eligibility, create_return (the guards)
    knowledge.py         search_policies (mock FAQ, becomes RAG later)
    escalation.py        escalate_to_human (ticket for a specialist)
supabase/
  001_agent_phase5.sql   escalations, id sequences, reset_demo() (agent's additions
                         on top of bookly-web/supabase/schema.sql)
tests/
  test_refund_guards.py  one test per business rule = the spec
  test_orders.py         lookup / status / knowledge
  test_agent_loop.py     tool loop mechanics (fake model, offline)
  test_graph.py          routing policy + append-only history (offline)
  test_memory_and_escalation.py  memory, auto-refund, escalation (offline)
  test_api.py            HTTP contract, SSE events, CORS (offline)
```

## Run Phase 1 (no API keys needed)

```bash
cd bookly-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

All tests should pass. Each test name states a business rule the agent can
never violate - read them as the agent's operating procedure. The agent-loop
tests use a scripted fake model, so they also need no API key.

## Use the real database (Phase 5)

Add to `.env`: `BOOKLY_DATA=supabase` and `SUPABASE_SERVICE_ROLE_KEY` (Supabase
→ Project Settings → API keys → service_role / secret key; server-side only).

```bash
BOOKLY_DATA=supabase pytest -q          # the same suite against Postgres
python -c "from app.data import store; store.reset()"   # restore demo data
```

`pytest` without the variable always uses the in-memory store.

## Run the API (Phase 6)

```bash
uvicorn app.main:app --reload --port 8000
curl localhost:8000/chat -H 'Content-Type: application/json' \
     -d '{"message": "Where is ORD-1004? carlos@email.com"}'
curl -N localhost:8000/chat/stream -H 'Content-Type: application/json' \
     -d '{"message": "How long does shipping take?"}'
```

The storefront widget posts to `/chat` (or `/chat/stream`) with a
`conversation_id` per browser session. Allowed browser origins come from
`ALLOWED_ORIGINS` (default `http://localhost:3000`).

## Talk to the agent

```bash
cp .env.example .env          # then paste your key after ANTHROPIC_API_KEY=
python -m app.cli --trace     # --trace shows each tool call and its raw result
```

Things to try (the trace shows the router's decision and every tool call):

| Say | What it shows |
|---|---|
| `I need help with my thing` | low confidence → asks a clarifying question |
| `I want to return a book` → `ORD-1001, jane@email.com` → `didn't like it` | multi-turn collection, then a refund via tool |
| `Return ORD-1002, jane@email.com, arrived damaged` | larger multi-item order → refunded automatically |
| `Refund ORD-1003, carlos@email.com` | outside the return window → refused by code |
| `Where's ORD-1004? carlos@email.com` → `I want to return it` | order status, then hand-off to the refund skill |
| `How long does shipping take?` | policy answer grounded in search_policies |
| `Can I talk to a real person?` | escalate_to_human opens a ticket with a summary |
