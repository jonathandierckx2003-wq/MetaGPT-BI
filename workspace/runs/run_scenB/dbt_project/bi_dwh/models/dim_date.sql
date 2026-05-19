SELECT
    CAST(TO_CHAR(purchase_date, 'YYYYMMDD') AS INTEGER) AS date_key,
    purchase_date,
    EXTRACT(YEAR FROM purchase_date)::INTEGER AS year,
    EXTRACT(MONTH FROM purchase_date)::INTEGER AS month,
    EXTRACT(DAY FROM purchase_date)::INTEGER AS day,
    TO_CHAR(purchase_date, 'Day') AS day_of_week
FROM raw_purchases
GROUP BY purchase_date