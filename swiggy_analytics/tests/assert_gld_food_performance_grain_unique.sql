select
    food_id,
    food_name,
    order_date,
    restaurant_id,
    restaurant_city,
    cuisine,
    currency,
    order_status
from {{ ref('gld_food_performance') }}
group by
    food_id,
    food_name,
    order_date,
    restaurant_id,
    restaurant_city,
    cuisine,
    currency,
    order_status
having count(*) > 1
