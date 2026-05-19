with source as (
    select distinct
        cast("Department ID" as varchar) as department
    from stg_hr_file_1
    where "Department ID" is not null
),
final as (
    select
        row_number() over (order by department) as department_key,
        department
    from source
)
select * from final