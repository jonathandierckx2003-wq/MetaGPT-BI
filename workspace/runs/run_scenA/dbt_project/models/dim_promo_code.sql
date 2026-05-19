SELECT DISTINCT
    "Promo Code Used" AS promo_code
FROM stg_customer_details
WHERE "Promo Code Used" IS NOT NULL