with purchase_events as (
    select
        cast(date_trunc('day', try_cast(i."Time stamp" as timestamp)) as date) as full_date,
        trim(cast(i."user id" as varchar)) as customer_id,
        trim(cast(i."product id" as varchar)) as product_id,
        lower(trim(i."Interaction type")) as interaction_type_name,
        case when lower(trim(i."Interaction type")) = 'purchase' then 1 else 0 end as purchase_count
    from staging_interaction_raw i
    where try_cast(i."Time stamp" as timestamp) is not null
),
customer_monthly as (
    select
        d.date_key,
        c.customer_key,
        pe.customer_id,
        date_trunc('month', pe.full_date) as month_start,
        sum(pe.purchase_count) as total_purchases,
        case
            when sum(pe.purchase_count) > 1 then true
            else false
        end as returning_customer_flag,
        case
            when sum(pe.purchase_count) = 1 then true
            else false
        end as new_customer_flag,
        case
            when count(distinct pe.full_date) = 0 then 0.0
            else cast(sum(pe.purchase_count) as double) / count(distinct pe.full_date)
        end as purchase_frequency,
        avg(coalesce(cast(p.selling_price as double), 0.0)) as average_order_value
    from purchase_events pe
    left join dim_date d
        on d.full_date = pe.full_date
    left join dim_customer c
        on c.customer_id = pe.customer_id
    left join dim_product p
        on p.product_id = pe.product_id
    where pe.interaction_type_name = 'purchase'
    group by 1, 2, 3, 4
)
select
    row_number() over (order by date_key, customer_key) as customer_summary_fact_key,
    date_key,
    customer_key,
    total_purchases,
    returning_customer_flag,
    new_customer_flag,
    purchase_frequency,
    average_order_value
from customer_monthly
order by date_key, customer_key