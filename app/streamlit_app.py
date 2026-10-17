from datetime import date, timedelta
from pathlib import Path
import re
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from text_to_sql import execute_sql, generate_sql, validate_sql


st.set_page_config(
    page_title="Swiggy | Data intelligence",
    page_icon=":material/restaurant:",
    layout="wide",
    initial_sidebar_state="expanded",
)

BRAND_ORANGE = "#FC8019"
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "swiggy_wordmark.svg"
MARK_PATH = Path(__file__).resolve().parent / "assets" / "swiggy_mark.svg"
DAILY_TABLE = '"swiggy_gold"."gld_daily_sales"'
RESTAURANT_TABLE = '"swiggy_gold"."gld_restaurant_performance"'
MAX_DASHBOARD_ROWS = 500

st.logo(str(LOGO_PATH), size="large", icon_image=str(MARK_PATH))

SUGGESTIONS = {
    "Top completed restaurants": "Show the top 10 restaurants by completed sales",
    "Compare city sales": "Compare sales across cities",
    "Weekly sales trend": "Show weekly sales by date",
    "Order performance": "Compare completed orders and total orders",
}


@st.cache_data(ttl=300, max_entries=64)
def run_dashboard_query(sql: str, max_rows: int = MAX_DASHBOARD_ROWS) -> pd.DataFrame:
    return pd.DataFrame(execute_sql(sql, max_rows=max_rows))


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def generate_sql_cached(question: str) -> str:
    return generate_sql(question)


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def run_chat_query(sql: str) -> list[dict]:
    return execute_sql(sql)


def clear_cached_data() -> None:
    run_dashboard_query.clear()
    generate_sql_cached.clear()
    run_chat_query.clear()


def format_currency(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        number = 0
    return f"INR {float(number):,.2f}"


def get_number(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame:
        return 0.0
    value = pd.to_numeric(frame.iloc[0][column], errors="coerce")
    return 0.0 if pd.isna(value) else float(value)


def get_source_tables(sql: str) -> list[str]:
    tables = re.findall(
        r'(?i)"swiggy_gold"\s*\.\s*"(gld_daily_sales|gld_restaurant_performance)"',
        sql,
    )
    return list(dict.fromkeys(f"swiggy_gold.{name}" for name in tables))


def render_message(message: dict) -> None:
    avatar = ":material/auto_awesome:" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message.get("source"):
            st.caption(f"Athena source: {message['source']}")
        if message.get("data") is not None:
            result_df = pd.DataFrame(message["data"])
            if result_df.empty:
                st.caption("No rows returned.")
            else:
                st.dataframe(
                    result_df,
                    hide_index=True,
                    width="stretch",
                    alt="Read-only Athena query results",
                )
        if message.get("sql"):
            with st.expander("View generated SQL"):
                st.code(message["sql"], language="sql")


def render_chat() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.title("AI data analyst", icon=":material/auto_awesome:")
    st.caption(
        "Ask a business question. The assistant drafts a query, checks its scope, "
        "and runs it against the approved Athena Gold tables."
    )
    st.badge("Read-only · Gold data", color="orange")

    for message in st.session_state.messages:
        render_message(message)

    prompt = st.chat_input("Ask about sales, orders, restaurants, or cuisine")
    if not st.session_state.messages:
        suggestion_slot = st.empty()
        selected = suggestion_slot.pills(
            "Try a question",
            options=list(SUGGESTIONS),
            label_visibility="collapsed",
            key="chat_suggestions",
        )
        if selected:
            prompt = SUGGESTIONS[selected]
    else:
        suggestion_slot = None

    if not prompt:
        return

    if suggestion_slot is not None:
        suggestion_slot.empty()

    prompt = prompt.strip()
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    started_at = time.perf_counter()
    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        try:
            with st.status(
                ":shimmer[Working through your request]",
                type="compact",
            ) as workflow:
                with st.status("Scope to approved Gold data", type="step"):
                    st.caption(
                        "Available tables: gld_daily_sales and "
                        "gld_restaurant_performance."
                    )

                with st.status("Draft SQL with Gemini", type="step"):
                    draft_sql = generate_sql_cached(prompt)

                with st.status("Validate read-only query and table access", type="step"):
                    sql = validate_sql(draft_sql)

                with st.status("Run query on Amazon Athena", type="step"):
                    results = run_chat_query(sql)

                elapsed = time.perf_counter() - started_at
                workflow.update(
                    label=f"Completed in {elapsed:.1f}s · {len(results)} rows",
                    state="complete",
                )

            sources = get_source_tables(sql)
            source_text = ", ".join(sources) if sources else "approved Gold tables"
            answer = f"Athena returned {len(results)} row(s) from {source_text}."
            st.markdown(answer)
            st.caption("Review the SQL and returned data before using them for decisions.")

            if results:
                st.dataframe(
                    pd.DataFrame(results),
                    hide_index=True,
                    width="stretch",
                    alt="Read-only Athena query results",
                )
            else:
                st.caption("No rows matched that question.")

            with st.expander("View generated SQL"):
                st.code(sql, language="sql")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "source": source_text,
                    "sql": sql,
                    "data": results,
                }
            )
        except Exception as exc:
            answer = "I could not complete this analysis. Check the query setup and try again."
            st.error(answer, icon=":material/cloud_off:")
            with st.expander("Technical details"):
                st.code(str(exc))
            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )


