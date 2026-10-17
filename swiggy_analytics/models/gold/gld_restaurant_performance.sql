
with orders as (

    select
        order_id,
        cast(restaurant_id as varchar) as restaurant_id,
        restaurant_city,
        order_status,
        try_cast(sales_amount as double) as sales_amount,
        try_cast(customer_rating as double) as customer_rating,
        try_cast(delivery_time_min as double) as delivery_time_min

    from {{ ref('slv_orders') }}

),

order_metrics as (

    select
        restaurant_id,
        restaurant_city,

        count(distinct order_id) as total_orders,

        count_if(
            lower(trim(order_status)) = 'completed'
        ) as completed_orders,

        round(sum(sales_amount), 2) as total_recorded_sales,

        round(
            sum(
                case
                    when lower(trim(order_status)) = 'completed'
                    then sales_amount
                end
            ),
            2
        ) as completed_order_sales,

        round(avg(customer_rating), 2) as avg_order_customer_rating,
        round(avg(delivery_time_min), 2) as avg_delivery_time_min

    from orders
    where restaurant_id is not null

    group by
        restaurant_id,
        restaurant_city

),

restaurants as (

    select
        cast(restaurant_id as varchar) as restaurant_id,
        restaurant_name,
        city,
        try_cast(rating as double) as restaurant_rating,
        try_cast(rating_count as bigint) as restaurant_rating_count,
        try_cast(cost as double) as restaurant_cost,
        cuisine

    from {{ ref('slv_restaurants') }}

)

select
    r.restaurant_id,
    r.restaurant_name,
    coalesce(m.restaurant_city, r.city) as restaurant_city,
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

left join order_metrics m
    on r.restaurant_id = m.restaurant_id
