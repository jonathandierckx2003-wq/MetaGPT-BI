with interaction_base as (
    select
        cast(date_trunc('day', try_cast("Time stamp" as timestamp)) as date) as full_date,
        trim(cast("product id" as varchar)) as product_id,
        trim(cast("user id" as varchar)) as customer_id,
        lower(trim("Interaction type")) as interaction_type_name,
        case when lower(trim("Interaction type")) = 'purchase' then 1 else 0 end as purchase_count,
        case when lower(trim("Interaction type")) = 'view' then 1 else 0 end as view_count,
        case when lower(trim("Interaction type")) = 'add-to-cart' then 1 else 0 end as add_to_cart_count
    from staging_interaction_raw
    where try_cast("Time stamp" as timestamp) is not null
),
joined as (
    select
        d.date_key,
        p.product_key,
        c.customer_key,
        it.interaction_type_key,
        1 as interaction_count,
        ib.purchase_count,
        ib.view_count,
        ib.add_to_cart_count
    from interaction_base ib
    left join dim_date d
        on d.full_date = ib.full_date
    left join dim_product p
        on p.product_id = ib.product_id
    left join dim_customer c
        on c.customer_id = ib.customer_id
    left join dim_interaction_type it
        on lower(it.interaction_type_name) = ib.interaction_type_name
)
select
    row_number() over (order by date_key, product_key, customer_key, interaction_type_key) as interaction_fact_key,
    date_key,
    product_key,
    customer_key,
    interaction_type_key,
    sum(interaction_count) as interaction_count,
    sum(purchase_count) as purchase_count,
    sum(view_count) as view_count,
    sum(add_to_cart_count) as add_to_cart_count
from joined
group by 2, 3, 4, 5
order by 2, 3, 4, 5