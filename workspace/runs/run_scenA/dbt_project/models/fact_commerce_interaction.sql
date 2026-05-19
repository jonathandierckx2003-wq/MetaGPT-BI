SELECT
    s."user id" AS user_id,
    s."product id" AS product_id,
    s."Interaction type" AS interaction_type,
    CAST(s."Time stamp" AS TIMESTAMP) AS time_stamp,
    s."Unnamed: 4" AS extra_field,
    c.customer_id,
    p.product_id AS dim_product_id,
    se.season,
    d.full_date,
    pc.promo_code,
    r.review_rating
FROM stg_e_commerce_sales_data s
LEFT JOIN dim_customer c
    ON CAST(s."user id" AS VARCHAR) = CAST(c.customer_id AS VARCHAR)
LEFT JOIN dim_product p
    ON CAST(s."product id" AS VARCHAR) = CAST(p.product_id AS VARCHAR)
LEFT JOIN dim_season se
    ON s."Interaction type" = se.season
LEFT JOIN dim_date d
    ON CAST(s."Time stamp" AS DATE) = d.full_date
LEFT JOIN dim_promo_code pc
    ON NULL = pc.promo_code
LEFT JOIN dim_review r
    ON NULL = r.review_rating