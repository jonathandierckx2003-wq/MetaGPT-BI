with source as (
    select distinct
        cast("Contract ZIP Code" as varchar) as postal_code
    from stg_hr_file_1
    where "Contract ZIP Code" is not null
),
final as (
    select
        row_number() over (order by postal_code) as postal_code_key,
        postal_code
    from source
)
select * from final