
with orders as (

    select
        order_id,
        order_date,
        restaurant_city,
        cuisine,
        currency,
        order_status,

        try_cast(subtotal as double) as subtotal,
        try_cast(discount as double) as discount,
        try_cast(delivery_fee as double) as delivery_fee,
        try_cast(gst as double) as gst,
        try_cast(sales_amount as double) as sales_amount,
        try_cast(items_count as integer) as items_count,
        try_cast(sales_qty as integer) as sales_qty,
        try_cast(delivery_time_min as double) as delivery_time_min,
        try_cast(customer_rating as double) as customer_rating

    from {{ ref('slv_orders') }}

)

select
    order_date,
    restaurant_city,
    cuisine,
    currency,

    count(distinct order_id) as total_orders,
    sum(coalesce(items_count, 0)) as total_items,
    sum(coalesce(sales_qty, 0)) as total_quantity,

    round(sum(subtotal), 2) as total_subtotal,
    round(sum(coalesce(discount, 0)), 2) as total_discount,
    round(sum(coalesce(delivery_fee, 0)), 2) as total_delivery_fee,
    round(sum(coalesce(gst, 0)), 2) as total_gst,
    round(sum(sales_amount), 2) as total_sales,

    round(
        sum(sales_amount) / nullif(count(distinct order_id), 0),
        2
    ) as average_order_value,

    round(avg(delivery_time_min), 2) as avg_delivery_time_min,
    round(avg(customer_rating), 2) as avg_customer_rating

from orders
where order_date is not null

group by
    order_date,
    restaurant_city,
    cuisine,
    currency
