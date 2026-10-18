
with restaurants as (

    select
        trim(cast(restaurant_id as varchar)) as restaurant_id,
        restaurant_name,
        city as restaurant_city,
        cuisine,
        rating as restaurant_rating,
        rating_count as restaurant_rating_count,
        cost as restaurant_cost
    from {{ ref('slv_restaurants') }}

),

orders as (

    select
        trim(cast(restaurant_id as varchar)) as restaurant_id,
        order_id,
        order_status,
        sales_amount,
        customer_rating,
        delivery_time_min
    from {{ ref('slv_orders') }}

),

restaurant_order_metrics as (

    select
        restaurant_id,

        count(distinct order_id) as total_orders,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                then order_id
            end
        ) as completed_orders,

        sum(sales_amount) as total_recorded_sales,

        sum(
            case
                when lower(trim(order_status)) = 'completed'
                then sales_amount
                else 0
            end
        ) as completed_order_sales,

        avg(
            case
                when lower(trim(order_status)) = 'completed'
                then customer_rating
            end
        ) as avg_order_customer_rating,

        avg(
            case
                when lower(trim(order_status)) = 'completed'
                then delivery_time_min
            end
        ) as avg_delivery_time_min

    from orders
    group by restaurant_id

)

select
    r.restaurant_id,
    r.restaurant_name,
    r.restaurant_city,
    r.cuisine,
    r.restaurant_rating,
    r.restaurant_rating_count,
    r.restaurant_cost,

    coalesce(m.total_orders, 0) as total_orders,
    coalesce(m.completed_orders, 0) as completed_orders,
    coalesce(m.total_recorded_sales, 0) as total_recorded_sales,
    coalesce(m.completed_order_sales, 0) as completed_order_sales,

    m.avg_order_customer_rating,
    m.avg_delivery_time_min

from restaurants r

left join restaurant_order_metrics m
    on r.restaurant_id = m.restaurant_id
