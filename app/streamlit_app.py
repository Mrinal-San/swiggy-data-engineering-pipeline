import time

import pandas as pd
import plotly.express as px
import streamlit as st

from text_to_sql import execute_sql, generate_sql, validate_sql

st.set_page_config(
    page_title="Swiggy | Ask your data",
    page_icon=":material/chat:",
    layout="wide",
)

SUGGESTIONS = {
    "Top restaurants by completed sales": (
        "Show the top 10 restaurants by completed sales"
    ),
    "Sales across cities": "Compare sales across cities",
    "Daily sales trend": "Show daily sales by date",
}


@st.cache_data(ttl=300)
def run_dashboard_query(sql: str) -> pd.DataFrame:
    return pd.DataFrame(execute_sql(sql))


@st.cache_data(ttl=60, show_spinner=False)
def run_chat_query(question: str) -> tuple[str, list[dict]]:
    """Cache identical questions briefly to avoid repeating Gemini and Athena calls."""
    sql = validate_sql(generate_sql(question))
    results = execute_sql(sql)
    return sql, results


def format_currency(value: object) -> str:
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return "₹0"


def render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sql"):
            with st.expander("Generated SQL"):
                st.code(message["sql"], language="sql")

        if message.get("data") is not None:
            result_df = pd.DataFrame(message["data"])
            if result_df.empty:
                st.caption("No rows returned.")
            else:
                st.dataframe(
                    result_df,
                    hide_index=True,
                    alt="Query results",
                )


def render_chat() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        render_message(message)

    prompt = st.chat_input("Ask a question about Swiggy data")
    if not st.session_state.messages:
        st.caption("Ask a question or choose a suggestion to get started.")
        selected_suggestion = st.pills(
            "Suggested questions",
            options=list(SUGGESTIONS),
            label_visibility="collapsed",
            key="chat_suggestions",
        )
        if selected_suggestion:
            prompt = SUGGESTIONS[selected_suggestion]

    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            query_start = time.perf_counter()
            with st.status(
                ":shimmer[Checking your data]",
                type="compact",
            ) as status:
                sql, results = run_chat_query(prompt.strip())
                elapsed = time.perf_counter() - query_start
                status.update(
                    label="Query complete",
                    state="complete",
                )

            st.caption(f"Response time: {elapsed:.2f} seconds")

            if results:
                st.markdown("Here’s what I found.")
                st.dataframe(
                    pd.DataFrame(results),
                    hide_index=True,
                    alt="Query results",
                )
            else:
                st.caption("No rows matched that question.")

            with st.expander("Generated SQL"):
                st.code(sql, language="sql")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "Here’s what I found.",
                    "sql": sql,
                    "data": results,
                }
            )
        except Exception as exc:
            error_message = f"Unable to answer this question: {exc}"
            st.error(error_message)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_message}
            )


