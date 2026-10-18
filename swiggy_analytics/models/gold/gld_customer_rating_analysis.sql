
with orders as (

    select
        order_id,
        trim(cast(restaurant_id as varchar)) as restaurant_id,
        try_cast(customer_rating as double) as customer_rating,
        try_cast(delivery_time_min as double) as delivery_time_min,
        lower(trim(order_status)) as order_status,
        try_cast(order_date as date) as order_date

    from {{ ref('slv_orders') }}

),

restaurants as (

    select
        trim(cast(restaurant_id as varchar)) as restaurant_id,
        restaurant_name,
        city as restaurant_city,
        cuisine

    from {{ ref('slv_restaurants') }}

),

rating_metrics as (

    select
        restaurant_id,

        count(distinct order_id) as total_orders,

        count(
            distinct case
                when order_status = 'completed'
                then order_id
            end
        ) as completed_orders,

        count(
            distinct case
                when order_status = 'completed'
                 and customer_rating between 1 and 5
                then order_id
            end
        ) as rated_orders,

        count(
            distinct case
                when order_status = 'completed'
                 and customer_rating is null
                then order_id
            end
        ) as unrated_orders,

        avg(
            case
                when order_status = 'completed'
                 and customer_rating between 1 and 5
                then customer_rating
            end
        ) as avg_customer_rating,

        count(
            distinct case
                when order_status = 'completed'
                 and customer_rating = 1
                then order_id
            end
        ) as rating_1_count,

        count(
            distinct case
                when order_status = 'completed'
                 and customer_rating = 2
                then order_id
            end
        ) as rating_2_count,

        count(
            distinct case
                when order_status = 'completed'
                 and customer_rating = 3
                then order_id
            end
        ) as rating_3_count,

        count(
            distinct case
                when order_status = 'completed'
                 and customer_rating = 4
                then order_id
            end
        ) as rating_4_count,

        count(
            distinct case
                when order_status = 'completed'
                 and customer_rating = 5
                then order_id
            end
        ) as rating_5_count,

        avg(
            case
                when order_status = 'completed'
                 and customer_rating between 1 and 5
                then delivery_time_min
            end
        ) as avg_delivery_time_min,

        min(order_date) as first_order_date,
        max(order_date) as last_order_date

    from orders
    group by restaurant_id

)

select
    r.restaurant_id,
    r.restaurant_name,
    r.restaurant_city,
    r.cuisine,

    coalesce(m.total_orders, 0) as total_orders,
    coalesce(m.completed_orders, 0) as completed_orders,
    coalesce(m.rated_orders, 0) as rated_orders,
    coalesce(m.unrated_orders, 0) as unrated_orders,

    m.avg_customer_rating,

    coalesce(m.rating_1_count, 0) as rating_1_count,
    coalesce(m.rating_2_count, 0) as rating_2_count,
    coalesce(m.rating_3_count, 0) as rating_3_count,
    coalesce(m.rating_4_count, 0) as rating_4_count,
    coalesce(m.rating_5_count, 0) as rating_5_count,

    m.avg_delivery_time_min,
    m.first_order_date,
    m.last_order_date

from restaurants r

left join rating_metrics m
    on r.restaurant_id = m.restaurant_id
