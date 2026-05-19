with source as (
    select distinct
        case
            when upper(coalesce(cast("Gender" as varchar), '')) in ('M', 'MALE') then 'Male'
            when upper(coalesce(cast("Gender" as varchar), '')) in ('F', 'FEMALE') then 'Female'
            else 'Unknown'
        end as gender
    from stg_hr_file_1
    where "Gender" is not null
),
final as (
    select
        row_number() over (order by gender) as gender_key,
        gender
    from source
)
select * from final