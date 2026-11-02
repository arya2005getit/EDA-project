-- 1. Show a useful admission record by joining the patient, visit, disease, and department.
SELECT p.patient_id, p.patient_name, a.admission_date,
       d.disease_name, dep.department_name
FROM admissions AS a
JOIN patients AS p ON p.patient_id = a.patient_id
JOIN diseases AS d ON d.disease_id = a.disease_id
JOIN departments AS dep ON dep.department_id = d.department_id;

-- 2. Show bills and insurance providers; uninsured bills stay in the result.
SELECT b.bill_id, b.admission_id, b.bill_amount,
       ip.provider_name, b.payment_status
FROM billing AS b
LEFT JOIN insurance_providers AS ip ON ip.provider_id = b.provider_id;

-- 3. Add up billed revenue for each department through each admission's disease.
SELECT dep.department_name, SUM(b.bill_amount) AS total_revenue
FROM departments AS dep
JOIN diseases AS d ON d.department_id = dep.department_id
JOIN admissions AS a ON a.disease_id = d.disease_id
JOIN billing AS b ON b.admission_id = a.admission_id
GROUP BY dep.department_id, dep.department_name
ORDER BY dep.department_name;

-- 4. Find the average stay length for each disease.
SELECT d.disease_name, AVG(a.stay_days) AS average_stay_days
FROM diseases AS d
JOIN admissions AS a ON a.disease_id = d.disease_id
GROUP BY d.disease_id, d.disease_name
ORDER BY d.disease_name;

-- 5. Count each doctor's admissions as a simple workload measure.
SELECT doc.doctor_name, COUNT(a.admission_id) AS admission_count
FROM doctors AS doc
LEFT JOIN admissions AS a ON a.doctor_id = doc.doctor_id
GROUP BY doc.doctor_id, doc.doctor_name
ORDER BY admission_count DESC, doc.doctor_name;
