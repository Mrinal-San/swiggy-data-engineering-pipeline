
with orders as (

    select
        order_id,
        restaurant_id,
        restaurant_city,
        cuisine,
        order_date,
        order_status,
        delivery_time_min,
        customer_rating,
        currency

    from {{ ref('slv_orders') }}

),

delivery_metrics as (

    select
        restaurant_id,
        restaurant_city,
        cuisine,
        currency,

        count(distinct order_id) as total_orders,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                then order_id
            end
        ) as completed_orders,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                 and delivery_time_min is not null
                then order_id
            end
        ) as orders_with_delivery_time,

        avg(
            case
                when lower(trim(order_status)) = 'completed'
                then delivery_time_min
            end
        ) as avg_delivery_time_min,

        min(
            case
                when lower(trim(order_status)) = 'completed'
                then delivery_time_min
            end
        ) as min_delivery_time_min,

        max(
            case
                when lower(trim(order_status)) = 'completed'
                then delivery_time_min
            end
        ) as max_delivery_time_min,

        avg(
            case
                when lower(trim(order_status)) = 'completed'
                then customer_rating
            end
        ) as avg_customer_rating,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                 and customer_rating is not null
                then order_id
            end
        ) as orders_with_customer_rating

    from orders

    group by
        restaurant_id,
        restaurant_city,
        cuisine,
        currency

)

select
    restaurant_id,
    restaurant_city,
    cuisine,
    currency,
    total_orders,
    completed_orders,
    orders_with_delivery_time,

    round(avg_delivery_time_min, 2)
        as avg_delivery_time_min,

    min_delivery_time_min,
    max_delivery_time_min,

    round(avg_customer_rating, 2)
        as avg_customer_rating,

    orders_with_customer_rating,

    round(
        100.0 * completed_orders
        / nullif(total_orders, 0),
        2
    ) as completion_rate_pct

from delivery_metrics
