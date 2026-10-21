with item_sales as (
    select
        restaurant_id,
        order_id,
        sum(coalesce(line_amount, price * quantity, price, 0)) as order_item_sales
    from {{ ref('slv_order_items') }}
    group by restaurant_id, order_id
),

order_metrics as (
    select
        trim(cast(o.restaurant_id as varchar)) as restaurant_id,
        count(distinct o.order_id) as total_orders,
        sum(coalesce(i.order_item_sales, 0)) as total_sales,
        avg(o.customer_rating) as avg_order_customer_rating,
        avg(o.delivery_time_min) as avg_delivery_time_min
    from {{ ref('slv_orders') }} o
    left join item_sales i
        on trim(cast(o.restaurant_id as varchar)) = trim(cast(i.restaurant_id as varchar))
        and trim(cast(o.order_id as varchar)) = trim(cast(i.order_id as varchar))
    group by trim(cast(o.restaurant_id as varchar))
)

select
    trim(cast(r.restaurant_id as varchar)) as restaurant_id,
    r.restaurant_name,
    r.city as restaurant_city,
    r.cuisine,
    r.rating as restaurant_rating,
    r.rating_count as restaurant_rating_count,
    r.cost as restaurant_cost,
    coalesce(m.total_orders, 0) as total_orders,
    coalesce(m.total_sales, 0) as total_sales,
    m.avg_order_customer_rating,
    m.avg_delivery_time_min
from {{ ref('slv_restaurants') }} r
left join order_metrics m
    on trim(cast(r.restaurant_id as varchar)) = m.restaurant_id
