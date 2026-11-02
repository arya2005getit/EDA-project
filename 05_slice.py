"""OLAP slice: view patients from one city."""
    
import pandas as pd

from olap_db import get_connection


QUERY = """
SELECT patient_id, patient_name, disease_name, department_name, doctor_name,
       admission_date, stay_days, bill_amount, payment_status
FROM vw_admission_details
WHERE city_name = %s
ORDER BY admission_date, patient_id
"""


with get_connection() as connection:
    result = pd.read_sql_query(QUERY, connection, params=("Mumbai",))

print("SLICE: Mumbai patients")
print(result.to_string(index=False))


