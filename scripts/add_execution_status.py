"""Migration script: add execution_status + deploy_dir columns to external_orders."""

import sqlite3
import sys

DB_PATH = "polsia.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("PRAGMA table_info(external_orders)")
    columns = {row[1] for row in cursor.fetchall()}

    if "execution_status" not in columns:
        conn.execute("ALTER TABLE external_orders ADD COLUMN execution_status VARCHAR(50) DEFAULT 'pending'")
        print("+ Added execution_status column")
    else:
        print("= execution_status already exists")

    if "deploy_dir" not in columns:
        conn.execute("ALTER TABLE external_orders ADD COLUMN deploy_dir VARCHAR(500)")
        print("+ Added deploy_dir column")
    else:
        print("= deploy_dir already exists")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
