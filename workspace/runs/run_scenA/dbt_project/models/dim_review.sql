SELECT DISTINCT
    CAST("Review Rating" AS DOUBLE) AS review_rating
FROM stg_customer_details
WHERE "Review Rating" IS NOT NULL