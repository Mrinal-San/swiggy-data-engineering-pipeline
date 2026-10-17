
with source_data as (

    select *
    from {{ source('swiggy_bronze', 'reviews') }}

),

cleaned as (

    select
        nullif(trim(cast(review_id as varchar)), '') as review_id,
        nullif(trim(cast(order_id as varchar)), '') as order_id,
        nullif(trim(cast(user_id as varchar)), '') as user_id,
        nullif(trim(cast(restaurant_id as varchar)), '') as restaurant_id,

        try_cast(
            nullif(trim(cast(rating as varchar)), '') as integer
        ) as rating,

        nullif(trim(cast(comment as varchar)), '') as review_comment,

        try_cast(
            nullif(trim(cast(review_date as varchar)), '') as date
        ) as review_date

    from source_data

)

select *
from cleaned
where review_id is not null
  and lower(review_id) <> 'review_id'
