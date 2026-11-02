"""
01_data_cleaning.py
====================
Reads the raw hospital CSV (Hospi.csv), cleans the data step by step,
and writes a single reliable output file (hospital_clean.csv) along with
a Markdown report (cleaning_report.md).

Run from any folder; all input/output files are placed next to this script.
"""

from pathlib import Path
from datetime import datetime

import pandas as pd


# ---------------------------------------------------------------------------
# File paths  (all relative to this script's location)
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent
INPUT_FILE  = BASE_DIR / "Hospi.csv"
OUTPUT_FILE = BASE_DIR / "hospital_clean.csv"
REPORT_FILE = BASE_DIR / "cleaning_report.md"

# ---------------------------------------------------------------------------
# Column configuration
# ---------------------------------------------------------------------------

# The final column names we want after renaming
EXPECTED_COLUMNS = [
    "patient_id", "patient_name", "age", "gender", "disease", "department",
    "doctor", "admission_date", "discharge_date", "stay_days", "bill_amount",
    "insurance", "insurance_provider", "city", "payment_status",
]

# Maps the raw CSV column headers to clean snake_case names
RENAME_COLUMNS = {
    "Patient ID":       "patient_id",
    "Patient_Name":     "patient_name",
    "Age":              "age",
    "Gender":           "gender",
    "Disease":          "disease",
    "Department":       "department",
    "Doctor":           "doctor",
    "Admission Date":   "admission_date",
    "Discharge Date":   "discharge_date",
    "Stay (Days)":      "stay_days",
    "Bill Amount (₹)":  "bill_amount",
    "Insurance":        "insurance",
    "Insurance Provider": "insurance_provider",
    "City":             "city",
    "Payment Status":   "payment_status",
}

# Columns that contain free-text and need trimming / title-casing
TEXT_COLUMNS = [
    "patient_id", "patient_name", "gender", "disease", "department", "doctor",
    "insurance", "insurance_provider", "city", "payment_status",
]

# Columns that should have a small, fixed set of values (used for reporting)
CATEGORY_COLUMNS = [
    "gender", "disease", "department", "doctor",
    "insurance_provider", "city", "payment_status",
]


# ---------------------------------------------------------------------------
# Step 1 – Profile raw data
# ---------------------------------------------------------------------------

def profile_data(frame):
    """Print a quick snapshot of the raw CSV so we know what we're starting with."""
    print("\n=== STEP 1: PROFILE BEFORE CLEANING ===")
    print(f"Shape: {frame.shape}")
    print("\nData types:\n",          frame.dtypes.to_string())
    print("\nNull counts:\n",         frame.isna().sum().to_string())
    print(f"\nExact duplicate rows:  {frame.duplicated().sum()}")
    print("\nUnique values per column (nulls counted as a value):\n",
          frame.nunique(dropna=False).to_string())


# ---------------------------------------------------------------------------
# Step 3 – Standardise text
# ---------------------------------------------------------------------------

def standardize_text(frame):
    """
    Trim leading/trailing whitespace and convert text columns to Title Case.
    Also corrects known capitalisation quirks (e.g. 'Covid-19' → 'COVID-19').
    Returns the number of rows that were changed.
    """
    before = frame.copy()

    # Apply strip + title-case to every text column
    for column in TEXT_COLUMNS:
        frame[column] = frame[column].map(
            lambda value: value.strip().title() if isinstance(value, str) else value
        )

    # Fix disease names that title-case gets wrong
    frame["disease"] = frame["disease"].replace({"Covid-19": "COVID-19"})

    # Fix insurance provider names where title-case produces wrong results
    frame["insurance_provider"] = frame["insurance_provider"].replace({
        "Hdfc Ergo":    "HDFC Ergo",
        "Icici Lombard": "ICICI Lombard",
    })

    # A dash ("-") in insurance_provider means "no provider" → treat as missing
    frame["insurance_provider"] = frame["insurance_provider"].replace({"-": pd.NA})

    # Report the unique values for each category column so we can spot mistakes
    print("\n=== STEP 3: STANDARDISED CATEGORY VALUES ===")
    for column in CATEGORY_COLUMNS:
        print(f"  {column}: {sorted(frame[column].dropna().unique().tolist())}")

    # Count how many rows actually changed
    rows_changed = int(
        (before[TEXT_COLUMNS].fillna("") != frame[TEXT_COLUMNS].fillna(""))
        .any(axis=1)
        .sum()
    )
    print(f"Rows affected by text cleanup: {rows_changed}")
    return rows_changed


