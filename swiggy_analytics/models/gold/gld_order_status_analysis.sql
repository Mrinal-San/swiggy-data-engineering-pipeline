
with orders as (

    select
        order_id,
        order_timestamp,
        order_date,
        restaurant_id,
        restaurant_city,
        cuisine,
        order_status,
        sales_amount,
        items_count,
        discount,
        delivery_fee,
        gst,
        customer_rating,
        delivery_time_min,
        currency

    from {{ ref('slv_orders') }}

),

cleaned_orders as (

    select
        order_id,
        order_date,
        restaurant_id,
        restaurant_city,
        cuisine,

        coalesce(
            nullif(lower(trim(order_status)), ''),
            'unknown'
        ) as order_status,

        sales_amount,
        items_count,
        discount,
        delivery_fee,
        gst,
        customer_rating,
        delivery_time_min,
        currency

    from orders

),

status_metrics as (

    select
        order_status,
        restaurant_city,
        currency,

        count(distinct order_id) as total_orders,

        sum(
            case
                when order_status = 'completed' then 1
                else 0
            end
        ) as completed_orders,

        sum(
            case
                when order_status = 'cancelled' then 1
                else 0
            end
        ) as cancelled_orders,

        sum(
            case
                when order_status = 'pending' then 1
                else 0
            end
        ) as pending_orders,

        sum(sales_amount) as total_recorded_sales,

        sum(
            case
                when order_status = 'completed'
                then sales_amount
                else 0
            end
        ) as completed_sales,

        sum(discount) as total_discount,
        sum(delivery_fee) as total_delivery_fee,
        sum(gst) as total_gst,

        avg(customer_rating) as avg_customer_rating,
        avg(delivery_time_min) as avg_delivery_time_min

    from cleaned_orders

    group by
        order_status,
        restaurant_city,
        currency

)

select
    order_status,
    restaurant_city,
    currency,
    total_orders,
    completed_orders,
    cancelled_orders,
    pending_orders,
    total_recorded_sales,
    completed_sales,
    total_discount,
    total_delivery_fee,
    total_gst,
    avg_customer_rating,
    avg_delivery_time_min

from status_metrics