def date_filter(start_date: date, end_date: date) -> str:
    # Values come from Streamlit's date_input and are rendered as ISO dates.
    return (
        f"order_date BETWEEN DATE '{start_date.isoformat()}' "
        f"AND DATE '{end_date.isoformat()}'"
    )


def render_sales_chart(data: pd.DataFrame) -> None:
    if data.empty:
        st.info("No weekly sales were found for this date range.")
        return

    data = data.copy()
    data["week_start"] = pd.to_datetime(data["week_start"], errors="coerce")
    data["recorded_sales"] = pd.to_numeric(data["recorded_sales"], errors="coerce")
    data = data.dropna(subset=["week_start", "recorded_sales"]).sort_values("week_start")
    if data.empty:
        st.info("No valid sales dates were returned for this date range.")
        return

    figure = px.area(
        data,
        x="week_start",
        y="recorded_sales",
        markers=True,
        color_discrete_sequence=[BRAND_ORANGE],
        labels={"week_start": "Week", "recorded_sales": "Recorded sales (INR)"},
    )
    figure.update_traces(line_width=2, fillcolor="rgba(252, 128, 25, 0.16)")
    figure.update_layout(
        height=330,
        hovermode="x unified",
        showlegend=False,
        plot_bgcolor="rgba(0, 0, 0, 0)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=8, r=8, t=16, b=8),
        yaxis=dict(tickprefix="INR ", separatethousands=True, title=None),
        xaxis=dict(title=None),
    )
    st.plotly_chart(figure, width="stretch", alt="Weekly recorded sales in INR")


def render_segment_chart(data: pd.DataFrame, segment_type: str, title: str) -> None:
    if data.empty or "segment_type" not in data:
        st.info(f"No {title.lower()} sales were found for this date range.")
        return
    segment = data[data["segment_type"] == segment_type].copy()
    if segment.empty:
        st.info(f"No {title.lower()} sales were found for this date range.")
        return

    segment["recorded_sales"] = pd.to_numeric(
        segment["recorded_sales"], errors="coerce"
    )
    segment = segment.dropna(subset=["recorded_sales"]).sort_values("recorded_sales")
    figure = px.bar(
        segment,
        x="recorded_sales",
        y="segment_name",
        orientation="h",
        color_discrete_sequence=[BRAND_ORANGE],
        labels={"recorded_sales": "Recorded sales (INR)", "segment_name": title},
    )
    figure.update_layout(
        height=330,
        showlegend=False,
        plot_bgcolor="rgba(0, 0, 0, 0)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=8, r=8, t=16, b=8),
        xaxis=dict(tickprefix="INR ", separatethousands=True, title=None),
        yaxis=dict(title=None),
    )
    st.plotly_chart(figure, width="stretch", alt=f"Recorded sales by {title.lower()}")


