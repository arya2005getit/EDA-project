"""Shared PostgreSQL connection for the simple OLAP examples."""

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
VIEWS_FILE = BASE_DIR / "05_views.sql"


@contextmanager
def get_connection():
    """Connect to PostgreSQL and make sure the analysis views exist."""
    load_dotenv(BASE_DIR / ".env")

    required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing database settings: " + ", ".join(missing)
            + ". Copy .env.example to .env and set your PostgreSQL credentials."
        )

    connection = psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
    )

    try:
        with connection:
            with connection.cursor() as cursor:
                sql_text = VIEWS_FILE.read_text(encoding="utf-8")
                sql_without_comments = "\n".join(
                    line.split("--", 1)[0] for line in sql_text.splitlines()
                )
                statements = [
                    statement.strip()
                    for statement in sql_without_comments.split(";")
                    if statement.strip()
                ]
                if not statements:
                    raise RuntimeError(f"No SQL statements found in {VIEWS_FILE.name}.")

                for statement in statements:
                    cursor.execute(statement)
            yield connection
    finally:
        connection.close()
