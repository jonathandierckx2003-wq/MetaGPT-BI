with months as (
    select distinct date_trunc('month', cast("Contract Start Date" as date)) as month_date
    from stg_hr_file_1
    where "Contract Start Date" is not null
    union
    select distinct date_trunc('month', cast("Contract End Date" as date)) as month_date
    from stg_hr_file_1
    where "Contract End Date" is not null
),
contracts as (
    select
        cast("Person ID" as varchar) as person_identifier,
        cast("Person ID" as varchar) as contract_identifier,
        cast("Contract Start Date" as date) as contract_start_date,
        cast("Contract End Date" as date) as contract_end_date,
        cast("Birth Date" as date) as birth_date,
        cast("Gender" as varchar) as gender,
        cast("Firm ID" as varchar) as region,
        cast("Department ID" as varchar) as department,
        cast("Category ID" as varchar) as category,
        cast("Contract ZIP Code" as varchar) as postal_code
    from stg_hr_file_1
    where "Person ID" is not null
),
expanded as (
    select
        m.month_date,
        c.*,
        case
            when c.birth_date is null then null
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) < 25 then 'Under 25'
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) between 25 and 34 then '25-34'
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) between 35 and 44 then '35-44'
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) between 45 and 54 then '45-54'
            else '55+'
        end as age_band,
        case
            when c.birth_date is null then null
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) < 2 then '0-1'
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) between 2 and 4 then '2-4'
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) between 5 and 9 then '5-9'
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) between 10 and 14 then '10-14'
            when cast(date_part('year', age(c.birth_date, m.month_date)) as integer) between 15 and 19 then '15-19'
            else '20+'
        end as seniority,
        case
            when upper(coalesce(c.gender, '')) in ('M', 'MALE') then 'Male'
            when upper(coalesce(c.gender, '')) in ('F', 'FEMALE') then 'Female'
            else 'Unknown'
        end as normalized_gender,
        row_number() over (partition by m.month_date, c.person_identifier order by c.contract_start_date) as rn
    from months m
    join contracts c
      on m.month_date between date_trunc('month', c.contract_start_date)
                     and date_trunc('month', coalesce(c.contract_end_date, m.month_date))
),
final as (
    select
        row_number() over (order by month_date, person_identifier) as date_key,
        row_number() over (order by person_identifier) as person_key,
        row_number() over (order by contract_identifier, contract_start_date) as contract_key,
        row_number() over (order by age_band) as age_band_key,
        row_number() over (order by seniority) as seniority_key,
        row_number() over (order by normalized_gender) as gender_key,
        row_number() over (order by region) as region_key,
        row_number() over (order by department) as department_key,
        row_number() over (order by category) as category_key,
        row_number() over (order by postal_code) as postal_code_key,
        1 as headcount_flag
    from expanded
    where rn = 1
)
select * from final