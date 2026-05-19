SELECT DISTINCT
    "Location" AS us_state
FROM stg_customer_details
WHERE "Location" IS NOT NULL