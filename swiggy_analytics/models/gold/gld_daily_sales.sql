with orders as (

    select
        order_id,
        coalesce(order_date, cast(order_timestamp as date)) as order_date,
        user_id,
        restaurant_id,
        restaurant_city,
        cuisine,
        items_count,
        sales_qty,
        subtotal,
        discount,
        delivery_fee,
        gst,
        sales_amount,
        currency,
        order_status,
        customer_rating,
        delivery_time_min

    from {{ ref('slv_orders') }}

),

daily_sales as (

    select
        order_date,
        restaurant_city,
        cuisine,
        currency,

        -- Order metrics
        count(distinct order_id) as total_orders,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                then order_id
            end
        ) as completed_orders,

        -- Item metrics
        sum(coalesce(items_count, 0)) as total_items,
        sum(coalesce(sales_qty, 0)) as total_quantity,

        -- Financial metrics
        sum(coalesce(subtotal, 0)) as total_subtotal,
        sum(coalesce(discount, 0)) as total_discount,
        sum(coalesce(delivery_fee, 0)) as total_delivery_fee,
        sum(coalesce(gst, 0)) as total_gst,

        sum(coalesce(sales_amount, 0)) as total_sales,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then coalesce(sales_amount, 0)
                else 0
            end
        ) as completed_order_sales,

        -- Average order value across all recorded orders
        cast(
            sum(coalesce(sales_amount, 0)) /
            nullif(count(distinct order_id), 0)
            as double
        ) as average_order_value,

        -- Operational metrics
        avg(try_cast(delivery_time_min as double))
            as avg_delivery_time_min,

        avg(try_cast(customer_rating as double))
            as avg_customer_rating

    from orders

    where order_date is not null

    group by
        order_date,
        restaurant_city,
        cuisine,
        currency

)

select *
from daily_sales