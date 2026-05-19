with source as (
    select
        id as purchase_id,
        user_id as customer_id,
        product_id,
        created_at::date as purchase_date
    from purchases
)
select
    purchase_id,
    customer_id,
    product_id,
    purchase_date
from source