"""
Runtime configuration: which model, how hard it thinks, and the loop's limits.

Model choice is a deliberate, reviewed decision (see AGENT_DESIGN.md §3) - it
lives here, in one place, and is never changed silently.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load ANTHROPIC_API_KEY (and later SUPABASE_*) from bookly-agent/.env.
load_dotenv()

# Workhorse model for every conversational turn.
MODEL = "claude-sonnet-5-5"

# Reserved for the hardest reasoning (not used yet).
REASONING_MODEL = "claude-opus-5-5"

# Intent router: a one-shot classification, so low effort is enough.
ROUTER_MODEL = MODEL
ROUTER_EFFORT = "low"

# Below this router confidence, the agent asks a clarifying question instead
# of guessing which skill to run. Code decides, not the model.
ROUTER_CONFIDENCE_THRESHOLD = 0.7

# How many times one customer turn may hand off between skills (switch_topic).
# Stops two skills from bouncing the conversation back and forth.
MAX_REROUTES_PER_TURN = 1

# Thinking depth. Support turns are short tool-use exchanges; "medium" is the
# recommended starting point for multistep tool use on Sonnet 5.5.
EFFORT = "medium"

MAX_TOKENS = 16000

# Hard ceiling on model<->tool round trips within ONE customer turn. A runaway
# loop is a cost and safety problem; code bounds it, not the model.
MAX_TOOL_ROUNDS = 6


def require_api_key() -> None:
    """Fail fast with a readable message instead of a stack trace."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
            "your key (see README)."
        )
