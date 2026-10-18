
with orders as (

    select
        user_id,
        order_id,
        order_date,
        order_timestamp,
        order_status,
        sales_amount,
        customer_rating,
        delivery_time_min

    from {{ ref('slv_orders') }}

),

customer_metrics as (

    select
        user_id,

        -- Order activity
        count(distinct order_id) as total_orders,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                then order_id
            end
        ) as completed_orders,

        count(
            distinct case
                when lower(trim(order_status)) in ('cancelled', 'canceled')
                then order_id
            end
        ) as cancelled_orders,

        -- Customer activity dates
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,

        -- Spending from completed orders only
        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then sales_amount
                else 0
            end
        ) as total_completed_spend,

        avg(
            case
                when lower(trim(order_status)) = 'completed'
                then sales_amount
            end
        ) as avg_completed_order_value,

        -- Customer experience
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
    where user_id is not null
    group by user_id

)

select *
from customer_metrics