# ---------------------------------------------------------------------------
# Step 4 – Parse dates
# ---------------------------------------------------------------------------

def parse_one_date(value):
    """
    Try to parse a single date value using the two allowed month-first formats.
    Returns a pandas Timestamp on success, or NaT (not-a-time) if parsing fails.
    We never use day-first guessing to avoid ambiguous dates.
    """
    if pd.isna(value) or not str(value).strip():
        return pd.NaT

    raw = str(value).strip()

    # Try MM-DD-YYYY first, then MM/DD/YYYY
    for date_format in ("%m-%d-%Y", "%m/%d/%Y"):
        try:
            return pd.Timestamp(datetime.strptime(raw, date_format))
        except (ValueError, TypeError):
            pass

    # If neither format worked, signal a parse failure
    return pd.NaT


def parse_dates(frame):
    """
    Parse both date columns and print a list of any values that could not be parsed.
    Returns a list of (csv_row_number, column_name, original_value) tuples for failures.
    """
    print("\n=== STEP 4: PARSE DATES ===")
    failures = []

    for column in ("admission_date", "discharge_date"):
        raw_values = frame[column].copy()
        parsed     = raw_values.map(parse_one_date)

        # Collect every row where parsing failed (result is NaT)
        for row_index in parsed[parsed.isna()].index:
            # Add 2 because: +1 for 0-based index, +1 for the CSV header row
            failures.append((row_index + 2, column, raw_values.loc[row_index]))

        frame[column] = pd.to_datetime(parsed)

    if failures:
        print("Date parse failures (CSV row number, column, original value):")
        for failure in failures:
            print("  ", failure)
    else:
        print("All admission and discharge dates parsed successfully.")

    return failures


# ---------------------------------------------------------------------------
# Step 5 – Convert bill amount
# ---------------------------------------------------------------------------

def convert_bill_amount(frame):
    """
    Strip the ₹ symbol, commas, and spaces from the bill_amount column,
    then convert it to a proper number.
    Returns a boolean Series marking rows where conversion failed.
    """
    print("\n=== STEP 5: CONVERT BILL AMOUNT ===")

    original_values = frame["bill_amount"].copy()

    # Remove currency symbols, commas, and whitespace before converting
    cleaned = original_values.astype("string").str.replace(r"[₹,\s]", "", regex=True)
    frame["bill_amount"] = pd.to_numeric(cleaned, errors="coerce")

    # A row failed if the original had a value but the conversion produced NaN
    conversion_failed = frame["bill_amount"].isna() & original_values.notna()

    print(f"Converted bill amounts to numbers; unconvertible non-empty values: {int(conversion_failed.sum())}")
    if conversion_failed.any():
        print("Unconvertible values:", original_values[conversion_failed].to_dict())

    return conversion_failed


# ---------------------------------------------------------------------------
# Step 7 – Check stay length
# ---------------------------------------------------------------------------

def compare_and_fix_stay(frame):
    """
    Compare the source stay_days value against the difference between
    admission_date and discharge_date.

    - If all rows match: replace stay_days with the calculated value (more reliable).
    - If any rows differ: keep the original and print details for manual review.
    """
    print("\n=== STEP 7: CHECK STAY LENGTH ===")

    original_stay  = pd.to_numeric(frame["stay_days"], errors="coerce")
    calculated_stay = (frame["discharge_date"] - frame["admission_date"]).dt.days

    # A row is a mismatch if the values differ OR either one is missing
    is_mismatch = original_stay.ne(calculated_stay) | original_stay.isna() | calculated_stay.isna()

    print(f"Rows where stay_days differs from date difference: {int(is_mismatch.sum())}")

    if is_mismatch.any():
        details = pd.DataFrame({
            "csv_row":             is_mismatch[is_mismatch].index + 2,
            "original_stay_days":  original_stay[is_mismatch],
            "date_difference_days": calculated_stay[is_mismatch],
        })
        print(details.to_string(index=False))
        print("Note: stay_days was NOT overwritten — mismatches need manual review.")
    else:
        frame["stay_days"] = calculated_stay.astype("int64")
        print("All rows agree; stay_days was recalculated from the parsed dates.")

    return is_mismatch, original_stay, calculated_stay


