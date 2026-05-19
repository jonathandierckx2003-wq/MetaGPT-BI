with source as (
    select distinct
        cast("Category ID" as varchar) as category
    from stg_hr_file_1
    where "Category ID" is not null
),
final as (
    select
        row_number() over (order by category) as category_key,
        category
    from source
)
select * from final