def render_analytics() -> None:
    st.subheader("Business overview")
    st.caption("Key metrics from your Athena Gold tables.")

    try:
        kpi_df = run_dashboard_query(
            """
            SELECT
                COALESCE(SUM(total_sales), 0) AS total_sales,
                COALESCE(SUM(total_orders), 0) AS total_orders
            FROM "swiggy_gold"."gld_daily_sales"
            WHERE currency = 'INR'
            """
        )
        restaurant_df = run_dashboard_query(
            """
            SELECT
                COUNT(*) AS restaurant_count,
                AVG(restaurant_rating) AS avg_rating
            FROM "swiggy_gold"."gld_restaurant_performance"
            """
        )

        sales = float(kpi_df.iloc[0]["total_sales"] or 0)
        orders = int(float(kpi_df.iloc[0]["total_orders"] or 0))
        restaurant_count = int(
            float(restaurant_df.iloc[0]["restaurant_count"] or 0)
        )
        avg_rating_value = restaurant_df.iloc[0]["avg_rating"]
        avg_rating = (
            f"{float(avg_rating_value):.1f} / 5"
            if pd.notna(avg_rating_value)
            else "N/A"
        )

        metric_columns = st.columns(4)
        metric_columns[0].metric("Total sales (INR)", format_currency(sales))
        metric_columns[1].metric("Total orders", f"{orders:,}")
        metric_columns[2].metric("Restaurants", f"{restaurant_count:,}")
        metric_columns[3].metric("Average rating", avg_rating)

        left, right = st.columns(2)
        with left:
            st.subheader("Daily sales")
            trend_df = run_dashboard_query(
                """
                SELECT
                    CAST(order_date AS VARCHAR) AS order_date,
                    SUM(total_sales) AS total_sales
                FROM "swiggy_gold"."gld_daily_sales"
                WHERE currency = 'INR'
                GROUP BY CAST(order_date AS VARCHAR)
                ORDER BY CAST(order_date AS VARCHAR)
                LIMIT 100
                """
            )
            if not trend_df.empty:
                trend_df["order_date"] = pd.to_datetime(
                    trend_df["order_date"],
                    errors="coerce",
                )
                trend_df["total_sales"] = pd.to_numeric(
                    trend_df["total_sales"],
                    errors="coerce",
                )
                trend_df = trend_df.dropna(subset=["order_date"])
                if not trend_df.empty:
                    fig = px.line(
                        trend_df,
                        x="order_date",
                        y="total_sales",
                        markers=True,
                        color_discrete_sequence=["#FC8019"],
                        labels={
                            "order_date": "Date",
                            "total_sales": "Sales (₹)",
                        },
                    )
                    fig.update_layout(
                        plot_bgcolor="rgba(0, 0, 0, 0)",
                        paper_bgcolor="rgba(0, 0, 0, 0)",
                        margin=dict(l=8, r=8, t=16, b=8),
                    )
                    st.plotly_chart(
                        fig,
                        width="stretch",
                        alt="Daily sales trend",
                    )
                else:
                    st.caption("No valid sales dates are available.")
            else:
                st.caption("No sales data available.")

        with right:
            st.subheader("Sales by city")
            city_df = run_dashboard_query(
                """
                SELECT
                    restaurant_city,
                    SUM(total_sales) AS total_sales
                FROM "swiggy_gold"."gld_daily_sales"
                WHERE currency = 'INR'
                  AND restaurant_city IS NOT NULL
                GROUP BY restaurant_city
                ORDER BY total_sales DESC
                LIMIT 10
                """
            )
            if not city_df.empty:
                city_df["total_sales"] = pd.to_numeric(
                    city_df["total_sales"],
                    errors="coerce",
                )
                fig = px.bar(
                    city_df.sort_values("total_sales"),
                    x="total_sales",
                    y="restaurant_city",
                    orientation="h",
                    color_discrete_sequence=["#FC8019"],
                    labels={
                        "total_sales": "Sales (₹)",
                        "restaurant_city": "City",
                    },
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0, 0, 0, 0)",
                    paper_bgcolor="rgba(0, 0, 0, 0)",
                    margin=dict(l=8, r=8, t=16, b=8),
                )
                st.plotly_chart(
                    fig,
                    width="stretch",
                    alt="Sales by city",
                )
            else:
                st.caption("No city sales data available.")

        st.subheader("Top restaurants by completed sales")
        top_df = run_dashboard_query(
            """
            SELECT
                restaurant_name,
                restaurant_city,
                cuisine,
                completed_orders,
                completed_order_sales
            FROM "swiggy_gold"."gld_restaurant_performance"
            ORDER BY completed_order_sales DESC
            LIMIT 10
            """
        )
        if top_df.empty:
            st.caption("No restaurant performance data available.")
        else:
            st.dataframe(
                top_df,
                hide_index=True,
                alt="Top restaurants by completed sales",
            )
    except Exception as exc:
        st.error("The analytics view could not load its data.")
        st.code(str(exc))
        st.caption(
            "Check the Gold table names, Athena permissions, "
            "and the Athena results S3 location."
        )


with st.container(horizontal=True, vertical_alignment="center"):
    st.title("Swiggy", icon=":material/chat:")
    st.caption("Analytics assistant")
    if st.button(
        "Refresh data",
        icon=":material/refresh:",
        key="refresh_data",
    ):
        run_dashboard_query.clear()
        run_chat_query.clear()
        st.rerun()

view = st.segmented_control(
    "Choose a view",
    options=["Ask", "Analytics"],
    default="Ask",
    label_visibility="collapsed",
    key="main_view",
)

if view == "Analytics":
    render_analytics()
else:
    render_chat()

st.caption("Swiggy data assistant · Gemini + Amazon Athena")
