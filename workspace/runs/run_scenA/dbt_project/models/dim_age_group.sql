SELECT DISTINCT
    CAST("Age" AS INTEGER) AS age
FROM stg_customer_details
WHERE "Age" IS NOT NULL