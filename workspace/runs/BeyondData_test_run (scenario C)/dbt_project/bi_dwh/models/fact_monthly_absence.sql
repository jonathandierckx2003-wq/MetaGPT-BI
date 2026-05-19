with source as (
    select
        date_trunc('month', cast("Date" as date)) as month_date,
        cast("Person ID" as varchar) as person_identifier,
        cast("Firm ID" as varchar) as region,
        cast("Category ID" as varchar) as postal_code,
        cast("Period" as varchar) as period,
        cast("Qty_Illness_Days" as numeric) as absence_days,
        cast("Qty_Z0_Days" as numeric) as qty_z0_days,
        cast("Qty_Z1_Days" as numeric) as qty_z1_days,
        cast("Qty_Z2_Days" as numeric) as qty_z2_days,
        cast("Qty_Z3_Days" as numeric) as qty_z3_days,
        cast("Qty_P0_Days" as numeric) as qty_p0_days,
        cast("Qty_P1_Days" as numeric) as qty_p1_days,
        cast("Qty_P2_Days" as numeric) as qty_p2_days,
        cast("Qty_P3_Days" as numeric) as qty_p3_days,
        cast("Qty_A1_Days" as numeric) as qty_a1_days,
        cast("Qty_A2_Days" as numeric) as qty_a2_days,
        cast("Type_Absence" as varchar) as absence_type
    from stg_hr_file_3
    left join stg_hr_file_6
      on 1 = 1
    where "Date" is not null
),
final as (
    select
        row_number() over (order by month_date, person_identifier) as date_key,
        row_number() over (order by person_identifier) as person_key,
        null::integer as age_band_key,
        row_number() over (order by region) as region_key,
        row_number() over (order by postal_code) as postal_code_key,
        row_number() over (order by absence_type) as absence_type_key,
        row_number() over (order by period) as period_key,
        absence_days
    from source
)
select * from final