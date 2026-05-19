with source as (
    select distinct
        cast("Person ID" as varchar) as person_identifier,
        cast("Person ID" as varchar) as individual_fdcp,
        null as person_name
    from stg_hr_file_1
    where "Person ID" is not null
),
final as (
    select
        row_number() over (order by person_identifier) as person_key,
        individual_fdcp,
        person_identifier,
        person_name
    from source
)
select * from final