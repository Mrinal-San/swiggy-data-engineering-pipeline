# Swiggy Analytics dbt Project

This dbt project implements the bronze, silver, and gold layers for the Swiggy data engineering pipeline. It reads from the AWS Glue/Athena-managed source tables and produces curated models for business analysis and data quality checks.

## Project layout

- `models/bronze/` - source definitions and table metadata for the raw datasets
- `models/silver/` - cleaned and typed transformations for each core entity
- `models/gold/` - aggregated sales, restaurant, customer, rating, delivery, order-status, city, and cuisine models
- `tests/` - custom dbt tests for business-level uniqueness and validation
- `macros/` - project macros, including schema-name generation

## Expected dbt inventory

Current project inventory includes:

- 7 bronze sources (`food`, `menu`, `orders`, `order_items`, `restaurants`, `reviews`, `users`)
- 7 silver models
- 9 gold models covering daily sales, restaurants, customers, ratings, delivery, order status, cities, and cuisines
- Schema tests and custom tests for menu-combination uniqueness

The Gold models aggregate order data from the cleaned Silver layer. Dashboard sales charts use date-filtered daily sales; customer, restaurant, delivery, and order-status metrics are aggregate models.

## dbt profile configuration

The project is configured to use an external dbt profile stored in `%USERPROFILE%\.dbt\profiles.yml` rather than inside the repository. The current active profile is `swiggy_analytics` with the Athena target configured for the `ap-southeast-2` region and the `primary` workgroup.

## Useful commands

From the repository root, run:

```bash
dbt debug --profiles-dir "%USERPROFILE%\.dbt"
dbt run --profiles-dir "%USERPROFILE%\.dbt"
dbt test --profiles-dir "%USERPROFILE%\.dbt"
```

If you want to target the project directory explicitly:

```bash
dbt run --project-dir swiggy_analytics --profiles-dir "%USERPROFILE%\.dbt"
dbt test --project-dir swiggy_analytics --profiles-dir "%USERPROFILE%\.dbt"
```

## Security and data handling

- Raw datasets are intentionally not stored in Git and should never be committed.
- Customer details, especially in the `users` dataset, must remain outside the repository and should not appear in logs, SQL examples, or documentation.
- The silver `slv_users` model excludes sensitive fields and retains only safe user attributes.