# ---------------------------------------------------------------------------
# Step 8 – Validate
# ---------------------------------------------------------------------------

def validate(frame):
    """
    Run each business rule check and print PASS or FAIL for each one.
    Also prints the disease-to-department mapping for reference.
    Returns (checks_dict, mapping_series).
    """
    print("\n=== STEP 8: VALIDATION ===")

    # Check how many departments each disease maps to (should be exactly 1)
    disease_dept_count = frame.groupby("disease", dropna=False)["department"].nunique(dropna=False)

    # Build a readable disease → department map for the report
    disease_dept_mapping = frame.groupby("disease", dropna=False)["department"].agg(
        lambda departments: ", ".join(sorted(set(departments.dropna().astype(str))))
    )

    print("Disease to department mapping:")
    for disease, department in disease_dept_mapping.items():
        print(f"  {disease}: {department}")

    # Define all rules as a dictionary of { description: True/False }
    checks = {
        "patient_id is unique and not null": (
            frame["patient_id"].notna().all() and frame["patient_id"].is_unique
        ),
        "age is between 0 and 120": (
            frame["age"].between(0, 120).all()
        ),
        "gender is only Male/Female": (
            frame["gender"].isin(["Male", "Female"]).all()
        ),
        "discharge_date >= admission_date": (
            (frame["discharge_date"] >= frame["admission_date"]).all()
        ),
        "bill_amount > 0": (
            frame["bill_amount"].gt(0).all()
        ),
        'insurance == "Yes" iff insurance_provider is present': (
            (frame["insurance"].eq("Yes") == frame["insurance_provider"].notna()).all()
        ),
        "payment_status is only Paid/Pending": (
            frame["payment_status"].isin(["Paid", "Pending"]).all()
        ),
        "no fully duplicated rows": (
            not frame.duplicated().any()
        ),
        "each disease maps to exactly one department": (
            disease_dept_count.eq(1).all()
        ),
    }

    for rule, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}: {rule}")

    return checks, disease_dept_mapping


# ---------------------------------------------------------------------------
# Step 10 – Before vs after summary
# ---------------------------------------------------------------------------

