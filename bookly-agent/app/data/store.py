"""
The data store the tools use - picks a backend once, at import.

    BOOKLY_DATA=mock      in-memory seed data (default; tests, offline dev)
    BOOKLY_DATA=supabase  the real Postgres database

Both backends expose the same functions (get_order, save_return, ...), so
nothing above this line knows or cares which one is running.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BACKEND = os.getenv("BOOKLY_DATA", "mock").strip().lower()

if BACKEND == "supabase":
    from app.data.supabase_store import *  # noqa: F401,F403
elif BACKEND == "mock":
    from app.data.mock_store import *  # noqa: F401,F403
else:
    raise RuntimeError(f"BOOKLY_DATA must be 'mock' or 'supabase', not {BACKEND!r}")
