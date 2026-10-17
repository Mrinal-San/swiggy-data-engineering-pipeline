
with source_data as (

    select
        col0, col1, col2, col3, col4, col5,
        col6, col7, col8, col9, col10, col11
    from {{ source('swiggy_bronze', 'restaurants') }}

),

cleaned as (

    select
        nullif(trim(col1), '') as restaurant_id,
        nullif(trim(col2), '') as restaurant_name,
        nullif(trim(col3), '') as city,

        try_cast(
            nullif(trim(col4), '') as double
        ) as rating,

        try_cast(
            nullif(trim(col5), '') as bigint
        ) as rating_count,

        try_cast(
            nullif(trim(col6), '') as double
        ) as cost,

        nullif(trim(col7), '') as cuisine,
        nullif(trim(col8), '') as licence_number,
        nullif(trim(col9), '') as restaurant_link,
        nullif(trim(col10), '') as address,
        nullif(trim(col11), '') as menu_description

    from source_data

)

select *
from cleaned
where restaurant_id is not null
  and lower(restaurant_id) <> 'id'
