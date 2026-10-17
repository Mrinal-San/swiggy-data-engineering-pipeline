from datetime import date, timedelta
from pathlib import Path
import time
from uuid import uuid4

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics_agent import analyze_question, build_date_filter
from text_to_sql import AthenaQueryReport, execute_sql, execute_sql_report, generate_sql


st.set_page_config(
    page_title="Swiggy | Data intelligence",
    page_icon=":material/restaurant:",
    layout="wide",
    initial_sidebar_state="expanded",
)

BRAND_ORANGE = "#FC8019"
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "swiggy_wordmark.svg"
MARK_PATH = Path(__file__).resolve().parent / "assets" / "swiggy_mark.svg"
ORDERS_TABLE = '"swiggy_silver"."slv_orders"'
RESTAURANTS_TABLE = '"swiggy_silver"."slv_restaurants"'
MAX_DASHBOARD_ROWS = 500
MONEY_COLUMN_MARKERS = (
    "sales", "amount", "subtotal", "discount", "delivery_fee", "gst",
    "price", "restaurant_cost", "order_value",
)

st.logo(str(LOGO_PATH), size="large", icon_image=str(MARK_PATH))

SUGGESTIONS = {
    "Top completed restaurants": "Show the top 10 restaurants by completed sales",
    "Most selling dish": "What is the most selling dish by units sold?",
    "Compare city sales": "Compare sales across cities",
    "Weekly sales trend": "Show weekly sales by date",
    "Order performance": "Compare completed orders and total orders",
}


@st.cache_data(ttl=300, max_entries=64)
def run_dashboard_query(sql: str, max_rows: int = MAX_DASHBOARD_ROWS) -> pd.DataFrame:
    return pd.DataFrame(execute_sql(sql, max_rows=max_rows))


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def generate_sql_cached(question: str) -> tuple[str, float]:
    started = time.perf_counter()
    sql = generate_sql(question)
    return sql, time.perf_counter() - started


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def run_chat_report(sql: str, *, max_rows: int = 100) -> AthenaQueryReport:
    return execute_sql_report(sql, max_rows=max_rows)


def clear_cached_data() -> None:
    run_dashboard_query.clear()
    generate_sql_cached.clear()
    run_chat_report.clear()


