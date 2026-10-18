
with restaurant_details as (

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

order_metrics as (

    select
        trim(cast(restaurant_id as varchar)) as restaurant_id,

        count(distinct order_id) as total_orders,

        count(
            distinct case
                when lower(trim(order_status)) = 'completed'
                then order_id
            end
        ) as completed_orders,

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

    from {{ ref('slv_orders') }}
    group by trim(cast(restaurant_id as varchar))

),

ranked_restaurants as (

    select
        r.restaurant_id,
        r.restaurant_name,
        r.restaurant_city,
        r.cuisine,
        r.restaurant_rating,
        r.restaurant_rating_count,
        r.restaurant_cost,

        coalesce(o.total_orders, 0) as total_orders,
        coalesce(o.completed_orders, 0) as completed_orders,
        coalesce(o.completed_order_sales, 0) as completed_order_sales,

        o.avg_order_customer_rating,
        o.avg_delivery_time_min,

        row_number() over (
            order by
                coalesce(o.completed_order_sales, 0) desc,
                coalesce(o.completed_orders, 0) desc,
                r.restaurant_id
        ) as sales_rank

    from restaurant_details r

    left join order_metrics o
        on r.restaurant_id = o.restaurant_id

)

select *
from ranked_restaurants
where sales_rank <= 10
