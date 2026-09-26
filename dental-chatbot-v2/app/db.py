from pathlib import Path

import psycopg

from app.config import DATABASE_DIR, DB_CONFIG


def get_connection():
    return psycopg.connect(**DB_CONFIG)


def ensure_schema() -> None:
    """
    Apply additive generic-runtime columns/tables if they are missing.
    Safe to call on every process start.
    """

    statements = [
        """
        ALTER TABLE chat_flows
            ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb
        """,
        """
        ALTER TABLE chat_nodes
            ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_session_values (
            session_id UUID NOT NULL,
            input_key VARCHAR(100) NOT NULL,
            value TEXT NOT NULL,
            label TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_chat_session_values
                PRIMARY KEY (session_id, input_key),
            CONSTRAINT fk_chat_session_values_session
                FOREIGN KEY (session_id)
                REFERENCES chat_sessions(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_chat_session_values_session
            ON chat_session_values (session_id)
        """,
        """
        ALTER TABLE order_details
            ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb
        """,
        """
        ALTER TABLE order_details
            ALTER COLUMN appointment_date DROP NOT NULL
        """,
        """
        ALTER TABLE order_details
            ALTER COLUMN start_time DROP NOT NULL
        """,
        """
        ALTER TABLE order_details
            ALTER COLUMN end_time DROP NOT NULL
        """,
        """
        ALTER TABLE order_details
            DROP CONSTRAINT IF EXISTS chk_order_details_time
        """,
        """
        ALTER TABLE order_details
            ADD CONSTRAINT chk_order_details_time
                CHECK (
                    start_time IS NULL
                    OR end_time IS NULL
                    OR end_time > start_time
                )
        """,
        """
        ALTER TABLE order_details
            DROP CONSTRAINT IF EXISTS chk_order_details_item_type
        """,
        """
        ALTER TABLE order_details
            ADD CONSTRAINT chk_order_details_item_type
                CHECK (
                    item_type IN (
                        'appointment',
                        'service',
                        'lead',
                        'quote',
                        'order'
                    )
                )
        """,
    ]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
    except psycopg.errors.UndefinedTable as exc:
        schema_file = DATABASE_DIR / "001_initial_schema.sql"
        raise RuntimeError(
            "Chatbot tables were not found. "
            f"Create the database and run: python scripts/init_db.py "
            f"({schema_file})"
        ) from exc