def format_currency(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        number = 0
    return f"₹{float(number):,.2f}"


def format_result_frame(rows: list[dict]) -> tuple[pd.DataFrame, dict]:
    frame = pd.DataFrame(rows)
    column_config = {}
    for column in frame.columns:
        if any(marker in column.lower() for marker in MONEY_COLUMN_MARKERS):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            label = column.replace("_", " ").title()
            column_config[column] = st.column_config.NumberColumn(
                label,
                format="₹%.2f",
            )
    return frame, column_config


def get_number(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame:
        return 0.0
    value = pd.to_numeric(frame.iloc[0][column], errors="coerce")
    return 0.0 if pd.isna(value) else float(value)


def render_message(message: dict) -> None:
    avatar = ":material/auto_awesome:" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message.get("source"):
            st.caption(f"Athena source: {message['source']}")
        if message.get("data") is not None:
            result_df, result_config = format_result_frame(message["data"])
            if result_df.empty:
                st.caption("No rows returned.")
            else:
                st.dataframe(
                    result_df,
                    hide_index=True,
                    width="stretch",
                    alt="Read-only Athena query results",
                    column_config=result_config,
                )
        if message.get("sql"):
            with st.expander("View generated SQL"):
                st.code(message["sql"], language="sql")


def render_chat() -> None:
    active_chat_id = st.session_state.active_chat_id
    conversation = st.session_state.chat_history[active_chat_id]
    messages = conversation["messages"]

    st.title("AI data analyst", icon=":material/auto_awesome:")
    st.caption(
        "Ask a business question. The assistant drafts a query, checks its scope, "
        "and runs it against the approved Athena Gold tables."
    )
    st.badge("Read-only · Gold data", color="orange")

    for message_index, message in enumerate(messages):
        render_message(message)
        if message["role"] != "user":
            continue

        edit_col, _ = st.columns([1, 8])
        with edit_col:
            if st.button(
                "Edit",
                key=f"edit_chat_message_{active_chat_id}_{message_index}",
                icon=":material/edit:",
                type="tertiary",
            ):
                st.session_state.editing_message = (active_chat_id, message_index)
                st.session_state[
                    f"edited_message_{active_chat_id}_{message_index}"
                ] = message["content"]
                st.rerun()

        if st.session_state.get("editing_message") == (active_chat_id, message_index):
            with st.form(f"edit_message_form_{active_chat_id}_{message_index}"):
                edited_text = st.text_area(
                    "Edit your question",
                    key=f"edited_message_{active_chat_id}_{message_index}",
                    max_chars=1000,
                )
                save_edit = st.form_submit_button(
                    "Save and rerun",
                    type="primary",
                    icon=":material/refresh:",
                )
                cancel_edit = st.form_submit_button("Cancel")

            if save_edit:
                edited_text = edited_text.strip()
                if edited_text:
                    if message_index == 0:
                        conversation["title"] = "New chat"
                    conversation["messages"] = messages[:message_index]
                    st.session_state.pending_prompt = edited_text
                    st.session_state.editing_message = None
                    st.rerun()
                st.warning("Enter a question before saving.")
            elif cancel_edit:
                st.session_state.editing_message = None
                st.rerun()

    pending_prompt = st.session_state.pop("pending_prompt", None)
    prompt = pending_prompt or st.chat_input(
        "Ask about sales, orders, restaurants, or cuisine",
        key=f"chat_input_{active_chat_id}",
    )
    if not messages and not pending_prompt:
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
    messages.append({"role": "user", "content": prompt})
    if conversation["title"] == "New chat":
        conversation["title"] = prompt[:42] + ("…" if len(prompt) > 42 else "")
    with st.chat_message("user"):
        st.markdown(prompt)

    started_at = time.perf_counter()
    def report_progress(label: str) -> None:
        step = st.status(label, type="step")
        step.update(state="complete", expanded=False)

    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        try:
            with st.status(
                ":shimmer[Working through your request]",
                type="compact",
            ) as workflow:
                result = analyze_question(
                    prompt,
                    sql_generator=generate_sql_cached,
                    query_executor=run_chat_report,
                    on_progress=report_progress,
                )
                elapsed = time.perf_counter() - started_at
                workflow.update(
                    label=(
                        f"Completed in {elapsed:.1f}s · {len(result.rows)} rows"
                        if not result.error else "Analysis could not be completed"
                    ),
                    state="complete" if not result.error else "error",
                )

            st.markdown(result.answer)
            if result.error and result.error != "unsupported_question":
                with st.expander("Technical details"):
                    st.code(result.error)
            if result.source_tables:
                st.caption("Athena source: " + ", ".join(result.source_tables))

            report = result.query_report
            if report:
                stats = [
                    f"Gemini generation (or cached timing): {result.gemini_seconds or 0:.2f}s",
                    f"Athena execution: {report.execution_seconds:.2f}s",
                    f"Result retrieval: {report.retrieval_seconds:.2f}s",
                    f"Total response: {elapsed:.2f}s",
                ]
                if report.engine_execution_ms is not None:
                    stats.append(f"Engine: {report.engine_execution_ms / 1000:.2f}s")
                if report.data_scanned_bytes is not None:
                    stats.append(f"Scanned: {report.data_scanned_bytes:,} bytes")
                st.caption(" · ".join(stats))
                st.caption(
                    "Gemini and Athena timings may show the original request when a cached result is reused."
                )
            elif result.gemini_seconds is not None:
                st.caption(f"Gemini generation (or cached timing): {result.gemini_seconds:.2f}s")

            if result.rows:
                frame, result_config = format_result_frame(result.rows)
                if result.chart:
                    chart_data = pd.DataFrame(result.chart["data"])
                    with st.container(border=True):
                        if result.chart["kind"] == "line":
                            figure = px.line(
                                chart_data, x="x", y="y", markers=True,
                                color_discrete_sequence=[BRAND_ORANGE],
                                labels={"x": result.chart["x_label"], "y": result.chart["y_label"]},
                            )
                        else:
                            figure = px.bar(
                                chart_data, x="y", y="x", orientation="h",
                                color_discrete_sequence=[BRAND_ORANGE],
                                labels={"x": result.chart["y_label"], "y": result.chart["x_label"]},
                            )
                        figure.update_layout(
                            height=320, showlegend=False,
                            plot_bgcolor="rgba(0, 0, 0, 0)",
                            paper_bgcolor="rgba(0, 0, 0, 0)",
                            margin=dict(l=8, r=8, t=16, b=8),
                        )
                        y_label = result.chart["y_label"].lower()
                        chart_is_money = any(
                            marker in y_label for marker in MONEY_COLUMN_MARKERS
                        )
                        if chart_is_money:
                            if result.chart["kind"] == "line":
                                figure.update_yaxes(tickprefix="₹", separatethousands=True)
                            else:
                                figure.update_xaxes(tickprefix="₹", separatethousands=True)
                        st.plotly_chart(
                            figure, width="stretch", alt="Agent-selected chart from Athena results"
                        )
                st.dataframe(
                    frame, hide_index=True, width="stretch",
                    alt="Read-only Athena query results",
                    column_config=result_config,
                )
            if result.limitations:
                for limitation in result.limitations:
                    st.caption("Limit: " + limitation)

            if result.sql:
                with st.expander("View generated SQL"):
                    st.code(result.sql, language="sql")

            messages.append(
                {
                    "role": "assistant",
                    "content": result.answer,
                    "source": ", ".join(result.source_tables),
                    "sql": result.sql,
                    "data": result.rows,
                }
            )
        except Exception as exc:
            answer = "I could not complete this analysis. Check the query setup and try again."
            st.error(answer, icon=":material/cloud_off:")
            with st.expander("Technical details"):
                st.code(str(exc))
            messages.append(
                {"role": "assistant", "content": answer}
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
        labels={"week_start": "Week", "recorded_sales": "Recorded sales (₹)"},
    )
    figure.update_traces(line_width=2, fillcolor="rgba(252, 128, 25, 0.16)")
    figure.update_layout(
        height=330,
        hovermode="x unified",
        showlegend=False,
        plot_bgcolor="rgba(0, 0, 0, 0)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=8, r=8, t=16, b=8),
        yaxis=dict(tickprefix="₹", separatethousands=True, title=None),
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
        labels={"recorded_sales": "Recorded sales (₹)", "segment_name": title},
    )
    figure.update_layout(
        height=330,
        showlegend=False,
        plot_bgcolor="rgba(0, 0, 0, 0)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=8, r=8, t=16, b=8),
        xaxis=dict(tickprefix="₹", separatethousands=True, title=None),
        yaxis=dict(title=None),
    )
    st.plotly_chart(figure, width="stretch", alt=f"Recorded sales by {title.lower()}")


def initialize_chat_history() -> None:
    history = st.session_state.get("chat_history")
    if not isinstance(history, dict) or not history:
        chat_id = uuid4().hex
        history = {
            chat_id: {
                "title": "New chat",
                "messages": st.session_state.pop("messages", []),
            }
        }
        st.session_state.chat_history = history

    active_chat_id = st.session_state.get("active_chat_id")
    if active_chat_id not in history:
        active_chat_id = next(iter(history))
        st.session_state.active_chat_id = active_chat_id
    st.session_state.setdefault("chat_picker", active_chat_id)
    st.session_state.setdefault("editing_message", None)


def create_chat() -> None:
    chat_id = uuid4().hex
    st.session_state.chat_history[chat_id] = {
        "title": "New chat",
        "messages": [],
    }
    st.session_state.active_chat_id = chat_id
    st.session_state.chat_picker = chat_id
    st.session_state.editing_message = None


def delete_active_chat() -> None:
    history = st.session_state.chat_history
    chat_id = st.session_state.active_chat_id
    history.pop(chat_id, None)
    if not history:
        replacement_id = uuid4().hex
        history[replacement_id] = {"title": "New chat", "messages": []}
    replacement_id = next(reversed(history))
    st.session_state.active_chat_id = replacement_id
    st.session_state.chat_picker = replacement_id
    st.session_state.editing_message = None


def render_analytics() -> None:
    st.title("Business overview", icon=":material/monitoring:")
    st.caption(
        "Explore order and restaurant data from Athena Silver views. Every KPI and chart below "
        "is queried from the project tables."
    )
    st.badge("Source · swiggy_silver", color="orange")

    bounds_sql = f"""
        SELECT
            CAST(MIN(order_date) AS VARCHAR) AS first_order_date,
            CAST(MAX(order_date) AS VARCHAR) AS last_order_date
        FROM {ORDERS_TABLE}
        WHERE currency = 'INR'
          AND order_date IS NOT NULL
    """

    try:
        with st.spinner("Checking the available order-date range in Athena..."):
            bounds = run_dashboard_query(bounds_sql, max_rows=1)
        if bounds.empty or pd.isna(bounds.iloc[0].get("first_order_date")):
            st.info(
                "The Silver orders view has no INR order dates to display.",
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
        st.info("No usable order-date range is available in the Silver view.")
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
    period_filter = build_date_filter(start_date, end_date)
    st.caption(
        f"Order dates: {start_date:%d %b %Y} to {end_date:%d %b %Y} · "
        "Currency: INR · query results cached for up to 5 minutes"
    )

    summary_sql = f"""
        SELECT
            COALESCE(SUM(TRY_CAST(sales_amount AS DOUBLE)), 0) AS recorded_sales,
            COUNT(DISTINCT order_id) AS order_count
        FROM {ORDERS_TABLE}
        WHERE currency = 'INR'
          AND {period_filter}
    """
    trend_sql = f"""
        SELECT
            CAST(DATE_TRUNC('week', order_date) AS VARCHAR) AS week_start,
            COALESCE(SUM(TRY_CAST(sales_amount AS DOUBLE)), 0) AS recorded_sales
        FROM {ORDERS_TABLE}
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
                COALESCE(SUM(TRY_CAST(sales_amount AS DOUBLE)), 0) AS recorded_sales
            FROM {ORDERS_TABLE}
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
                COALESCE(SUM(TRY_CAST(sales_amount AS DOUBLE)), 0) AS recorded_sales
            FROM {ORDERS_TABLE}
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
        WITH order_metrics AS (
            SELECT
                CAST(restaurant_id AS VARCHAR) AS restaurant_id,
                COUNT(DISTINCT order_id) AS total_orders,
                COUNT_IF(LOWER(TRIM(order_status)) = 'completed') AS completed_orders,
                COALESCE(SUM(TRY_CAST(sales_amount AS DOUBLE)), 0) AS total_recorded_sales,
                COALESCE(SUM(CASE WHEN LOWER(TRIM(order_status)) = 'completed'
                    THEN TRY_CAST(sales_amount AS DOUBLE) ELSE 0 END), 0) AS completed_order_sales
            FROM {ORDERS_TABLE}
            WHERE currency = 'INR'
            GROUP BY CAST(restaurant_id AS VARCHAR)
        ),
        restaurant_data AS (
            SELECT
                r.restaurant_id,
                r.restaurant_name,
                r.city AS restaurant_city,
                r.cuisine,
                TRY_CAST(r.rating AS DOUBLE) AS restaurant_rating,
                COALESCE(o.total_orders, 0) AS total_orders,
                COALESCE(o.completed_orders, 0) AS completed_orders,
                COALESCE(o.total_recorded_sales, 0) AS total_recorded_sales,
                COALESCE(o.completed_order_sales, 0) AS completed_order_sales
            FROM {RESTAURANTS_TABLE} AS r
            LEFT JOIN order_metrics AS o
              ON CAST(r.restaurant_id AS VARCHAR) = o.restaurant_id
        ),
        restaurant_stats AS (
            SELECT
                COUNT(*) AS restaurant_count,
                COUNT_IF(total_orders > 0) AS active_restaurant_count,
                AVG(restaurant_rating) AS avg_listed_rating
            FROM restaurant_data
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
        FROM restaurant_data AS restaurants
        CROSS JOIN restaurant_stats AS stats
        ORDER BY restaurants.completed_order_sales DESC NULLS LAST,
                 restaurants.restaurant_name
        LIMIT 10
    """

    query_failures = {}

    def load_panel(name: str, sql: str, max_rows: int) -> pd.DataFrame:
        try:
            return run_dashboard_query(sql, max_rows=max_rows)
        except Exception as exc:
            query_failures[name] = str(exc)
            return pd.DataFrame()

    with st.spinner("Loading Silver metrics and breakdowns from Athena..."):
        summary = load_panel("Sales KPIs", summary_sql, 1)
        trend = load_panel("Weekly sales", trend_sql, MAX_DASHBOARD_ROWS)
        segments = load_panel("City and cuisine", segment_sql, 20)
        restaurants = load_panel("Restaurant performance", restaurant_sql, 10)

    if query_failures:
        st.warning(
            "Some dashboard panels could not be loaded. Available panels are still shown.",
            icon=":material/cloud_off:",
        )
        with st.expander("Panel errors"):
            for panel, error in query_failures.items():
                st.markdown(f"**{panel}**")
                st.code(error)

    summary_available = "Sales KPIs" not in query_failures and not summary.empty
    restaurant_available = "Restaurant performance" not in query_failures
    sales = get_number(summary, "recorded_sales")
    orders = int(get_number(summary, "order_count"))
    average_order_value = sales / orders if orders else None
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
        (
            "Recorded sales",
            format_currency(sales) if summary_available else "N/A",
            "INR · all order statuses",
        ),
        (
            "Orders",
            f"{orders:,}" if summary_available else "N/A",
            "Distinct order IDs from Silver order grain",
        ),
        (
            "Sales / Silver order count",
            format_currency(average_order_value) if average_order_value is not None else "N/A",
            "Recorded sales ÷ distinct Silver order IDs",
        ),
        ("Restaurant rating", average_rating, "Average listed rating · all time"),
    ]
    for column, (label, value, help_text) in zip(metric_columns, metrics):
        with column:
            st.metric(label, value, help=help_text, border=True)

    if restaurant_available:
        st.caption(
            f"Silver contains {restaurant_count:,} restaurants; "
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
        st.caption("Source: swiggy_silver.slv_orders · selected date range")
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
            "Sources: swiggy_silver.slv_restaurants + slv_orders · all time · INR"
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
            "Completed sales (₹)", format="₹%.2f"
                    ),
                },
            )


