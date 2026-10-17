
SELECT
    menu_id,
    restaurant_id,
    food_id
FROM {{ ref('slv_menu') }}
GROUP BY
    menu_id,
    restaurant_id,
    food_id
HAVING COUNT(*) > 1
