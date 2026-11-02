"""OLAP dice: view female patients from one city."""

import pandas as pd

from olap_db import get_connection


QUERY = """
SELECT patient_id, patient_name, city_name, gender, disease_name,
       department_name, doctor_name, bill_amount, payment_status
FROM vw_admission_details
WHERE city_name = %s AND gender = %s
ORDER BY patient_id
"""


with get_connection() as connection:
    result = pd.read_sql_query(QUERY, connection, params=("Mumbai", "Female"))

print("DICE: Female patients from Mumbai")
print(result.to_string(index=False))
