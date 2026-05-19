SELECT DISTINCT
    "Subscription Status" AS subscription_status
FROM stg_customer_details
WHERE "Subscription Status" IS NOT NULL