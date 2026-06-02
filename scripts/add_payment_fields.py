"""Migration script — add payment fields to external_orders table.

Usage:
    python scripts/add_payment_fields.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, init_db
from sqlalchemy import text


async def migrate():
    await init_db()
    async with engine.connect() as conn:
        # Check if columns already exist
        result = await conn.execute(
            text("PRAGMA table_info(external_orders)")
        )
        columns = {row[1] for row in result.fetchall()}

        if "payment_status" not in columns:
            await conn.execute(
                text("ALTER TABLE external_orders ADD COLUMN payment_status VARCHAR(50) NOT NULL DEFAULT 'pending'")
            )
            print("✅ Added payment_status column")
        else:
            print("⏭️  payment_status already exists")

        if "stripe_session_id" not in columns:
            await conn.execute(
                text("ALTER TABLE external_orders ADD COLUMN stripe_session_id VARCHAR(255)")
            )
            print("✅ Added stripe_session_id column")
        else:
            print("⏭️  stripe_session_id already exists")

        if "amount_paid" not in columns:
            await conn.execute(
                text("ALTER TABLE external_orders ADD COLUMN amount_paid FLOAT")
            )
            print("✅ Added amount_paid column")
        else:
            print("⏭️  amount_paid already exists")

        await conn.commit()
        print("\nMigration complete! All payment fields added.")


if __name__ == "__main__":
    asyncio.run(migrate())
