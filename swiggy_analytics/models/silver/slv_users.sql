
with source_data as (

    select
        col0, col1, col2, col3, col4, col5,
        col6, col7, col8, col9, col10, col11
    from {{ source('swiggy_bronze', 'users') }}

),

cleaned as (

    select
        nullif(trim(col1), '') as user_id,

        try_cast(
            nullif(trim(col5), '') as integer
        ) as age,

        nullif(lower(trim(col6)), '') as gender,
        nullif(lower(trim(col7)), '') as marital_status,
        nullif(trim(col8), '') as occupation,

        try_cast(
            nullif(trim(col9), '') as double
        ) as monthly_income,

        nullif(trim(col10), '') as educational_qualification,

        try_cast(
            nullif(trim(col11), '') as integer
        ) as family_size

    from source_data

)

select *
from cleaned
where user_id is not null
  and lower(user_id) <> 'user_id'
