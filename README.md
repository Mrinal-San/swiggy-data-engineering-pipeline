# Swiggy Data Engineering Pipeline

An AWS and dbt analytics pipeline with a Streamlit interface for exploring curated Swiggy data. The project uses Amazon S3 for storage, AWS Glue Data Catalog for table metadata, Amazon Athena for SQL execution, and Google Gemini to turn natural-language questions into draft queries.

> **Project status:** The code and local datasets are present in this workspace. AWS resources, data uploads, and live query results are account-specific and must be verified in your environment. The project has no scheduler or production deployment.

## Overview

The pipeline follows a raw, Silver, and Gold flow:

1. CSV files are stored in S3 under `raw/`.
2. Glue Data Catalog tables describe the files for Athena.
3. dbt builds cleaned Silver views and analytics-oriented Gold tables.
4. The Streamlit application queries verified Gold tables for its dashboard and analytics sections. The AI Data Assistant uses the approved Gold-table allowlist.

The application does not load the large CSV files into memory. It sends SQL to Athena and displays the returned results.

![Swiggy Data Engineering Pipeline architecture](docs/architecture.png)

*Architecture image retained for now; replace `docs/architecture.png` when the updated diagram is ready.*

## What's included

| Area | Implementation |
|---|---|
| Source data | Seven CSV datasets: food, menu, orders, order items, restaurants, reviews, and users |
| Bronze | dbt source definitions for seven Glue Catalog tables in `swiggy_bronze` |
| Silver | Seven dbt views in `swiggy_silver`, including a users model that excludes names, emails, and passwords |
| Gold | Daily sales, restaurant performance, customer, rating, delivery, order-status, city, cuisine, and top-restaurant analytics models in `swiggy_gold` |
| Data quality | dbt schema tests and a custom test for duplicate menu combinations |
| Application | Swiggy-branded Streamlit dashboard, analytics sections, and Gemini-powered AI Data Assistant |
| Orchestration | Not included; data upload, dbt runs, and refreshes are manual |

SQL is parsed with SQLGlot and constrained to read-only queries over approved Gold tables and columns. AWS IAM remains the access-control boundary; review this learning project before production use. Sales fields describe recorded order amounts and should not be treated as settled payments without a separate business definition.

## Repository layout

```text
.
├── app/                         # Streamlit, controlled analytics agent, Gemini/Athena
│   └── assets/                  # Swiggy wordmark and app icon (SVG)
├── data/raw/                    # Local CSV inputs; excluded from Git
├── docs/                        # Architecture diagram
├── glue/                        # Glue crawler setup guide
├── swiggy_analytics/            # dbt project, models, and tests
├── tests/                       # Local analytics-agent and SQL-validation tests
├── .env.example                 # Local configuration template
├── .gitignore
└── requirements.txt
```

## Requirements

- Windows with PowerShell
- Python 3.12
- AWS CLI v2 and an AWS identity authorized for the required resources
- Google AI Studio API key for the Gemini interface
- An S3 bucket, Glue Data Catalog tables, and Athena workgroup configured for your AWS account

The checked-in defaults use AWS Region `ap-southeast-2`, bucket `swiggy-pipeline-mrinal`, Athena workgroup `primary`, and query/staging prefix `s3://swiggy-pipeline-mrinal/athena-results/`. Verify these values and your access before running queries. Athena and S3 usage can incur charges.

## Local setup

From the project root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Add your Gemini key to the local `.env` file:

```dotenv
GEMINI_API_KEY=your_api_key
```

Do not commit `.env`, AWS credentials, or the local dbt profile. Configure AWS access using your organization's approved method. For an AWS CLI profile named `swiggy-dev`:

```powershell
aws sso login --profile swiggy-dev
$env:AWS_PROFILE = "swiggy-dev"
$env:AWS_DEFAULT_REGION = "ap-southeast-2"
aws sts get-caller-identity --profile $env:AWS_PROFILE --region ap-southeast-2
```

## AWS and dbt configuration

The dbt project is in `swiggy_analytics/`. Its profile is named `swiggy_analytics` and is expected at `%USERPROFILE%\.dbt\profiles.yml`. Keep the profile outside the repository. The local profile should specify the Athena adapter, catalog `awsdatacatalog`, default schema `swiggy_analytics`, workgroup `primary`, and an approved S3 staging location.

dbt source definitions expect these tables in the Glue database `swiggy_bronze`: `food`, `menu`, `orders`, `order_items`, `restaurants`, `reviews`, and `users`. The guide at [glue/crawler_setup.md](glue/crawler_setup.md) describes a crawler targeting `swiggy_raw`, so reconcile the actual Glue database and table names with dbt before running models. In particular, confirm how the S3 folder `restaurant/` maps to the catalog table `restaurants`.

