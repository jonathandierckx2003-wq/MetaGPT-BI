with source as (
    select distinct
        cast("Person ID" as varchar) as contract_identifier,
        cast("Contract Start Date" as date) as contract_start_date,
        cast("Contract End Date" as date) as contract_end_date,
        case
            when "Contract End Date" is null then 'active'
            else 'ended'
        end as contract_status
    from stg_hr_file_1
    where "Person ID" is not null
),
final as (
    select
        row_number() over (order by contract_identifier, contract_start_date) as contract_key,
        contract_identifier,
        contract_start_date,
        contract_end_date,
        contract_status
    from source
)
select * from final