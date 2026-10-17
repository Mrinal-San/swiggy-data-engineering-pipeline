# Swiggy Analytics dbt Project

This dbt project implements the bronze, silver, and gold layers for the Swiggy data engineering pipeline. It reads from the AWS Glue/Athena-managed source tables and produces curated models for business analysis and data quality checks.

## Project layout

- `models/bronze/` - source definitions and table metadata for the raw datasets
- `models/silver/` - cleaned and typed transformations for each core entity
- `models/gold/` - aggregated business-level models such as sales and restaurant performance
- `tests/` - custom dbt tests for business-level uniqueness and validation
- `macros/` - project macros, including schema-name generation

## Expected dbt inventory

Current Stage 1 inventory includes:

- 7 bronze sources (`food`, `menu`, `orders`, `order_items`, `restaurants`, `reviews`, `users`)
- 7 silver models
- 2 gold models: `gld_daily_sales` and `gld_restaurant_performance`
- 16 data tests, including the custom uniqueness test for menu combinations

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
