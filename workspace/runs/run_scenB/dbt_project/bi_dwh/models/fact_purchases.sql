SELECT
    p.id AS purchase_id,
    p.customer_id,
    p.product_id,
    p.store_name,
    d.date_key,
    p.quantity,
    p.revenue
FROM raw_purchases AS p
LEFT JOIN dim_date AS d
    ON p.purchase_date = d.purchase_date
LEFT JOIN dim_customer AS c
    ON p.customer_id = c.customer_id
LEFT JOIN dim_product AS pr
    ON p.product_id = pr.product_id
LEFT JOIN dim_store AS s
    ON p.store_name = s.store_name