"""
02_profile_for_design.py
=========================
Reads hospital_clean.csv and checks several assumptions about the data
that the database schema design depends on.

Run this script AFTER 01_data_cleaning.py and BEFORE creating schema.sql.
If any assumption fails, the script exits with an error message so you
know to fix the data before designing the schema.
"""

from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# File path
# ---------------------------------------------------------------------------
CSV_FILE = Path(__file__).resolve().parent / "hospital_clean.csv"


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def main():
    # Load the cleaned data
    data = pd.read_csv(CSV_FILE)
    print(f"Rows and columns: {data.shape}")

    # ------------------------------------------------------------------
    # 1. How many unique values does each text column have?
    #    Useful for deciding which columns need lookup tables.
    # ------------------------------------------------------------------
    print("\nUnique counts for categorical (text) columns:")
    categorical_columns = data.select_dtypes(include="object").columns
    for column in categorical_columns:
        print(f"  {column}: {data[column].nunique(dropna=True)}")

    # ------------------------------------------------------------------
    # 2. Does each disease map to exactly one department?
    #    If yes, we can store the department inside the diseases table
    #    instead of in every admission row.
    # ------------------------------------------------------------------
    disease_dept_count  = data.groupby("disease")["department"].nunique(dropna=False)
    disease_dept_mapping = data.groupby("disease")["department"].unique()

    print("\nDisease-to-department mapping:")
    for disease, departments in disease_dept_mapping.items():
        print(f"  {disease}: {', '.join(map(str, departments))}")

    disease_maps_to_one_dept = disease_dept_count.eq(1).all()
    print(f"Each disease maps to exactly one department: {disease_maps_to_one_dept}")

    # ------------------------------------------------------------------
    # 3. Do doctors appear in multiple departments?
    #    If yes, we cannot store department_id directly on the doctors table.
    # ------------------------------------------------------------------
    doctor_dept_count = data.groupby("doctor")["department"].nunique(dropna=False)
    every_doctor_in_multiple_depts = doctor_dept_count.gt(1).all()

    print("\nDepartments per doctor:")
    for doctor, count in doctor_dept_count.items():
        print(f"  {doctor}: {count}")

    print(f"Every doctor appears across multiple departments: {every_doctor_in_multiple_depts}")

    # ------------------------------------------------------------------
    # 4. Does 'insurance = Yes' always match a non-null insurance_provider?
    #    The two columns should be perfectly consistent with each other.
    # ------------------------------------------------------------------
    insurance_matches_provider = (
        data["insurance"].eq("Yes") == data["insurance_provider"].notna()
    ).all()
    print("\nInsurance 'Yes' exactly matches provider present: ", insurance_matches_provider, sep="")

    # ------------------------------------------------------------------
    # 5. Summarise all assumptions and exit with an error if any fail
    # ------------------------------------------------------------------
    assumptions = {
        "patient_id is unique per row": (
            data["patient_id"].notna().all() and data["patient_id"].is_unique
        ),
        "disease maps to one department": disease_maps_to_one_dept,
        "every doctor appears in multiple departments": every_doctor_in_multiple_depts,
        "insurance status matches provider presence": insurance_matches_provider,
    }

    print("\nAssumption checks:")
    for assumption, passed in assumptions.items():
        print(f"  {'PASS' if passed else 'FAIL'}: {assumption}")

    if not all(assumptions.values()):
        raise SystemExit(
            "\nAt least one design assumption is FALSE. "
            "Review the output above and fix the data before designing the schema."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