The project macro directs Silver and Gold models to `swiggy_silver` and `swiggy_gold`. The `swiggy_analytics` profile schema is the default and does not mean a Glue database with that name must exist.

Before running dbt, verify the catalog tables, Athena workgroup, S3 results location, and AWS identity. Then run from PowerShell:

```powershell
$ProjectDir = Join-Path (Get-Location) "swiggy_analytics"
$ProfileDir = Join-Path $env:USERPROFILE ".dbt"

dbt debug --project-dir $ProjectDir --profiles-dir $ProfileDir
dbt compile --project-dir $ProjectDir --profiles-dir $ProfileDir
dbt run --project-dir $ProjectDir --profiles-dir $ProfileDir
dbt test --project-dir $ProjectDir --profiles-dir $ProfileDir
```

`dbt run` builds views and tables in Athena; `dbt test` executes queries as well. Both can incur costs. Start only after confirming the source tables and target schemas.

## Run the application

With `.env` and AWS access configured, run the single Streamlit entry point:

```powershell
python -m streamlit run .\app\streamlit_app.py
```

The app has separate sidebar sections for **Dashboard**, **AI Assistant**, **Restaurant Analytics**, **Customer Analytics**, **Delivery & Orders**, and **Data Status**. The Dashboard applies a selected date range and INR filter to its daily sales KPIs and date-based charts. The customer, restaurant, delivery, and order-status sections use Gold models that contain all-time aggregates; those views are labeled accordingly. The dashboard date selection and AI conversation remain in Streamlit session state while navigating between sections.

The AI Data Assistant uses the existing bounded workflow: Gemini drafts a query, SQLGlot validates one read-only statement against the approved Gold tables and columns, and Athena executes it. The app displays returned rows and may chart results with clearly meaningful time-series or category-comparison columns. Generated SQL and technical errors are available in collapsed expanders. It never executes generated Python. AI requests require `GEMINI_API_KEY`; all data views require AWS access and the corresponding Gold tables. Dashboard queries are cached for up to 5 minutes, while generated SQL and AI query results are cached for up to 60 seconds. Refreshing clears these caches and may trigger new Athena queries.

Recorded sales include all order statuses and are not a settled-payment or profit measure. Average order value is recorded sales divided by recorded orders. Restaurant rankings use completed-order sales and are all-time because `gld_restaurant_performance` is a restaurant-level aggregate without a dashboard date filter. Delivery averages are weighted by orders with a recorded delivery time. Customer summaries are all-time aggregates. The AI query allowlist follows the current Gold schemas in `app/text_to_sql.py`; it does not include removed models such as `gld_food_performance`.

An optional Gemini connectivity check is available at `app/test_openai.py` (the filename is retained for historical reasons). Running it makes an external API request and may use quota:

```powershell
python .\app\test_openai.py
```

## Validation

Run the local mocked agent and SQL-safety checks with:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .\app .\tests
```

Other useful local checks include:

```powershell
python -m pip check
dbt ls --project-dir .\swiggy_analytics --profiles-dir "$env:USERPROFILE\.dbt"
```

These checks do not prove that your AWS resources or live data are correct. Verify the Glue schemas, S3 locations, Athena workgroup, model results, and test output in your own account. Avoid scanning the full `orders` and `order_items` CSVs for exploratory work; they are large files.

## Security and cost

- Raw datasets are excluded from Git. The users dataset contains sensitive information; do not publish it or expose unnecessary personal data in models, logs, screenshots, or reports.
- Never commit `.env`, API keys, AWS credentials, or `%USERPROFILE%\.dbt\profiles.yml`.
- Use short-lived credentials and least-privilege IAM permissions where available.
- SQLGlot parsing, table and column allowlists, a 5,000-row SQL limit, and a 180-second Athena timeout constrain application queries. These controls do not replace AWS IAM or a production security review.
- Athena charges are based on data scanned. Select only needed columns, apply useful filters, and check scanned data before repeating queries.
- Keep Athena result objects private and apply suitable retention and encryption settings.

## Limitations

- AWS resource setup, source uploads, dbt execution, and app refreshes are manual.
- Glue table naming and the `swiggy_raw` versus `swiggy_bronze` database configuration must be reconciled for the target account.
- The Gemini model ID (`gemini-3.8-flash`) and AWS defaults may need updating for your account.
- The project is a learning and development implementation; it has not been security-reviewed or deployed for production.

## Cleanup

Stop Streamlit with **Ctrl+C**. To remove only the local virtual environment later, deactivate it and run:

```powershell
deactivate
Remove-Item -Recurse -Force .\.venv
```

AWS cleanup is separate. Inspect ownership, dependencies, and stored data before changing or deleting any AWS resource. Do not empty or remove buckets, databases, or tables as a routine local cleanup step.
