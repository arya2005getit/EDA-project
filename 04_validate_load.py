"""
04_validate_load.py
====================
Checks that everything in hospital_clean.csv was loaded into PostgreSQL
correctly by running a series of comparison checks.

What is verified
----------------
1. Row counts  – each database table has the expected number of rows.
2. Foreign keys – no orphan rows (every FK points to an existing parent row).
3. Bill total   – the sum of all bills in the database matches the CSV total.
4. Payment counts – paid/pending counts match the CSV.
5. Insurance     – rows without a provider match "insurance = No" in the CSV.
6. Round-trip    – every field value in the database matches the original CSV.
7. Sample queries – runs the SQL queries in sample_queries.sql as a smoke test.

Run this script AFTER 03_etl_load.py.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
BASE_DIR             = Path(__file__).resolve().parent
CSV_FILE             = BASE_DIR / "hospital_clean.csv"
SAMPLE_QUERIES_FILE  = BASE_DIR / "sample_queries.sql"

# All tables we expect to find in the database
TABLES = [
    "cities", "departments", "diseases", "doctors", "insurance_providers",
    "patients", "admissions", "billing",
]


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def make_engine():
    """
    Read database credentials from .env and open a connection.
    Same logic as 03_etl_load.py so both scripts use the same settings.
    """
    load_dotenv(BASE_DIR / ".env")

    required_vars = ["PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"]
    missing_vars  = [name for name in required_vars if not os.getenv(name)]

    if missing_vars:
        raise RuntimeError(
            "Database settings are missing: " + ", ".join(missing_vars)
            + ". Copy .env.example to .env and add your PostgreSQL settings."
        )

    connection_url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        host=os.environ["PGHOST"],
        port=int(os.getenv("PGPORT", "5432")),
        database=os.environ["PGDATABASE"],
    )

    engine = create_engine(connection_url, future=True)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        engine.dispose()
        raise RuntimeError(
            "Could not connect to PostgreSQL. Check that the server is running and "
            "your PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD values are correct.\n"
            f"Database error: {error}"
        ) from error

    print("Connected to PostgreSQL.")
    return engine


# ---------------------------------------------------------------------------
# Value normalisation helper
# ---------------------------------------------------------------------------

def normalize(value, column):
    """
    Convert a value from either the CSV or the database to a common
    comparison format so that minor type differences don't cause false failures.

    For example:
    - Dates become "YYYY-MM-DD" strings
    - Bill amounts become Decimal with 2 decimal places
    - Age and stay_days become plain integers
    - Everything else becomes a string (or None for missing values)
    """
    if pd.isna(value):
        return None

    if column in ("admission_date", "discharge_date"):
        return pd.Timestamp(value).strftime("%Y-%m-%d")

    if column == "bill_amount":
        return Decimal(str(value)).quantize(Decimal("0.01"))

    if column in ("age", "stay_days"):
        return int(value)

    return str(value)


# ---------------------------------------------------------------------------
# Main validation logic
# ---------------------------------------------------------------------------

def validate_csv_and_database(connection, csv_data):
    """
    Run all seven validation checks against the live database and print
    PASS or FAIL for each one.

    Returns (results_list, mismatches_list, row_counts_dict).
    """
    results = []   # list of (label, passed, detail) tuples

    def check(label, passed, detail=""):
        """Print and record a single pass/fail result."""
        mark = "PASS" if passed else "FAIL"
        print(f"{mark}: {label}" + (f" — {detail}" if detail else ""))
        results.append((label, bool(passed), detail))

    # ------------------------------------------------------------------
    # 1. Row counts
    # ------------------------------------------------------------------
    print("\n=== CHECK 1: ROW COUNTS ===")

    # How many rows should each table have?
    expected_row_counts = {
        "cities":              csv_data["city"].nunique(),
        "departments":         csv_data["department"].nunique(),
        "diseases":            csv_data["disease"].nunique(),
        "doctors":             csv_data["doctor"].nunique(),
        "insurance_providers": csv_data["insurance_provider"].nunique(dropna=True),
        "patients":            300,
        "admissions":          300,
        "billing":             300,
    }

    actual_row_counts = {}
    for table in TABLES:
        actual_count = int(
            connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
        )
        actual_row_counts[table] = actual_count
        check(
            f"{table} row count",
            actual_count == expected_row_counts[table],
            f"expected {expected_row_counts[table]}, found {actual_count}",
        )

    # ------------------------------------------------------------------
    # 2. Foreign key checks — look for orphan rows
    # ------------------------------------------------------------------
    print("\n=== CHECK 2: FOREIGN KEY INTEGRITY ===")

    # Each query counts rows in the child table that have no matching parent row
    orphan_queries = {
        "patients.city_id → cities.city_id": """
            SELECT COUNT(*) FROM patients child
            LEFT JOIN cities parent ON parent.city_id = child.city_id
            WHERE parent.city_id IS NULL""",

        "diseases.department_id → departments.department_id": """
            SELECT COUNT(*) FROM diseases child
            LEFT JOIN departments parent ON parent.department_id = child.department_id
            WHERE parent.department_id IS NULL""",

        "admissions.patient_id → patients.patient_id": """
            SELECT COUNT(*) FROM admissions child
            LEFT JOIN patients parent ON parent.patient_id = child.patient_id
            WHERE parent.patient_id IS NULL""",

        "admissions.doctor_id → doctors.doctor_id": """
            SELECT COUNT(*) FROM admissions child
            LEFT JOIN doctors parent ON parent.doctor_id = child.doctor_id
            WHERE parent.doctor_id IS NULL""",

        "admissions.disease_id → diseases.disease_id": """
            SELECT COUNT(*) FROM admissions child
            LEFT JOIN diseases parent ON parent.disease_id = child.disease_id
            WHERE parent.disease_id IS NULL""",

        "billing.admission_id → admissions.admission_id": """
            SELECT COUNT(*) FROM billing child
            LEFT JOIN admissions parent ON parent.admission_id = child.admission_id
            WHERE parent.admission_id IS NULL""",

        "billing.provider_id → insurance_providers.provider_id": """
            SELECT COUNT(*) FROM billing child
            LEFT JOIN insurance_providers parent ON parent.provider_id = child.provider_id
            WHERE child.provider_id IS NOT NULL AND parent.provider_id IS NULL""",
    }

    for label, query in orphan_queries.items():
        orphan_count = int(connection.execute(text(query)).scalar_one())
        check(f"no orphans: {label}", orphan_count == 0, f"orphan rows: {orphan_count}")

    # ------------------------------------------------------------------
    # 3. CSV total reconciliation — bill sums and payment counts
    # ------------------------------------------------------------------
    print("\n=== CHECK 3: CSV TOTAL RECONCILIATION ===")

    # Compare total bill amount (using Decimal to avoid floating-point drift)
    db_total  = Decimal(str(
        connection.execute(text("SELECT COALESCE(SUM(bill_amount), 0) FROM billing")).scalar_one()
    )).quantize(Decimal("0.01"))
    csv_total = Decimal(str(csv_data["bill_amount"].sum())).quantize(Decimal("0.01"))
    check("total bill amount", db_total == csv_total, f"CSV {csv_total}; database {db_total}")

    # Compare Paid and Pending row counts
    for status in ["Paid", "Pending"]:
        db_count  = int(connection.execute(
            text("SELECT COUNT(*) FROM billing WHERE payment_status = :status"),
            {"status": status},
        ).scalar_one())
        csv_count = int(csv_data["payment_status"].eq(status).sum())
        check(
            f"{status} payment count",
            db_count == csv_count,
            f"CSV {csv_count}; database {db_count}",
        )

    # ------------------------------------------------------------------
    # 4. Insurance consistency
    # ------------------------------------------------------------------
    print("\n=== CHECK 4: INSURANCE CONSISTENCY ===")

    # Rows with no provider in the database should match "insurance = No" in the CSV
    uninsured_db  = int(connection.execute(
        text("SELECT COUNT(*) FROM billing WHERE provider_id IS NULL")
    ).scalar_one())
    uninsured_csv = int(csv_data["insurance"].eq("No").sum())
    check(
        "uninsured bills match CSV insurance = No",
        uninsured_db == uninsured_csv,
        f"CSV {uninsured_csv}; database {uninsured_db}",
    )

    # ------------------------------------------------------------------
    # 5. Round-trip check — reassemble the original flat CSV from the DB
    # ------------------------------------------------------------------
    print("\n=== CHECK 5: ROUND-TRIP CHECK ===")

    # This query joins all eight tables to rebuild the original flat view
    round_trip_query = text("""
        SELECT
            p.patient_id,
            p.patient_name,
            p.age,
            p.gender,
            d.disease_name       AS disease,
            dep.department_name  AS department,
            doc.doctor_name      AS doctor,
            a.admission_date,
            a.discharge_date,
            a.stay_days,
            b.bill_amount,
            CASE WHEN b.provider_id IS NULL THEN 'No' ELSE 'Yes' END AS insurance,
            ip.provider_name     AS insurance_provider,
            c.city_name          AS city,
            b.payment_status
        FROM patients p
        JOIN cities             c   ON c.city_id       = p.city_id
        JOIN admissions         a   ON a.patient_id    = p.patient_id
        JOIN doctors            doc ON doc.doctor_id   = a.doctor_id
        JOIN diseases           d   ON d.disease_id    = a.disease_id
        JOIN departments        dep ON dep.department_id = d.department_id
        JOIN billing            b   ON b.admission_id  = a.admission_id
        LEFT JOIN insurance_providers ip ON ip.provider_id = b.provider_id
        ORDER BY p.patient_id
    """)

    db_rows  = pd.read_sql_query(round_trip_query, connection)
    csv_rows = csv_data.copy().sort_values("patient_id").reset_index(drop=True)
    db_rows  = db_rows.sort_values("patient_id").reset_index(drop=True)

    columns_to_compare = [
        "patient_id", "patient_name", "age", "gender", "disease", "department",
        "doctor", "admission_date", "discharge_date", "stay_days", "bill_amount",
        "insurance", "insurance_provider", "city", "payment_status",
    ]

    mismatches = []

    if len(db_rows) != len(csv_rows):
        # Completely different row counts — no point checking field by field
        mismatches.append({"row_count": {"csv": len(csv_rows), "database": len(db_rows)}})
    else:
        for row_number in range(len(csv_rows)):
            row_differences = {}
            for column in columns_to_compare:
                csv_value = normalize(csv_rows.at[row_number, column], column)
                db_value  = normalize(db_rows.at[row_number, column],  column)
                if csv_value != db_value:
                    row_differences[column] = {"csv": csv_value, "database": db_value}
            if row_differences:
                mismatches.append({
                    "patient_id":  csv_rows.at[row_number, "patient_id"],
                    "differences": row_differences,
                })

    check(
        "round trip matches all 15 CSV fields",
        not mismatches,
        f"mismatched rows: {len(mismatches)}",
    )

    if mismatches:
        print("Mismatch details:")
        for mismatch in mismatches:
            print(f"  {mismatch}")

    # ------------------------------------------------------------------
    # 6. Spot check – show a few random rows for visual inspection
    # ------------------------------------------------------------------
    print("\n=== CHECK 6: FIVE-ROW SPOT CHECK ===")
    if db_rows.empty:
        print("No rows returned from the database.")
    else:
        sample = db_rows.sample(n=min(5, len(db_rows)), random_state=42)[columns_to_compare]
        print(sample.to_string(index=False))

    # ------------------------------------------------------------------
    # 7. Sample query smoke test
    # ------------------------------------------------------------------
    print("\n=== CHECK 7: SAMPLE QUERY RESULTS ===")
    if SAMPLE_QUERIES_FILE.exists():
        query_text = SAMPLE_QUERIES_FILE.read_text(encoding="utf-8")

        # Strip SQL comments (anything after --) so we can split on semicolons safely
        uncommented = "\n".join(
            line.split("--", 1)[0] for line in query_text.splitlines()
        )
        statements = [part.strip() for part in uncommented.split(";") if part.strip()]

        for number, statement in enumerate(statements, start=1):
            result = pd.read_sql_query(text(statement), connection)
            print(f"\nSample query {number} ({len(result)} rows):")
            print(result.to_string(index=False))
    else:
        print(f"Sample queries file not found: {SAMPLE_QUERIES_FILE}")

    return results, mismatches, actual_row_counts


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def update_report(results, mismatches, row_counts):
    """
    Append the validation results to etl_report.md.
    Replaces any previous validation section so we don't accumulate duplicates.
    """
    overall_status = (
        "ALL CHECKS PASSED"
        if all(passed for _, passed, _ in results)
        else "SOME CHECKS FAILED"
    )

    lines = [
        "## Validation", "",
        f"Overall result: **{overall_status}**. "
        f"Round-trip mismatched rows: **{len(mismatches)}**.", "",
        "| Check | Result | Details |",
        "|---|---|---|",
    ]

    for label, passed, detail in results:
        safe_detail = detail.replace("|", "\\|")   # escape pipe characters for Markdown tables
        lines.append(f"| {label} | {'PASS' if passed else 'FAIL'} | {safe_detail} |")

    report_path = BASE_DIR / "etl_report.md"
    existing    = report_path.read_text(encoding="utf-8") if report_path.exists() \
                  else "# ETL and database load report\n"

    # Remove any old validation section so we start fresh
    if "## Validation" in existing:
        existing = existing.split("## Validation", 1)[0].rstrip() + "\n\n"

    # Add a row-count table if it is missing (e.g. if the ETL report was deleted)
    if "## Rows inserted in the latest successful load" not in existing:
        count_lines = [
            "## Rows inserted in the latest successful load", "",
            "| Table | Rows inserted |", "|---|---:|",
        ]
        count_lines.extend(f"| `{table}` | {count} |" for table, count in row_counts.items())
        existing = existing.rstrip() + "\n\n" + "\n".join(count_lines) + "\n\n"

    report_path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nValidation results saved to {report_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_FILE}")

    # Load the CSV (same dtype settings as the ETL script)
    csv_data = pd.read_csv(
        CSV_FILE,
        dtype={"patient_id": "string"},
        parse_dates=["admission_date", "discharge_date"],
    )

    engine = make_engine()
    try:
        with engine.connect() as connection:
            results, mismatches, row_counts = validate_csv_and_database(connection, csv_data)
        update_report(results, mismatches, row_counts)
    finally:
        engine.dispose()

    if not all(passed for _, passed, _ in results):
        raise SystemExit(
            "One or more load checks FAILED. "
            "Review the output above and etl_report.md for details."
        )

    print("\nOverall validation: ALL CHECKS PASSED")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Validation stopped: {error}") from error
