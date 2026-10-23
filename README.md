# Bookly Support Agent

An AI customer-support agent for **Bookly**, a fictional online bookstore. It
answers **order-status** questions, processes **returns/refunds**, and handles
**general policy** questions (shipping, returns, password reset).

Built **without** an all-in-one agent platform, so the mechanics are visible: the
orchestration graph, tool schemas, intent routing, and deterministic guardrails
are all code you can read and run.

> **Core idea — "LLM proposes, code disposes."** The model owns the conversation
> and intent; deterministic code enforces anything consequential (identity
> verification, refund eligibility). The prompt is advisory; the code is binding.

## Live demo (zero setup)

- **Storefront + chat widget:** https://bookly-web-theta.vercel.app
- **Agent API health check:** https://bookly-support-agent-zpbb.onrender.com/health

The agent runs on a free tier that sleeps when idle — the first message may take
~30s to wake it, then it's fast.

## Architecture at a glance

- **Storefront** — Next.js on Vercel (`bookly-web/`): book catalog + a floating
  support chat widget.
- **Agent** — FastAPI + LangGraph on Render (`bookly-agent/`): a router
  classifies intent, then hands off to a scoped **skill** (order status / refund /
  FAQ / clarify); each skill calls **tools** whose side effects pass through
  **deterministic guards**.
- **Data** — Supabase (Postgres). The agent also ships with a **seeded in-memory
  mock store**, so you can run it with no database at all.
- **Model** — Claude (Anthropic).

## Run the agent locally (mock data — no database required)

```bash
cd bookly-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Option 1 — run the tests (no API key, no cloud, no env vars)

The deterministic core and the agent logic run fully offline against a scripted
fake model and seeded in-memory data:

```bash
pytest -v
```

Each test name reads as a business rule the agent can never violate — they are
the guardrails, provable without any LLM.

### Option 2 — chat offline with no API key (`--mock`)

A scripted stand-in plays the model, **calls the real tools**, and runs the
**real deterministic guards** on the mock data. It handles the documented demo
scenarios (order status, refund, FAQ, clarifying questions, the identity check,
and topic switches); it won't improvise on off-script input — for open-ended
chat use a real key (Option 3) or the hosted demo.

```bash
python -m app.cli --mock            # no key required
python -m app.cli --mock --trace    # also prints routing + tool calls
```

### Option 3 — chat with the real model (seeded mock data, one key)

For genuine open-ended conversation, add an **Anthropic API key** (as any LLM app
needs). Still uses the seeded in-memory store **by default — no Supabase needed.**

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # or put it in bookly-agent/.env
# BOOKLY_DATA defaults to "mock" — leave it unset for offline seed data
python -m app.cli            # chat in the terminal
python -m app.cli --trace    # also prints routing decisions + tool calls
```

#### Things to try (against the seeded mock orders)

| Say this | What it demonstrates |
|---|---|
| `Where is my order ORD-1004? email carlos@email.com` | grounded order status (shipped) |
| `I want to return ORD-1001, jane@email.com — didn't like it` | multi-turn collection + refund action |
| `I need help with something` | asks a clarifying question (won't guess) |
| `How long does shipping take?` | grounded FAQ answer |
| `Status of ORD-1004? email jane@email.com` | identity guard — reveals nothing (wrong email) |

Seeded customers: `jane@email.com`, `carlos@email.com`. Orders: `ORD-1001`–`ORD-1005`.

## Run the storefront locally (optional)

```bash
cd bookly-web
npm install
# set NEXT_PUBLIC_AGENT_URL + Supabase keys in .env.local
npm run dev     # http://localhost:3000
```

## Repo layout

```
bookly-agent/   FastAPI + LangGraph agent (Python)
bookly-web/     Next.js storefront (TypeScript)
```
