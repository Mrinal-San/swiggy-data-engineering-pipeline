with item_orders as (

    select
        items.food_id,
        items.order_id,
        orders.order_date,
        cast(orders.restaurant_id as varchar) as restaurant_id,
        orders.restaurant_city,
        orders.cuisine,
        orders.currency,
        lower(trim(orders.order_status)) as order_status,
        try_cast(items.quantity as integer) as quantity,
        try_cast(items.line_amount as double) as line_amount

    from {{ ref('slv_order_items') }} as items
    inner join {{ ref('slv_orders') }} as orders
        on items.order_id = orders.order_id
    where items.food_id is not null
      and orders.order_date is not null

),

named_items as (

    select
        item_orders.food_id,
        food.food_name,
        item_orders.order_date,
        item_orders.restaurant_id,
        item_orders.restaurant_city,
        item_orders.cuisine,
        item_orders.currency,
        item_orders.order_status,
        item_orders.order_id,
        item_orders.quantity,
        item_orders.line_amount

    from item_orders
    inner join {{ ref('slv_food') }} as food
        on item_orders.food_id = food.food_id

)

select
    food_id,
    food_name,
    order_date,
    restaurant_id,
    restaurant_city,
    cuisine,
    currency,
    order_status,

    sum(coalesce(quantity, 0)) as total_quantity,
    sum(
        case
            when order_status = 'completed' then coalesce(quantity, 0)
            else 0
        end
    ) as completed_quantity,
    count(distinct order_id) as total_orders,
    round(sum(coalesce(line_amount, 0)), 2) as total_item_sales,
    round(
        sum(
            case
                when order_status = 'completed' then coalesce(line_amount, 0)
                else 0
            end
        ),
        2
    ) as completed_item_sales

from named_items
group by
    food_id,
    food_name,
    order_date,
    restaurant_id,
    restaurant_city,
    cuisine,
    currency,
    order_status
