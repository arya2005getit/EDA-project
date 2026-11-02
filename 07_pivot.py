"""OLAP pivot: compare paid and pending bills by department."""

import pandas as pd

from olap_db import get_connection


QUERY = """
SELECT department_name, payment_status, SUM(bill_amount) AS total_bill
FROM vw_admission_details
GROUP BY department_name, payment_status
ORDER BY department_name, payment_status
"""


with get_connection() as connection:
    result = pd.read_sql_query(QUERY, connection)

pivot = result.pivot_table(
    index="department_name",
    columns="payment_status",
    values="total_bill",
    aggfunc="sum",
    fill_value=0,
).round(2)

print("PIVOT: Total bill by department and payment status")
print(pivot.to_string())