def render_analytics() -> None:
    st.title("Business overview", icon=":material/monitoring:")
    st.caption(
        "Explore order sales from Athena Gold data. Every KPI and chart below "
        "is queried from the project tables."
    )
    st.badge("Source · swiggy_gold", color="orange")

    bounds_sql = f"""
        SELECT
            CAST(MIN(order_date) AS VARCHAR) AS first_order_date,
            CAST(MAX(order_date) AS VARCHAR) AS last_order_date
        FROM {DAILY_TABLE}
        WHERE currency = 'INR'
    """

    try:
        with st.spinner("Checking the available order-date range in Athena..."):
            bounds = run_dashboard_query(bounds_sql, max_rows=1)
        if bounds.empty or pd.isna(bounds.iloc[0].get("first_order_date")):
            st.info(
                "The Gold sales table has no INR order dates to display.",
                icon=":material/info:",
            )
            return

        first_date = pd.to_datetime(bounds.iloc[0]["first_order_date"]).date()
        last_date = pd.to_datetime(bounds.iloc[0]["last_order_date"]).date()
    except Exception as exc:
        st.error(
            "The analytics dashboard could not read its Athena date range.",
            icon=":material/cloud_off:",
        )
        with st.expander("Technical details"):
            st.code(str(exc))
        return

    if first_date > last_date:
        st.info("No usable order-date range is available in the Gold table.")
        return

    default_start = max(first_date, last_date - timedelta(days=29))
    applied_range = st.session_state.get("analytics_date_range")
    if (
        not isinstance(applied_range, tuple)
        or len(applied_range) != 2
        or applied_range[0] < first_date
        or applied_range[1] > last_date
    ):
        applied_range = (default_start, last_date)
        st.session_state.analytics_date_range = applied_range

    with st.form("analytics_filters", border=True):
        filter_col, action_col = st.columns([3, 1], vertical_alignment="bottom")
        with filter_col:
            selected_range = st.date_input(
                "Order date range",
                value=applied_range,
                min_value=first_date,
                max_value=last_date,
                format="YYYY-MM-DD",
                help="The sales KPIs and breakdown charts use this date range.",
            )
        with action_col:
            apply_filter = st.form_submit_button(
                "Apply filters",
                type="primary",
                icon=":material/filter_alt:",
                width="stretch",
            )

    if apply_filter:
        if not isinstance(selected_range, tuple) or len(selected_range) != 2:
            st.warning("Select both a start date and an end date.")
            return
        st.session_state.analytics_date_range = selected_range
        applied_range = selected_range

    start_date, end_date = applied_range
    period_filter = date_filter(start_date, end_date)
    st.caption(
        f"Order dates: {start_date:%d %b %Y} to {end_date:%d %b %Y} · "
        "Currency: INR · query results cached for up to 5 minutes"
    )

    summary_sql = f"""
        SELECT
            COALESCE(SUM(total_sales), 0) AS recorded_sales,
            COALESCE(SUM(total_orders), 0) AS order_count
        FROM {DAILY_TABLE}
        WHERE currency = 'INR'
          AND {period_filter}
    """
    trend_sql = f"""
        SELECT
            CAST(DATE_TRUNC('week', order_date) AS VARCHAR) AS week_start,
            COALESCE(SUM(total_sales), 0) AS recorded_sales
        FROM {DAILY_TABLE}
        WHERE currency = 'INR'
          AND {period_filter}
        GROUP BY DATE_TRUNC('week', order_date)
        ORDER BY DATE_TRUNC('week', order_date) DESC
        LIMIT {MAX_DASHBOARD_ROWS}
    """
    segment_sql = f"""
        WITH city_sales AS (
            SELECT
                'City' AS segment_type,
                restaurant_city AS segment_name,
                COALESCE(SUM(total_sales), 0) AS recorded_sales
            FROM {DAILY_TABLE}
            WHERE currency = 'INR'
              AND {period_filter}
              AND restaurant_city IS NOT NULL
            GROUP BY restaurant_city
            ORDER BY recorded_sales DESC
            LIMIT 10
        ),
        cuisine_sales AS (
            SELECT
                'Cuisine' AS segment_type,
                cuisine AS segment_name,
                COALESCE(SUM(total_sales), 0) AS recorded_sales
            FROM {DAILY_TABLE}
            WHERE currency = 'INR'
              AND {period_filter}
              AND cuisine IS NOT NULL
            GROUP BY cuisine
            ORDER BY recorded_sales DESC
            LIMIT 10
        )
        SELECT segment_type, segment_name, recorded_sales FROM city_sales
        UNION ALL
        SELECT segment_type, segment_name, recorded_sales FROM cuisine_sales
    """
    restaurant_sql = f"""
        WITH restaurant_rollup AS (
            SELECT
                restaurant_id,
                MAX(restaurant_name) AS restaurant_name,
                MAX(restaurant_city) AS restaurant_city,
                MAX(cuisine) AS cuisine,
                MAX(restaurant_rating) AS restaurant_rating,
                SUM(total_orders) AS total_orders,
                SUM(completed_orders) AS completed_orders,
                SUM(completed_order_sales) AS completed_order_sales
            FROM {RESTAURANT_TABLE}
            GROUP BY restaurant_id
        ),
        restaurant_stats AS (
            SELECT
                COUNT(*) AS restaurant_count,
                COUNT_IF(total_orders > 0) AS active_restaurant_count,
                AVG(restaurant_rating) AS avg_listed_rating
            FROM restaurant_rollup
        )
        SELECT
            stats.restaurant_count,
            stats.active_restaurant_count,
            stats.avg_listed_rating,
            restaurants.restaurant_name,
            restaurants.restaurant_city,
            restaurants.cuisine,
            restaurants.completed_orders,
            restaurants.completed_order_sales
        FROM restaurant_rollup AS restaurants
        CROSS JOIN restaurant_stats AS stats
        ORDER BY restaurants.completed_order_sales DESC NULLS LAST,
                 restaurants.restaurant_name
        LIMIT 10
    """

    try:
        with st.spinner("Loading Gold metrics and breakdowns from Athena..."):
            summary = run_dashboard_query(summary_sql, max_rows=1)
            trend = run_dashboard_query(trend_sql, max_rows=MAX_DASHBOARD_ROWS)
            segments = run_dashboard_query(segment_sql, max_rows=20)
            restaurants = run_dashboard_query(restaurant_sql, max_rows=10)
    except Exception as exc:
        st.error(
            "Athena could not load one or more Gold dashboard queries.",
            icon=":material/cloud_off:",
        )
        with st.expander("Technical details"):
            st.code(str(exc))
        st.caption(
            "Check access to swiggy_gold.gld_daily_sales and "
            "swiggy_gold.gld_restaurant_performance."
        )
        return

    sales = get_number(summary, "recorded_sales")
    orders = int(get_number(summary, "order_count"))
    average_order_value = sales / orders if orders else 0.0
    average_rating_value = (
        pd.to_numeric(restaurants.iloc[0]["avg_listed_rating"], errors="coerce")
        if not restaurants.empty
        else float("nan")
    )
    average_rating = (
        f"{average_rating_value:.2f} / 5"
        if pd.notna(average_rating_value)
        else "N/A"
    )
    restaurant_count = int(get_number(restaurants, "restaurant_count"))
    active_restaurant_count = int(get_number(restaurants, "active_restaurant_count"))

    metric_columns = st.columns(4)
    metrics = [
        ("Recorded sales", format_currency(sales), "INR · all order statuses"),
        ("Orders", f"{orders:,}", "Distinct order IDs summed by Gold grain"),
        (
            "Sales / Gold order count",
            format_currency(average_order_value),
            "Recorded sales ÷ summed Gold order count",
        ),
        ("Restaurant rating", average_rating, "Average listed rating · all time"),
    ]
    for column, (label, value, help_text) in zip(metric_columns, metrics):
        with column:
            st.metric(label, value, help=help_text, border=True)

    st.caption(
        f"Gold contains {restaurant_count:,} restaurants; "
        f"{active_restaurant_count:,} have recorded orders."
    )
    st.info(
        "Recorded sales include every order status and are not a settled-payment "
        "measure. The completed-sales table below uses orders whose status is "
        "completed and is an all-time view.",
        icon=":material/info:",
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Weekly recorded sales")
        st.caption("Source: swiggy_gold.gld_daily_sales · selected date range")
        render_sales_chart(trend)
    with right:
        st.subheader("Sales by city")
        st.caption("Top 10 cities · selected date range")
        render_segment_chart(segments, "City", "City")

    left, right = st.columns(2)
    with left:
        st.subheader("Sales by cuisine")
        st.caption("Top 10 cuisines · selected date range")
        render_segment_chart(segments, "Cuisine", "Cuisine")
    with right:
        st.subheader("Top restaurants by completed sales")
        st.caption(
            "Source: swiggy_gold.gld_restaurant_performance · all time · INR"
        )
        if restaurants.empty:
            st.info("No restaurant performance rows are available.")
        else:
            display = restaurants[
                [
                    "restaurant_name",
                    "restaurant_city",
                    "cuisine",
                    "completed_orders",
                    "completed_order_sales",
                ]
            ].copy()
            display["completed_orders"] = pd.to_numeric(
                display["completed_orders"], errors="coerce"
            )
            display["completed_order_sales"] = pd.to_numeric(
                display["completed_order_sales"], errors="coerce"
            )
            st.dataframe(
                display,
                hide_index=True,
                width="stretch",
                alt="Top restaurants by all-time completed-order sales",
                column_config={
                    "restaurant_name": st.column_config.TextColumn("Restaurant"),
                    "restaurant_city": st.column_config.TextColumn("City"),
                    "cuisine": st.column_config.TextColumn("Cuisine"),
                    "completed_orders": st.column_config.NumberColumn(
                        "Completed orders", format="localized"
                    ),
                    "completed_order_sales": st.column_config.NumberColumn(
                        "Completed sales (INR)", format="%.2f"
                    ),
                },
            )


with st.sidebar:
    st.caption("DATA INTELLIGENCE")
    st.divider()
    st.markdown("#### Your workspace")
    st.caption("Ask questions or explore curated business metrics.")
    st.info(
        "Prototype checks restrict generated SQL to the approved Gold tables. "
        "AWS permissions remain the access boundary.",
        icon=":material/verified_user:",
    )
    if st.button(
        "Refresh Athena data",
        icon=":material/refresh:",
        width="stretch",
        key="refresh_data",
    ):
        clear_cached_data()
        st.rerun()
    st.caption("AWS region: ap-southeast-2 · Gold schema: swiggy_gold")


with st.container(horizontal=True, vertical_alignment="center"):
    st.markdown("### Business intelligence")
    st.badge("Athena · Gold", color="orange")

view = st.segmented_control(
    "Choose a view",
    options=["Ask AI", "Analytics"],
    default="Ask AI",
    label_visibility="collapsed",
    key="main_view",
)

if view == "Analytics":
    render_analytics()
else:
    render_chat()

st.divider()
st.caption("Swiggy data assistant · Gemini + Amazon Athena · read-only Gold access")
