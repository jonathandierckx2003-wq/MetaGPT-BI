SELECT DISTINCT
    TRY_CAST("Time stamp" AS TIMESTAMP) AS full_date,
    EXTRACT(WEEK FROM TRY_CAST("Time stamp" AS TIMESTAMP)) AS week_number,
    EXTRACT(YEAR FROM TRY_CAST("Time stamp" AS TIMESTAMP)) AS year
FROM stg_e_commerce_sales_data
WHERE TRY_CAST("Time stamp" AS TIMESTAMP) IS NOT NULL