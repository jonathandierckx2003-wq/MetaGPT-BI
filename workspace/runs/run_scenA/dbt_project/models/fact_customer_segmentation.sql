SELECT
    "Customer ID" AS customer_id,
    "Location" AS us_state,
    CAST("Age" AS INTEGER) AS age,
    "Frequency of Purchases" AS purchase_frequency_segment,
    COUNT(*) AS customer_count
FROM stg_customer_details
GROUP BY
    "Customer ID",
    "Location",
    CAST("Age" AS INTEGER),
    "Frequency of Purchases"