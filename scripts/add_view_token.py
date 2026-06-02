#!/usr/bin/env python3
"""Migration script — add `view_token` column to the `proposals` table.

Can be run standalone:
    python scripts/add_view_token.py

Uses the same DATABASE_URL env var as the main app (defaults to SQLite).
"""

import os
import sys
import uuid

# Ensure the project root is on sys.path so we can import app config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text


def main():
    database_url = os.getenv(
        "DATABASE_URL", "sqlite:///./polsia.db"
    )
    # Convert async URL to sync for the migration script
    sync_url = database_url.replace("sqlite+aiosqlite://", "sqlite://")
    if sync_url == database_url:
        sync_url = database_url.replace("+asyncpg", "").replace("+aiosqlite", "")

    engine = create_engine(sync_url)

    with engine.begin() as conn:
        # Check if column already exists
        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM pragma_table_info('proposals') WHERE name='view_token'"
            )
        )
        exists = (result.scalar() or 0) > 0
        if exists:
            print("✓ Column 'view_token' already exists — nothing to do.")
        else:
            conn.execute(text("ALTER TABLE proposals ADD COLUMN view_token VARCHAR(32)"))
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_proposals_view_token "
                    "ON proposals(view_token)"
                )
            )
            print("✓ Added 'view_token' column to proposals table.")
            print("✓ Created unique index ix_proposals_view_token.")

        # Update existing rows without view_token
        rows = conn.execute(
            text("SELECT id FROM proposals WHERE view_token IS NULL OR view_token = ''")
        ).fetchall()

        if rows:
            print(f"  Updating {len(rows)} existing proposal(s) with view_token values...")
            for (pid,) in rows:
                token = uuid.uuid4().hex[:12]
                conn.execute(
                    text("UPDATE proposals SET view_token = :token WHERE id = :id"),
                    {"token": token, "id": pid},
                )
            print(f"  ✓ Updated {len(rows)} proposal(s).")
        else:
            print("  No existing proposals need view_token updates.")

    print("\n✓ Migration complete.")


if __name__ == "__main__":
    main()
