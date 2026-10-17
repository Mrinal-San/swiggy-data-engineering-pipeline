
with source_data as (

    select *
    from {{ source('swiggy_bronze', 'order_items') }}

),

cleaned as (

    select
        nullif(trim(cast(order_item_id as varchar)), '') as order_item_id,
        nullif(trim(cast(order_id as varchar)), '') as order_id,
        nullif(trim(cast(r_id as varchar)), '') as restaurant_id,
        nullif(trim(cast(f_id as varchar)), '') as food_id,

        try_cast(
            nullif(trim(cast(price as varchar)), '') as double
        ) as price,

        try_cast(
            nullif(trim(cast(quantity as varchar)), '') as integer
        ) as quantity,

        try_cast(
            nullif(trim(cast(line_amount as varchar)), '') as double
        ) as line_amount

    from source_data

)

select *
from cleaned
where order_item_id is not null
  and lower(order_item_id) <> 'order_item_id'
