"""Migration: add customer_email column to external_orders + backfill from requirements."""
import asyncio
import re
import sys
sys.path.insert(0, ".")

from sqlalchemy import text
from app.core.database import async_session


async def migrate():
    async with async_session() as db:
        # Check if column already exists
        result = await db.execute(
            text("PRAGMA table_info(external_orders)")
        )
        cols = {row[1] for row in result.fetchall()}
        if "customer_email" not in cols:
            await db.execute(
                text("ALTER TABLE external_orders ADD COLUMN customer_email VARCHAR(255)")
            )
            print("✅ Added customer_email column")
        else:
            print("ℹ️  customer_email column already exists")

        # Backfill from requirements: extract email from "Client: Name <email>"
        rows = await db.execute(
            text("SELECT id, requirements FROM external_orders "
                 "WHERE customer_email IS NULL AND requirements IS NOT NULL")
        )
        updated = 0
        for row in rows.fetchall():
            match = re.search(r"<([^>]+@[^>]+)>", row[1] or "")
            if match:
                email = match.group(1)
                await db.execute(
                    text("UPDATE external_orders SET customer_email = :email WHERE id = :id"),
                    {"email": email, "id": row[0]},
                )
                updated += 1

        await db.commit()
        print(f"✅ Backfilled {updated} orders with customer_email from requirements")
        print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
