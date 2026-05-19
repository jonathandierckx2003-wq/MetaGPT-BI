with source as (
    select distinct
        case
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) < 2 then '0-1'
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) between 2 and 4 then '2-4'
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) between 5 and 9 then '5-9'
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) between 10 and 14 then '10-14'
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) between 15 and 19 then '15-19'
            else '20+'
        end as seniority
    from stg_hr_file_1
    where "Birth Date" is not null
),
final as (
    select
        row_number() over (order by seniority) as seniority_key,
        seniority
    from source
)
select * from final