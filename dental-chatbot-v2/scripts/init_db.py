import sys
from pathlib import Path

from app.config import DATABASE_DIR, DB_CONFIG
from app.db import ensure_schema, get_connection


def split_sql(sql_text: str) -> list[str]:
    statements = []

    for raw in sql_text.split(";"):
        statement = raw.strip()

        if not statement or statement.upper() == "COMMIT":
            continue

        statements.append(statement)

    return statements


def tables_exist() -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.chat_flows')")
            return cur.fetchone()[0] is not None


def apply_file(path: Path) -> None:
    sql_text = path.read_text(encoding="utf-8")

    with get_connection() as conn:
        with conn.cursor() as cur:
            for statement in split_sql(sql_text):
                cur.execute(statement)
        conn.commit()


def main() -> None:
    initial = DATABASE_DIR / "001_initial_schema.sql"
    runtime = DATABASE_DIR / "002_generic_runtime.sql"

    if not tables_exist():
        if not initial.exists():
            print(f"Schema file not found: {initial}")
            sys.exit(1)

        print(f"Creating tables from {initial}")
        apply_file(initial)
    else:
        print("Core tables already exist.")

    if runtime.exists():
        print(f"Applying runtime extras from {runtime}")
        ensure_schema()

    print()
    print("Database is ready.")
    print(f"Connected to {DB_CONFIG['dbname']} on {DB_CONFIG['host']}")
    print()
    print("Next:")
    print("  python scripts/import_flow.py flow/dental_reception.json")
    print("  python scripts/import_flow.py flow/oil_company.json")
    print("  python scripts/import_appointments.py flow/appointments.json")


if __name__ == "__main__":
    main()
