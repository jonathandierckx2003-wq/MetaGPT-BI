with source as (
    select
        date_trunc('month', cast("Period" || '-01' as date)) as month_date,
        cast("FDCP" as varchar) as person_identifier,
        cast("FDCP" as varchar) as contract_identifier,
        cast("Gross Salary" as numeric) as salary_cost,
        cast("Gross Salary 108" as numeric) as salary_cost_108,
        cast("Period" as varchar) as period
    from stg_hr_file_2
    where "Period" is not null
),
final as (
    select
        row_number() over (order by month_date, person_identifier, contract_identifier) as date_key,
        row_number() over (order by person_identifier) as person_key,
        row_number() over (order by contract_identifier) as contract_key,
        null::integer as age_band_key,
        null::integer as seniority_key,
        null::integer as gender_key,
        null::integer as region_key,
        salary_cost
    from source
)
select * from final