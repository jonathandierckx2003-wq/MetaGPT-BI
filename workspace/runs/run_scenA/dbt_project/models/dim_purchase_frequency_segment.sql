SELECT DISTINCT
    "Frequency of Purchases" AS purchase_frequency_segment
FROM stg_customer_details
WHERE "Frequency of Purchases" IS NOT NULL