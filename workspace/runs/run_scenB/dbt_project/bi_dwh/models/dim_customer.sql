SELECT
    id AS customer_id,
    name,
    email,
    gender,
    age,
    company,
    CASE
        WHEN company IS NOT NULL THEN 'B2B'
        ELSE 'consumer'
    END AS customer_segment
FROM raw_users