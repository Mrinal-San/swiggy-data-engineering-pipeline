
with source_data as (

    select
        col0,
        col1,
        col2,
        col3
    from {{ source('swiggy_bronze', 'food') }}

),

cleaned as (

    select
        try_cast(col1 as varchar) as food_id,
        nullif(trim(col2), '') as food_name,
        nullif(lower(trim(col3)), '') as food_type

    from source_data

)

select *
from cleaned
where food_id is not null
  and lower(food_id) <> 'f_id'
  and food_name is not null
