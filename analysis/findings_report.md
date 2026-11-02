# Hospital Data Analysis – Findings Report
**Step 4: SQL Joins & Analysis | Dataset: 300 admissions, hospital_db**

---

## Key Insights (backed by actual query numbers)

### 1. General Medicine is the busiest and highest-revenue department
Q01 shows General Medicine handled **68 admissions** — nearly double the next department (Pulmonology with 52). Q08 confirms it also generated the highest total revenue: **₹89,74,444**, though Endocrinology commands the highest average bill (₹1,49,233).

### 2. Pulmonology punches above its weight on revenue
Pulmonology had 52 admissions (second most) but generated ₹73,50,125 in revenue with the highest department average bill of **₹1,41,349** — showing that pulmonology treatments are expensive per admission.

### 3. Over half the patients have no insurance, and they pay more per bill on average
Q05 reveals that **154 out of 300 patients (51.3%) are self-pay (uninsured)** with a total billed amount of ₹2,06,21,533 and an average bill of **₹1,33,906** — roughly ₹7,000 more per bill than insured patients (₹1,26,908). This is worth investigating as it may indicate under-use of insurance.

### 4. Nearly half the total bills are still pending — a significant collection problem
Q10 shows **143 of 300 bills are Pending** (47.7%) with a total unpaid amount spread across all departments. General Medicine has the most pending bills: **39 pending vs 29 paid** — it is the only major department where pending bills outnumber paid ones.

### 5. Insured patients have a *higher* pending rate than uninsured patients
Q24 is counterintuitive: **51.37% of insured patients' bills are pending**, compared to **44.16% for self-pay** patients. This may reflect insurance claim delays or processing time — a real operational issue for hospital finance teams.

### 6. Diabetes and Asthma are the most expensive diseases on average
Q11 shows four diseases have average bills above the hospital-wide average of **₹1,30,501**:
- **Diabetes** (Endocrinology): ₹1,49,233
- **Asthma** (Pulmonology): ₹1,47,225
- **Migraine** (Neurology): ₹1,35,066
- **Dengue** (General Medicine): ₹1,33,974

### 7. April was the busiest and highest-revenue month
Q21 reveals April 2026 had the most admissions (**62**) and highest revenue (**₹84,31,949**). January had the fewest admissions (42) and lowest revenue (₹48,43,772). Q22 shows month-over-month revenue grew **56.9% from February to March** — the steepest jump.

### 8. Tuesdays have the most admissions; Thursdays the fewest
Q23 shows **Tuesday** is the busiest admission day (51 admissions) and **Thursday** the quietest (32 admissions). This is somewhat uniform across weekdays, suggesting admissions are distributed throughout the week without a clear weekly cycle — possibly reflecting emergency/walk-in patterns rather than scheduled admissions.

### 9. Mumbai + Asthma is the single costliest city–disease combination
Q26 shows **Mumbai + Asthma** tops the list with **13 admissions totalling ₹18,11,360** (avg ₹1,39,335). The next combination, Nashik + Kidney Stone, had 11 admissions and ₹14,26,213 total.

### 10. Seniors (61+) generate the most admissions, but middle-aged patients have lower average bills
Q12 shows **103 senior admissions (61+)** — the largest group. However, middle-aged patients (41–60) have the lowest average bill at **₹1,18,646**, while young adults (19–40) have the highest at **₹1,37,761**. Note: only 1 child (0–18) is in the dataset, so that group's data is not meaningful.

---

## What JOINs and Relationships Allowed That a Single Table Could Not

A flat single table can store data, but JOINs over a normalised schema enabled much richer analysis:

1. **Reaching department through disease** — The schema intentionally omits `department` from `admissions`. Without the JOIN `admissions → diseases → departments`, it would be impossible to group admissions by department. Every department-level insight (Q01, Q08, Q10, Q13, Q14) depends on this two-hop join.

