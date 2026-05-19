with source as (
    select distinct
        cast("Period" as varchar) as period
    from stg_hr_file_3
    where "Period" is not null
),
final as (
    select
        row_number() over (order by period) as period_key,
        period
    from source
)
select * from final