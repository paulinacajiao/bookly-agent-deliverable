"""
Interactive CLI for the Bookly support agent.

    python -m app.cli            # chat
    python -m app.cli --trace    # chat + show routing, tool calls and results

Type 'quit' (or Ctrl-D) to exit, 'reset' to start a new conversation.
"""

from __future__ import annotations

import argparse
import os
from functools import partial

import anthropic

from app import config
from app.agent.graph import Conversation

DIM, RESET = "\033[2m", "\033[0m"


def print_trace(state) -> None:
    route = state.get("route")
    if route:
        print(f"{DIM}  [router] {route['intent']} (confidence {route['confidence']:.2f})"
              f" -> {state.get('intent') or 'clarify'}{RESET}")
    else:
        locked = state["checkpoint"]["intent"]  # as of the start of this turn
        print(f"{DIM}  [router] skipped - thread locked to {locked}{RESET}")
    for call in state.get("tool_calls", []):
        print(f"{DIM}  [{call['skill']}] {call['name']}({call['args']}) -> {call['result']}{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the Bookly support agent.")
    parser.add_argument("--trace", action="store_true",
                        help="show routing decisions, tool calls and raw results")
    parser.add_argument("--mock", action="store_true",
                        help="run offline with a scripted fake model (no API key)")
    args = parser.parse_args()

    if args.mock:
        from app.mock_model import MockClient
        new_convo = partial(Conversation, client=MockClient())
        banner = "MOCK MODE - scripted replies, no API key"
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "No ANTHROPIC_API_KEY found.\n"
                "  - Offline demo (no key):  python -m app.cli --mock\n"
                "  - Hosted demo:            https://bookly-web-theta.vercel.app")
        config.require_api_key()
        new_convo = Conversation
        banner = config.MODEL

    convo = new_convo()
    print(f"Bookly support ({banner}). 'quit' to exit, 'reset' for a new chat.\n")

    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit"}:
            break
        if user.lower() == "reset":
            convo = new_convo()
            print("(new conversation)\n")
            continue

        try:
            state = convo.send(user)
        except anthropic.AuthenticationError:
            raise SystemExit("Invalid ANTHROPIC_API_KEY - check your .env.")
        except anthropic.APIConnectionError:
            print("bookly> (network error - check your connection and try again)\n")
            continue
        except anthropic.APIStatusError as exc:
            print(f"bookly> (API error {exc.status_code}: {exc.message})\n")
            continue

        if args.trace:
            print_trace(state)
        print(f"bookly> {state['reply']}\n")


if __name__ == "__main__":
    main()
