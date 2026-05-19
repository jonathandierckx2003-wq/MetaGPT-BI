SELECT DISTINCT
    store_name
FROM (
    SELECT store_name FROM raw_products
    UNION
    SELECT store_name FROM raw_purchases
) AS stores
WHERE store_name IS NOT NULL