def summary_table(before_frame, after_frame):
    """
    Build and print a side-by-side table showing row counts, null counts,
    and data types before and after cleaning.
    """
    print("\n=== STEP 10: BEFORE VS AFTER SUMMARY ===")

    row_labels = (
        ["row_count"]
        + [f"nulls: {col}" for col in EXPECTED_COLUMNS]
        + [f"dtype: {col}" for col in EXPECTED_COLUMNS]
    )

    summary = pd.DataFrame(index=row_labels, columns=["before", "after"])
    summary.loc["row_count"] = [len(before_frame), len(after_frame)]

    for column in EXPECTED_COLUMNS:
        # Find the original header name for this column so we can compare
        original_name = next(
            raw for raw, clean in RENAME_COLUMNS.items() if clean == column
        )
        summary.loc[f"nulls: {column}"] = [
            before_frame[original_name].isna().sum(),
            after_frame[column].isna().sum(),
        ]
        summary.loc[f"dtype: {column}"] = [
            str(before_frame[original_name].dtype),
            str(after_frame[column].dtype),
        ]

    print(summary.to_string())
    return summary


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main():
    """
    Run all cleaning steps in order, then write the clean CSV and a Markdown report.
    Steps:
      1  Profile raw data
      2  Rename columns to snake_case
      3  Standardise text (trim, title-case, fix known quirks)
      4  Parse date columns
      5  Convert bill_amount to a number
      6  Convert age and stay_days to numbers
      7  Check that stay_days matches the date difference
      8  Validate business rules
      9  Remove exact duplicate rows
      10 Print a before-vs-after summary
    """
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    # --- Read raw CSV (let pandas infer types so the initial profile is honest) ---
    raw_frame = pd.read_csv(INPUT_FILE)
    profile_data(raw_frame)
    raw_duplicate_count = int(raw_frame.duplicated().sum())

    # --- Rename columns so every step below uses clean names ---
    frame = raw_frame.rename(columns=RENAME_COLUMNS).copy()
    if list(frame.columns) != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected columns after rename. Found: {list(frame.columns)}")

    # --- Run each cleaning step ---
    text_rows_changed = standardize_text(frame)

    # Convert numeric columns; invalid values become NaN (visible, not silently dropped)
    frame["age"]       = pd.to_numeric(frame["age"],       errors="coerce")
    frame["stay_days"] = pd.to_numeric(frame["stay_days"], errors="coerce")

    date_failures  = parse_dates(frame)
    bill_failures  = convert_bill_amount(frame)
    stay_mismatch, original_stay, calculated_stay = compare_and_fix_stay(frame)

    # --- Remove exact duplicate rows (source currently has none) ---
    duplicates_removed = int(frame.duplicated().sum())
    if duplicates_removed:
        frame = frame.drop_duplicates().reset_index(drop=True)
        print(f"Dropped {duplicates_removed} exact duplicate row(s).")
    else:
        print("No rows dropped: there were no exact duplicate records.")

    checks, disease_mapping = validate(frame)
    summary = summary_table(raw_frame, frame)

    # --- Write clean CSV (dates in ISO format; missing values become empty cells) ---
    frame.to_csv(OUTPUT_FILE, index=False, date_format="%Y-%m-%d", na_rep="")
    print(f"\nCleaned CSV written to: {OUTPUT_FILE}")

    # --- Build and write the Markdown report ---
    failed_rules = [rule for rule, passed in checks.items() if not passed]

    report_lines = [
        "# Hospital data cleaning report", "",
        f"Input: `{INPUT_FILE.name}` (original file left unchanged)",
        f"Output: `{OUTPUT_FILE.name}`", "",
        "## Problems found and actions", "",
        f"- Source size: {raw_frame.shape[0]} rows × {raw_frame.shape[1]} columns.",
        f"- Mixed month-first date formats parsed with `%m-%d-%Y` and `%m/%d/%Y`; failures: {len(date_failures)}.",
        f"- Currency text stripped and converted to numeric; failures: {int(bill_failures.sum())}.",
        f"- Text trimming/capitalisation cleanup affected {text_rows_changed} row(s).",
        f"- `-` in `insurance_provider` replaced with missing value "
        f"({int(frame['insurance_provider'].isna().sum())} missing after cleaning).",
        f"- Exact duplicate rows in source: {raw_duplicate_count}; removed: {duplicates_removed}.",
        f"- Stay length mismatches: {int(stay_mismatch.sum())}.",
    ]

    if stay_mismatch.any():
        report_lines.append(
            "- Mismatched `stay_days` values were preserved for review; "
            "see the console output for details."
        )
    else:
        report_lines.append(
            "- Stay lengths matched the date differences and were recalculated from the dates."
        )

    if date_failures:
        report_lines.extend(["", "Date parse failures:"])
        report_lines.extend([
            f"- CSV row {row}, `{col}`: `{val}`"
            for row, col, val in date_failures
        ])

    if bill_failures.any():
        report_lines.extend(["", "Bill amount conversion failures:"])
        report_lines.extend([
            f"- CSV row {row + 2}: `{raw_frame.loc[row, 'Bill Amount (₹)']}`"
            for row in bill_failures[bill_failures].index
        ])

    report_lines.extend(["", "## Validation results", ""])
    report_lines.extend([
        f"- {'PASS' if passed else 'FAIL'} — {rule}"
        for rule, passed in checks.items()
    ])
    report_lines.extend(["", "Disease to department mapping:", ""])
    report_lines.extend([
        f"- {disease}: {dept}"
        for disease, dept in disease_mapping.items()
    ])
    report_lines.extend(["", "## Before vs after summary", "", "```text", summary.to_string(), "```", ""])
    report_lines.append(
        "All validation checks passed."
        if not failed_rules
        else "Failed checks: " + "; ".join(failed_rules)
    )

    REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Cleaning report written to: {REPORT_FILE}")
    print("\nOverall validation:", "ALL PASS" if not failed_rules else "CHECK FAILURES — see report")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
