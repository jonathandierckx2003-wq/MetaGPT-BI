with source_months as (
    select distinct date_trunc('month', cast("Date" as date)) as month_date
    from stg_hr_file_3
    where "Date" is not null
    union
    select distinct date_trunc('month', cast("Period" || '-01' as date)) as month_date
    from stg_hr_file_2
    where "Period" is not null
),
calendar as (
    select
        row_number() over (order by month_date) as date_key,
        month_date as month,
        strftime(month_date, '%B') as month_name,
        extract(year from month_date)::integer as year,
        strftime(month_date, '%Y-%m') as year_month_key
    from source_months
)
select * from calendar
