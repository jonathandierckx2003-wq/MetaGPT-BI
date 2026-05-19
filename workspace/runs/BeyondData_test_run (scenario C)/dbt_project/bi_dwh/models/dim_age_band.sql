with source as (
    select distinct
        case
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) < 25 then 'Under 25'
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) between 25 and 34 then '25-34'
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) between 35 and 44 then '35-44'
            when cast(date_part('year', age(cast("Birth Date" as date), current_date)) as integer) between 45 and 54 then '45-54'
            else '55+'
        end as age_band
    from stg_hr_file_1
    where "Birth Date" is not null
),
final as (
    select
        row_number() over (order by age_band) as age_band_key,
        age_band
    from source
)
select * from final