initialize_chat_history()

with st.sidebar:
    st.caption("DATA INTELLIGENCE")
    st.divider()
    st.markdown("#### Your workspace")
    st.caption("Ask questions or explore curated business metrics.")
    st.markdown("#### Chat history")
    st.caption("Conversation history lasts for this app session.")
    if st.button(
        "New chat",
        icon=":material/add_comment:",
        type="primary",
        width="stretch",
        key="new_chat",
    ):
        create_chat()
        st.rerun()

    chat_ids = list(st.session_state.chat_history)
    if st.session_state.chat_picker not in chat_ids:
        st.session_state.chat_picker = st.session_state.active_chat_id
    selected_chat_id = st.selectbox(
        "Conversations",
        options=chat_ids,
        key="chat_picker",
        format_func=lambda chat_id: st.session_state.chat_history[chat_id]["title"],
        label_visibility="collapsed",
    )
    st.session_state.active_chat_id = selected_chat_id

    selected_chat = st.session_state.chat_history[selected_chat_id]
    with st.expander("Edit or delete chat"):
        with st.form(f"rename_chat_form_{selected_chat_id}"):
            new_title = st.text_input(
                "Chat name",
                value=selected_chat["title"],
                max_chars=60,
                key=f"chat_title_{selected_chat_id}",
            )
            rename_chat = st.form_submit_button(
                "Save name",
                icon=":material/edit:",
                width="stretch",
            )
        if rename_chat and new_title.strip():
            selected_chat["title"] = new_title.strip()
            st.rerun()
        confirm_delete = st.checkbox(
            "Confirm deleting this conversation",
            key=f"confirm_delete_chat_{selected_chat_id}",
        )
        st.button(
            "Delete chat",
            icon=":material/delete:",
            type="secondary",
            width="stretch",
            disabled=not confirm_delete,
            key=f"delete_chat_{selected_chat_id}",
            on_click=delete_active_chat,
        )

    st.info(
        "The dashboard reads Silver views; AI questions use approved Gold tables. "
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
    st.caption("AWS region: ap-southeast-2 · Dashboard: Silver · AI: Gold")


with st.container(horizontal=True, vertical_alignment="center"):
    st.markdown("### Business intelligence")
    st.badge("Athena · Silver dashboard / Gold AI", color="orange")

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
st.caption("Swiggy data assistant · Gemini + Amazon Athena · Silver dashboard / Gold AI")
