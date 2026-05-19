with source as (
    select
        cast("Person ID" as varchar) as person_identifier,
        cast("Person ID" as varchar) as contract_identifier,
        cast("Contract Start Date" as date) as contract_start_date,
        cast("Contract End Date" as date) as contract_end_date
    from stg_hr_file_1
    where "Person ID" is not null
),
months as (
    select distinct date_trunc('month', cast("Contract Start Date" as date)) as month_date
    from stg_hr_file_1
    where "Contract Start Date" is not null
    union
    select distinct date_trunc('month', cast("Contract End Date" as date)) as month_date
    from stg_hr_file_1
    where "Contract End Date" is not null
),
movement as (
    select
        m.month_date,
        s.person_identifier,
        s.contract_identifier,
        s.contract_start_date,
        case when date_trunc('month', s.contract_start_date) = m.month_date then 1 else 0 end as in_count,
        case when date_trunc('month', s.contract_end_date) = m.month_date then 1 else 0 end as out_count
    from months m
    join source s
      on m.month_date between date_trunc('month', s.contract_start_date)
                     and coalesce(date_trunc('month', s.contract_end_date), m.month_date)
),
final as (
    select
        row_number() over (order by month_date, person_identifier, contract_identifier) as date_key,
        row_number() over (order by person_identifier) as person_key,
        row_number() over (order by contract_identifier, contract_start_date) as contract_key,
        sum(in_count) as in_count,
        sum(out_count) as out_count
    from movement
    group by month_date, person_identifier, contract_identifier, contract_start_date
)
select * from final