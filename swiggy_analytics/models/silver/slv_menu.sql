
with source_data as (

    select
        col0, col1, col2, col3, col4, col5
    from {{ source('swiggy_bronze', 'menu') }}

),

cleaned as (

    select
        nullif(trim(col1), '') as menu_id,
        nullif(trim(col2), '') as restaurant_id,
        nullif(trim(col3), '') as food_id,
        nullif(trim(col4), '') as cuisine,
        try_cast(
            nullif(trim(col5), '') as double
        ) as price

    from source_data

)

select *
from cleaned
where menu_id is not null
  and lower(menu_id) <> 'menu_id'
