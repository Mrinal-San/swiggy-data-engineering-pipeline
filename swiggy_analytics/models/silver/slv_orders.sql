
with source_data as (

    select *
    from {{ source('swiggy_bronze', 'orders') }}

),

cleaned as (

    select
        order_id,
        order_timestamp as order_timestamp_raw,
        try_cast(
            nullif(trim(order_timestamp), '') as timestamp
        ) as order_timestamp,

        order_date as order_date_raw,
        try_cast(
            nullif(trim(order_date), '') as date
        ) as order_date,

        user_id,
        r_id as restaurant_id,
        nullif(trim(restaurant_city), '') as restaurant_city,
        nullif(trim(cuisine), '') as cuisine,

        items_count,
        sales_qty,
        subtotal,
        discount,
        delivery_fee,
        gst,
        sales_amount,
        nullif(trim(currency), '') as currency,
        nullif(trim(payment_method), '') as payment_method,
        nullif(trim(order_status), '') as order_status,
        customer_rating,
        delivery_time_min

    from source_data

)

select *
from cleaned
where order_id is not null