2. **Linking uninsured patients without a dedicated flag** — There is no "is_insured" column. Instead, a `LEFT JOIN` between `billing` and `insurance_providers` produces `NULL` for `provider_id` when no insurance exists. The `COALESCE(provider_name, 'Self-Pay')` pattern cleanly handles this in SQL, which a flat table with a text column would handle inconsistently.

3. **Cross-dimension analysis** — Joining five or more tables in a single query lets us ask questions like "which city + disease combination costs the most?" (Q26). This requires bridging `patients → cities` (for geography) with `admissions → diseases` (for clinical context) and `billing` (for money) — impossible from any single table.

4. **Window functions over joined data** — Q14 (ranking doctors by revenue *within* each department) and Q15 (top-3 expensive admissions *per* department) use `PARTITION BY department_name`, which is only meaningful after joining `admissions`, `diseases`, `departments`, `doctors`, and `billing`. The partition key itself comes from a different table than the metric being ranked.

---

## Limitations

> The following limitations should be stated clearly when presenting this analysis:

- **Small dataset**: The dataset contains only **300 rows**. Statistical patterns (averages, percentages) have wide uncertainty. Real-world hospital databases have tens of thousands of rows.
- **Repeated patient names**: The source data has only about **10 distinct patient names** (e.g., Rahul, Priya, Amit). Each name appears ~30 times across different `patient_id` values. Patient-level analysis (e.g., "which patient has the highest total spend") is not meaningful.
- **One admission per patient**: Every patient has exactly **one admission** in this dataset, even though the schema supports many. Repeat-visit analysis (readmission rates, chronic disease tracking) cannot be done.
- **Synthetic data**: The data was generated for practice and does not represent a real hospital's operations. Findings like "insured patients have higher pending rates" or "Tuesdays are busiest" are artifacts of the data generation process, not real medical conclusions.
- **Narrow time range**: All admissions fall within a **6-month window** (January–June 2026), so seasonality analysis is limited to half a year.

---

## Business Recommendations

*(These follow from the data patterns; they are exercise-level suggestions, not clinical advice.)*

### 1. Prioritise collections for General Medicine's pending bills
General Medicine is the only major department where pending bills **outnumber** paid ones (39 pending vs 29 paid). The hospital should implement a follow-up reminder system or dedicated billing officer for this department. The unpaid amount across all departments is substantial — addressing even 50% of pending bills would add several lakhs of rupees to cash flow.

### 2. Investigate why insured patients have a higher pending rate than uninsured
An insured patient pending rate of **51.37%** vs **44.16%** for self-pay is unusual. This likely points to delays in insurance claim submission or rejection. The hospital should audit its claim-filing process and set a target to reduce the insured-pending rate below the self-pay rate.

### 3. Plan staffing around the April peak and mid-week pattern
April had **62 admissions** (48% more than January's 42) and generated the highest monthly revenue. Ensuring adequate staffing in spring months will improve patient care. Additionally, Tuesdays (51 admissions) are significantly busier than Thursdays (32), suggesting doctors and admission staff could be distributed more efficiently across the week.

### 4. Focus preventive programmes on Diabetes and Asthma in Mumbai and Nagpur
These two diseases have the highest average bills and appear frequently as top city–disease pairs. Community health initiatives targeting **diabetes prevention in Nagpur** (₹12,69,667 total, 9 cases) and **asthma management in Mumbai** (₹18,11,360 total, 13 cases) could reduce hospitalisation and associated costs.

---

## Files Created in This Step

| File | Purpose |
|---|---|
| [`05_views.sql`](../05_views.sql) | 3 reusable views joining all 8 tables |
| [`06_analysis_queries.sql`](../06_analysis_queries.sql) | 26 SQL queries across 7 categories |
| [`07_run_analysis.py`](../07_run_analysis.py) | Runs queries, prints tables, exports CSVs |
| [`08_charts.py`](../08_charts.py) | Generates 6 PNG charts with matplotlib |
| `analysis/results/` | 26 CSV files (one per query) |
| `analysis/charts/` | 6 PNG chart files |
| `analysis/findings_report.md` | This report |
