with source as (
    select
        cast("Person ID" as varchar) as person_identifier,
        cast("Person ID" as varchar) as person_key_source,
        cast("Qty_Illness_Days" as numeric) as illness_days,
        cast("Freq_Z0_Days" as numeric) as freq_z0_days,
        cast("Freq_Z1_Days" as numeric) as freq_z1_days,
        cast("Freq_Z2_Days" as numeric) as freq_z2_days,
        cast("Freq_Z3_Daqs" as numeric) as freq_z3_days,
        cast("Freq_P0_Days" as numeric) as freq_p0_days,
        cast("Freq_P1_Days" as numeric) as freq_p1_days,
        cast("Freq_P2_Days" as numeric) as freq_p2_days,
        cast("Freq_P3_Days" as numeric) as freq_p3_days,
        cast("Freq_A1_Days" as numeric) as freq_a1_days,
        cast("Freq_A2_Days" as numeric) as freq_a2_days
    from stg_hr_file_3
    where "Person ID" is not null
),
final as (
    select
        row_number() over (order by person_identifier) as person_key,
        person_identifier,
        coalesce((freq_z0_days + freq_z1_days + freq_z2_days + freq_z3_days + freq_p0_days + freq_p1_days + freq_p2_days + freq_p3_days + freq_a1_days + freq_a2_days), 0) as bradford_index
    from source
    group by person_identifier, freq_z0_days, freq_z1_days, freq_z2_days, freq_z3_days, freq_p0_days, freq_p1_days, freq_p2_days, freq_p3_days, freq_a1_days, freq_a2_days
)
select * from final