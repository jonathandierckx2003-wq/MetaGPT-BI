with source as (
    select distinct
        cast("Firm ID" as varchar) as region
    from stg_hr_file_1
    where "Firm ID" is not null
),
final as (
    select
        row_number() over (order by region) as region_key,
        region
    from source
)
select * from final