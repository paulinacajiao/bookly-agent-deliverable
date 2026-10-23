"""
Tests run against the in-memory store by default (offline, fast).

    BOOKLY_DATA=supabase pytest     # same suite against the real database

Set before any app module loads; load_dotenv() never overrides it, so a
BOOKLY_DATA=supabase line in .env can't silently point tests at the database.
"""

import os

os.environ.setdefault("BOOKLY_DATA", "mock")
