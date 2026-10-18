
with orders as (

    select
        nullif(trim(cast(restaurant_city as varchar)), '') as restaurant_city,
        order_id,
        order_status,
        sales_amount,
        items_count,
        sales_qty,
        subtotal,
        discount,
        delivery_fee,
        gst,
        customer_rating,
        delivery_time_min

    from {{ ref('slv_orders') }}

),

city_metrics as (

    select
        restaurant_city,

        count(distinct order_id) as total_orders,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                then order_id
            end
        ) as completed_orders,

        count(
            distinct case
                when lower(trim(order_status)) <> 'completed'
                  or order_status is null
                then order_id
            end
        ) as non_completed_orders,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then sales_amount
                else 0
            end
        ) as completed_sales,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then items_count
                else 0
            end
        ) as completed_items,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then sales_qty
                else 0
            end
        ) as completed_quantity,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then subtotal
                else 0
            end
        ) as completed_subtotal,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then discount
                else 0
            end
        ) as completed_discount,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then delivery_fee
                else 0
            end
        ) as completed_delivery_fee,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then gst
                else 0
            end
        ) as completed_gst,

        avg(
            case
                when lower(trim(order_status)) = 'completed'
                then customer_rating
            end
        ) as avg_customer_rating,

        avg(
            case
                when lower(trim(order_status)) = 'completed'
                then delivery_time_min
            end
        ) as avg_delivery_time_min

    from orders
    where restaurant_city is not null
    group by restaurant_city

)

select
    restaurant_city,
    total_orders,
    completed_orders,
    non_completed_orders,

    case
        when total_orders > 0
        then 100.0 * completed_orders / total_orders
        else 0
    end as completion_rate_pct,

    coalesce(completed_sales, 0) as completed_sales,
    coalesce(completed_items, 0) as completed_items,
    coalesce(completed_quantity, 0) as completed_quantity,
    coalesce(completed_subtotal, 0) as completed_subtotal,
    coalesce(completed_discount, 0) as completed_discount,
    coalesce(completed_delivery_fee, 0) as completed_delivery_fee,
    coalesce(completed_gst, 0) as completed_gst,

    case
        when completed_orders > 0
        then completed_sales / completed_orders
        else 0
    end as average_order_value,

    avg_customer_rating,
    avg_delivery_time_min

from city_metrics
