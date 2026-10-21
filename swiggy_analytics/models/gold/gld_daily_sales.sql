with item_sales as (

    select
        order_id,
        sum(coalesce(line_amount, price * quantity, price, 0)) as item_sales,
        sum(coalesce(quantity, 0)) as total_quantity,
        count(*) as total_items
    from {{ ref('slv_order_items') }}
    group by order_id

),

orders as (

    select
        o.order_id,
        coalesce(o.order_date, cast(o.order_timestamp as date)) as order_date,
        o.restaurant_city,
        o.cuisine,
        o.currency,
        o.delivery_time_min,
        o.customer_rating,
        coalesce(i.total_items, 0) as total_items,
        coalesce(i.total_quantity, 0) as total_quantity,
        coalesce(i.item_sales, 0) as total_sales
    from {{ ref('slv_orders') }} o
    left join item_sales i
        on trim(cast(o.order_id as varchar)) = trim(cast(i.order_id as varchar))

)

select
    order_date,
    restaurant_city,
    cuisine,
    currency,
    count(distinct order_id) as total_orders,
    sum(total_items) as total_items,
    sum(total_quantity) as total_quantity,
    sum(total_sales) as total_sales,
    cast(sum(total_sales) / nullif(count(distinct order_id), 0) as double) as average_order_value,
    avg(try_cast(delivery_time_min as double)) as avg_delivery_time_min,
    avg(try_cast(customer_rating as double)) as avg_customer_rating
from orders
where order_date is not null
group by order_date, restaurant_city, cuisine, currency
