from __future__ import annotations

import re
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from text_to_sql import execute_sql, generate_sql, validate_sql


APP_DIR = Path(__file__).resolve().parent
ORANGE = "#FC8019"
DAILY = '"swiggy_gold"."gld_daily_sales"'
RESTAURANTS = '"swiggy_gold"."gld_restaurant_performance"'
MAX_ROWS = 500

st.set_page_config(
    page_title="Swiggy BI | Dashboard overview",
    page_icon=str(APP_DIR / "assets" / "swiggy_mark.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)
st.logo(
    str(APP_DIR / "assets" / "swiggy_wordmark.svg"),
    icon_image=str(APP_DIR / "assets" / "swiggy_mark.svg"),
    size="large",
)

st.markdown(
    """
    <style>
    :root {
      --swiggy-orange: #FC8019;
      --swiggy-ink: #24272B;
      --swiggy-muted: #73777D;
      --swiggy-line: #E8E9EB;
      --swiggy-paper: #FFFFFF;
    }
    [data-testid="stAppViewContainer"] { background: #F5F6F7; }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
      background: var(--swiggy-paper);
      border-right: 1px solid var(--swiggy-line);
    }
    .block-container { max-width: 1480px; padding-top: 1.2rem; padding-bottom: 2rem; }
    .page-heading { margin: .1rem 0 1.25rem; }
    .page-heading h1 {
      color: var(--swiggy-ink); font-size: 1.9rem; letter-spacing: -.045em;
      line-height: 1.15; margin: .2rem 0 .35rem;
    }
    .page-heading p { color: var(--swiggy-muted); font-size: .92rem; margin: 0; }
    .eyebrow {
      color: var(--swiggy-orange); font-size: .68rem; font-weight: 700;
      letter-spacing: .12em; text-transform: uppercase;
    }
    div[data-testid="stMetric"] {
      border: 1px solid var(--swiggy-line); border-radius: 12px;
      background: var(--swiggy-paper); padding: .9rem 1rem; min-height: 112px;
    }
    div[data-testid="stHorizontalBlock"]:has(> div [data-testid="stMetric"])
      > div[data-testid="stColumn"]:first-child [data-testid="stMetric"] {
      background: var(--swiggy-orange); border-color: var(--swiggy-orange);
    }
    div[data-testid="stHorizontalBlock"]:has(> div [data-testid="stMetric"])
      > div[data-testid="stColumn"]:first-child [data-testid="stMetricLabel"],
    div[data-testid="stHorizontalBlock"]:has(> div [data-testid="stMetric"])
      > div[data-testid="stColumn"]:first-child [data-testid="stMetricValue"],
    div[data-testid="stHorizontalBlock"]:has(> div [data-testid="stMetric"])
      > div[data-testid="stColumn"]:first-child [data-testid="stMetricDelta"] {
      color: #FFFFFF !important;
    }
    .stButton > button, .stFormSubmitButton > button { border-radius: 9px; }
    div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {
      border: 1px solid var(--swiggy-line); border-radius: 12px;
      background: #FFFFFF; overflow: hidden;
    }
    div[data-testid="stChatMessage"] {
      border: 1px solid var(--swiggy-line); border-radius: 12px; background: #FFFFFF;
    }
    .st-key-assistant_conversation { max-width: 900px; margin: 0 auto; }
    .assistant-welcome { padding: 8vh 0 1.2rem; }
    .assistant-welcome h1 { color: var(--swiggy-ink); font-size: 2rem; letter-spacing: -.04em; }
    .assistant-welcome p { color: var(--swiggy-muted); font-size: 1rem; }
    hr { border-color: var(--swiggy-line); }
    @media (max-width: 640px) {
      .page-heading h1 { font-size: 1.6rem; }
      .block-container { padding-top: .75rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, max_entries=64, show_spinner=False)
def query_df(sql: str, max_rows: int = MAX_ROWS) -> pd.DataFrame:
    return pd.DataFrame(execute_sql(sql, max_rows=max_rows))


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def generate_sql_cached(question: str) -> str:
    return generate_sql(question)


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def execute_chat_sql(sql: str) -> list[dict]:
    return execute_sql(sql, max_rows=100)


def clear_cache() -> None:
    query_df.clear()
    generate_sql_cached.clear()
    execute_chat_sql.clear()


def number(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    value = pd.to_numeric(df.iloc[0][column], errors="coerce")
    return 0.0 if pd.isna(value) else float(value)


def compact_inr(value: float) -> str:
    magnitude = abs(value)
    if magnitude >= 10_000_000:
        return f"₹{value / 10_000_000:.1f}Cr"
    if magnitude >= 100_000:
        return f"₹{value / 100_000:.1f}L"
    if magnitude >= 1_000:
        return f"₹{value / 1_000:.1f}K"
    return f"₹{value:,.0f}"


def date_filter(start: date, end: date) -> str:
    return f"order_date BETWEEN DATE '{start.isoformat()}' AND DATE '{end.isoformat()}'"


def style_chart(fig, height: int = 330):
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=12, t=14, b=8),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#666B72", size=12),
        hovermode="x unified",
        showlegend=False,
    )
    fig.update_xaxes(showgrid=False, title=None, zeroline=False)
    fig.update_yaxes(showgrid=False, title=None, zeroline=False)
    return fig


def source_tables(sql: str) -> str:
    tables = re.findall(
        r'(?i)"?swiggy_gold"?\s*\.\s*"?(gld_[A-Za-z0-9_]+)', sql
    )
    return ", ".join(f"swiggy_gold.{name}" for name in dict.fromkeys(tables)) or "approved Gold tables"


def render_dashboard() -> None:
    st.markdown(
        '<div class="page-heading"><div class="eyebrow">Swiggy · Business intelligence</div>'
        "<h1>Dashboard Overview</h1>"
        "<p>Monitor sales, orders, restaurant performance and customer experience.</p></div>",
        unsafe_allow_html=True,
    )

    try:
        bounds = query_df(
            f"SELECT CAST(MIN(order_date) AS VARCHAR) AS first_date, "
            f"CAST(MAX(order_date) AS VARCHAR) AS last_date FROM {DAILY} WHERE currency = 'INR'",
            1,
        )
        if bounds.empty or pd.isna(bounds.iloc[0].get("first_date")):
            st.info("No INR order dates are available in gld_daily_sales.")
            return
        first = pd.to_datetime(bounds.iloc[0]["first_date"]).date()
        last = pd.to_datetime(bounds.iloc[0]["last_date"]).date()
    except Exception as exc:
        st.error("Could not load the available order date range.")
        with st.expander("Technical details"):
            st.code(str(exc))
        return

    default = (max(first, last - timedelta(days=29)), last)
    current = st.session_state.get("dashboard_range", default)
    if (
        not isinstance(current, (tuple, list)) or len(current) != 2
        or current[0] < first or current[1] > last or current[0] > current[1]
    ):
        current = default

    with st.form("dashboard_date_filter", border=True):
        date_col, apply_col = st.columns([4, 1], vertical_alignment="bottom")
        with date_col:
            chosen = st.date_input(
                "Order date range", value=tuple(current), min_value=first,
                max_value=last, format="YYYY-MM-DD",
            )
        with apply_col:
            apply = st.form_submit_button("Apply dates", type="primary", width="stretch")
    if apply:
        if not isinstance(chosen, (tuple, list)) or len(chosen) != 2 or chosen[0] > chosen[1]:
            st.warning("Choose a valid start and end date.")
            return
        current = tuple(chosen)
        st.session_state.dashboard_range = current

    start, end = current
    selected_filter = date_filter(start, end)
    period_days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    previous_filter = date_filter(previous_start, previous_end)

    current_sql = f"""
        SELECT COALESCE(SUM(total_sales), 0) AS sales,
               COALESCE(SUM(total_orders), 0) AS orders,
               COALESCE(SUM(total_items), 0) AS items
        FROM {DAILY}
        WHERE currency = 'INR' AND {selected_filter}
    """
    previous_sql = f"""
        SELECT COALESCE(SUM(total_sales), 0) AS sales,
               COALESCE(SUM(total_orders), 0) AS orders
        FROM {DAILY}
        WHERE currency = 'INR' AND {previous_filter}
    """
    trend_sql = f"""
        SELECT CAST(DATE_TRUNC('week', order_date) AS VARCHAR) AS week_start,
               COALESCE(SUM(total_sales), 0) AS sales,
               COALESCE(SUM(total_orders), 0) AS orders
        FROM {DAILY}
        WHERE currency = 'INR' AND {selected_filter}
        GROUP BY DATE_TRUNC('week', order_date)
        ORDER BY DATE_TRUNC('week', order_date)
        LIMIT {MAX_ROWS}
    """
    city_sql = f"""
        SELECT TRIM(restaurant_city) AS city, SUM(total_sales) AS sales
        FROM {DAILY}
        WHERE currency = 'INR' AND {selected_filter}
          AND restaurant_city IS NOT NULL AND TRIM(restaurant_city) <> ''
        GROUP BY TRIM(restaurant_city)
        ORDER BY sales DESC
        LIMIT 10
    """
    cuisine_sql = f"""
        SELECT TRIM(cuisine) AS cuisine, SUM(total_sales) AS sales
        FROM {DAILY}
        WHERE currency = 'INR' AND {selected_filter}
          AND cuisine IS NOT NULL AND TRIM(cuisine) <> ''
        GROUP BY TRIM(cuisine)
        ORDER BY sales DESC
        LIMIT 10
    """
    top_sql = f"""
        SELECT restaurant_name, restaurant_city, cuisine, completed_orders,
               completed_order_sales, restaurant_rating,
               avg_delivery_time_min
        FROM {RESTAURANTS}
        ORDER BY completed_order_sales DESC NULLS LAST
        LIMIT 10
    """

    try:
        with st.spinner("Loading metrics from Athena…"):
            current_stats = query_df(current_sql, 1)
            previous_stats = query_df(previous_sql, 1)
            trend = query_df(trend_sql, MAX_ROWS)
            cities = query_df(city_sql, 10)
            cuisines = query_df(cuisine_sql, 10)
            top = query_df(top_sql, 10)
    except Exception as exc:
        st.error("Some dashboard data could not be loaded.")
        with st.expander("Technical details"):
            st.code(str(exc))
        st.caption("Queries use gld_daily_sales and gld_restaurant_performance in swiggy_gold.")
        return

    sales = number(current_stats, "sales")
    orders = number(current_stats, "orders")
    items = number(current_stats, "items")
    previous_sales = number(previous_stats, "sales")
    previous_orders = number(previous_stats, "orders")
    sales_delta = (
        f"{(sales - previous_sales) / abs(previous_sales) * 100:+.1f}%"
        if previous_sales else None
    )
    orders_delta = (
        f"{(orders - previous_orders) / abs(previous_orders) * 100:+.1f}%"
        if previous_orders else None
    )
    st.caption(f"{start:%d %b %Y} – {end:%d %b %Y} · INR · {period_days} days")
    metrics = st.columns(4, gap="medium")
    aov = sales / orders if orders else 0
    cards = [
        ("Recorded sales", compact_inr(sales), sales_delta, "All order statuses; this is not settled revenue."),
        ("Total orders", f"{orders:,.0f}", orders_delta, "Summed from daily aggregates."),
        ("Average order value", compact_inr(aov), None, "Recorded sales per recorded order."),
        ("Items sold", f"{items:,.0f}", None, "Sum of item lines; excludes quantity units."),
    ]
    for col, (label, value, delta, help_text) in zip(metrics, cards):
        with col:
            st.metric(
                label, value, delta=delta,
                delta_description="vs prior period" if delta is not None else None,
                help=help_text, border=True, height="stretch",
            )

    st.caption(
        f"Comparisons use the immediately preceding {period_days}-day period. "
        "A comparison is omitted when the prior period has no recorded sales or orders."
    )

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown("#### Weekly sales trend")
        st.caption("Recorded sales · selected date range")
        if trend.empty:
            st.info("No sales found for this date range.")
        else:
            trend["week_start"] = pd.to_datetime(trend["week_start"], errors="coerce")
            trend["sales"] = pd.to_numeric(trend["sales"], errors="coerce")
            trend = trend.dropna(subset=["week_start", "sales"]).sort_values("week_start")
            fig = px.area(
                trend, x="week_start", y="sales", markers=True,
                color_discrete_sequence=[ORANGE], labels={"week_start": "Week", "sales": "Sales (INR)"},
            )
            fig.update_traces(
                line_width=2.5, fillcolor="rgba(252,128,25,.13)",
                hovertemplate="%{x|%d %b %Y}<br>Sales: ₹%{y:,.0f}<extra></extra>",
            )
            fig.update_yaxes(tickprefix="₹", separatethousands=True, showgrid=True, gridcolor="#ECEDEF")
            st.plotly_chart(style_chart(fig), width="stretch", config={"displayModeBar": False})

    with right:
        st.markdown("#### Sales by city")
        st.caption("Top 10 · selected date range")
        if cities.empty:
            st.info("No city sales found for this date range.")
        else:
            cities["sales"] = pd.to_numeric(cities["sales"], errors="coerce")
            cities = cities.dropna(subset=["sales"]).sort_values("sales", ascending=True)
            fig = px.bar(
                cities, x="sales", y="city", orientation="h",
                color_discrete_sequence=[ORANGE], labels={"sales": "Sales (INR)", "city": "City"},
            )
            fig.update_traces(hovertemplate="%{y}<br>Sales: ₹%{x:,.0f}<extra></extra>")
            fig.update_xaxes(tickprefix="₹", separatethousands=True, showgrid=True, gridcolor="#ECEDEF")
            st.plotly_chart(style_chart(fig, 330), width="stretch", config={"displayModeBar": False})

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Sales by cuisine")
        st.caption("Top 10 · selected date range")
        if cuisines.empty:
            st.info("No cuisine sales found for this date range.")
        else:
            cuisines["sales"] = pd.to_numeric(cuisines["sales"], errors="coerce")
            cuisines = cuisines.dropna(subset=["sales"]).sort_values("sales", ascending=True)
            fig = px.bar(
                cuisines, x="sales", y="cuisine", orientation="h",
                color_discrete_sequence=[ORANGE], labels={"sales": "Sales (INR)", "cuisine": "Cuisine"},
            )
            fig.update_traces(hovertemplate="%{y}<br>Sales: ₹%{x:,.0f}<extra></extra>")
            fig.update_xaxes(tickprefix="₹", separatethousands=True, showgrid=True, gridcolor="#ECEDEF")
            st.plotly_chart(style_chart(fig, 350), width="stretch", config={"displayModeBar": False})

    with right:
        st.markdown("#### Top restaurants")
        st.caption("Ranked by completed-order sales · all time")
        if top.empty:
            st.info("No restaurant performance records are available.")
        else:
            top = top.rename(columns={
                "restaurant_name": "Restaurant", "restaurant_city": "City",
                "cuisine": "Cuisine", "completed_orders": "Completed orders",
                "completed_order_sales": "Completed sales (INR)",
                "restaurant_rating": "Listed rating", "avg_delivery_time_min": "Avg delivery (min)",
            })
            st.dataframe(
                top, hide_index=True, width="stretch", alt="Top restaurants ranked by all-time completed-order sales",
                column_config={
                    "Completed orders": st.column_config.NumberColumn(format="localized"),
                    "Completed sales (INR)": st.column_config.NumberColumn(format="₹%.0f"),
                    "Listed rating": st.column_config.NumberColumn(format="%.1f"),
                    "Avg delivery (min)": st.column_config.NumberColumn(format="%.1f"),
                },
            )


def section_heading(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-heading"><div class="eyebrow">{eyebrow}</div>'
        f"<h1>{title}</h1><p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )


def render_restaurant_analytics() -> None:
    section_heading(
        "Restaurant intelligence", "Restaurant Analytics",
        "All-time restaurant catalogue and completed-order performance.",
    )
    try:
        summary = query_df(
            f"SELECT COUNT(DISTINCT restaurant_id) AS restaurants, "
            f"AVG(restaurant_rating) AS avg_rating, "
            f"SUM(completed_order_sales) AS completed_sales FROM {RESTAURANTS}", 1,
        )
        top = query_df(
            f"SELECT restaurant_name, restaurant_city, cuisine, total_orders, "
            f"completed_orders, completed_order_sales, restaurant_rating, "
            f"avg_delivery_time_min FROM {RESTAURANTS} "
            "ORDER BY completed_order_sales DESC NULLS LAST LIMIT 10", 10,
        )
    except Exception as exc:
        st.error("Restaurant analytics could not be loaded.")
        with st.expander("Technical details"):
            st.code(str(exc))
        return
    cols = st.columns(3)
    with cols[0]:
        st.metric("Restaurants", f"{number(summary, 'restaurants'):,.0f}", border=True)
    with cols[1]:
        rating = number(summary, "avg_rating")
        st.metric("Average listed rating", f"{rating:.2f}/5" if rating else "—", border=True)
    with cols[2]:
        st.metric("Completed-order sales", compact_inr(number(summary, "completed_sales")), border=True)
    st.markdown("#### Top restaurants")
    st.caption("Ranked by completed-order sales · all time")
    if top.empty:
        st.info("No restaurant records are available.")
        return
    top = top.rename(columns={
        "restaurant_name": "Restaurant", "restaurant_city": "City", "cuisine": "Cuisine",
        "total_orders": "Total orders", "completed_orders": "Completed orders",
        "completed_order_sales": "Completed sales (INR)",
        "restaurant_rating": "Listed rating", "avg_delivery_time_min": "Avg delivery (min)",
    })
    st.dataframe(top, hide_index=True, width="stretch", alt="Top restaurants by all-time completed-order sales", column_config={
        "Total orders": st.column_config.NumberColumn(format="localized"),
        "Completed orders": st.column_config.NumberColumn(format="localized"),
        "Completed sales (INR)": st.column_config.NumberColumn(format="₹%.0f"),
        "Listed rating": st.column_config.NumberColumn(format="%.1f"),
        "Avg delivery (min)": st.column_config.NumberColumn(format="%.1f"),
    })


def render_customer_analytics() -> None:
    section_heading(
        "Customer intelligence", "Customer Analytics",
        "All-time customer activity and completed-order rating distribution.",
    )
    try:
        summary = query_df(
            'SELECT COUNT(DISTINCT user_id) AS customers, '
            'SUM(completed_orders) AS completed_orders, '
            'AVG(avg_customer_rating) AS avg_customer_rating '
            'FROM "swiggy_gold"."gld_customer_analytics"', 1,
        )
        customers = query_df(
        'SELECT user_id, total_orders, completed_orders, cancelled_orders, '
            'avg_customer_rating '
            'FROM "swiggy_gold"."gld_customer_analytics" '
            'ORDER BY completed_orders DESC, total_orders DESC LIMIT 10', 10,
        )
        ratings = query_df(
            'SELECT SUM(rating_1_count) AS rating_1, SUM(rating_2_count) AS rating_2, '
            'SUM(rating_3_count) AS rating_3, SUM(rating_4_count) AS rating_4, '
            'SUM(rating_5_count) AS rating_5 '
            'FROM "swiggy_gold"."gld_customer_rating_analysis"', 1,
        )
    except Exception as exc:
        st.error("Customer analytics could not be loaded.")
        with st.expander("Technical details"):
            st.code(str(exc))
        return
    cols = st.columns(3)
    with cols[0]:
        st.metric("Customers", f"{number(summary, 'customers'):,.0f}", border=True)
    with cols[1]:
        st.metric("Completed orders", f"{number(summary, 'completed_orders'):,.0f}", border=True)
    with cols[2]:
        rating = number(summary, "avg_customer_rating")
        st.metric("Average customer rating", f"{rating:.2f}/5" if rating else "—", border=True)
    st.caption("Customer metrics are all time. Average rating is an average of customer-level averages.")
    rating_columns = [f"rating_{i}" for i in range(1, 6)]
    if not ratings.empty and any(number(ratings, column) for column in rating_columns):
        rating_frame = pd.DataFrame({
            "Rating": ["1 star", "2 stars", "3 stars", "4 stars", "5 stars"],
            "Completed orders": [number(ratings, column) for column in rating_columns],
        })
        rating_frame = rating_frame[rating_frame["Completed orders"] > 0]
        st.markdown("#### Completed-order ratings")
        st.caption("Counts from gld_customer_rating_analysis")
        fig = px.bar(
            rating_frame, x="Completed orders", y="Rating", orientation="h",
            color_discrete_sequence=[ORANGE],
        )
        fig.update_traces(hovertemplate="%{y}<br>Orders: %{x:,.0f}<extra></extra>")
        st.plotly_chart(style_chart(fig, 260), width="stretch", config={"displayModeBar": False})
    st.markdown("#### Most active customers")
    st.caption("Ranked by completed-order count · all time")
    if customers.empty:
        st.info("No customer records are available.")
    else:
        customers = customers.rename(columns={
            "user_id": "Customer ID", "total_orders": "Total orders",
            "completed_orders": "Completed orders", "cancelled_orders": "Cancelled orders",
            "avg_customer_rating": "Avg customer rating",
        })
        st.dataframe(customers, hide_index=True, width="stretch", alt="Most active customers", column_config={
            "Total orders": st.column_config.NumberColumn(format="localized"),
            "Completed orders": st.column_config.NumberColumn(format="localized"),
            "Cancelled orders": st.column_config.NumberColumn(format="localized"),
            "Avg customer rating": st.column_config.NumberColumn(format="%.2f"),
        })


def render_delivery_orders() -> None:
    section_heading(
        "Operations", "Delivery & Orders",
        "All-time delivery averages and the validated INR order-status breakdown.",
    )
    try:
        delivery = query_df(
            'SELECT SUM(completed_orders) AS completed_orders, '
            'SUM(orders_with_delivery_time) AS timed_orders, '
            'SUM(avg_delivery_time_min * orders_with_delivery_time) / '
            'NULLIF(SUM(orders_with_delivery_time), 0) AS weighted_delivery_minutes '
            'FROM "swiggy_gold"."gld_delivery_performance" WHERE currency = \'INR\'', 1,
        )
        city_delivery = query_df(
            'SELECT restaurant_city AS city, '
            'SUM(avg_delivery_time_min * orders_with_delivery_time) / '
            'NULLIF(SUM(orders_with_delivery_time), 0) AS avg_delivery_minutes, '
            'SUM(orders_with_delivery_time) AS timed_orders '
            'FROM "swiggy_gold"."gld_delivery_performance" '
            'WHERE currency = \'INR\' AND restaurant_city IS NOT NULL '
            'AND TRIM(restaurant_city) <> \'\' '
            'GROUP BY restaurant_city ORDER BY avg_delivery_minutes DESC LIMIT 10', 10,
        )
        statuses = query_df(
            'SELECT order_status, SUM(total_orders) AS total_orders '
            'FROM "swiggy_gold"."gld_order_status_analysis" '
            'WHERE currency = \'INR\' GROUP BY order_status ORDER BY total_orders DESC', 100,
        )
    except Exception as exc:
        st.error("Delivery and order analytics could not be loaded.")
        with st.expander("Technical details"):
            st.code(str(exc))
        return
    cols = st.columns(3)
    with cols[0]:
        st.metric("Completed orders", f"{number(delivery, 'completed_orders'):,.0f}", border=True)
    with cols[1]:
        minutes = number(delivery, "weighted_delivery_minutes")
        st.metric("Weighted avg delivery", f"{minutes:.1f} min" if minutes else "—", border=True)
    with cols[2]:
        st.metric("Orders with delivery time", f"{number(delivery, 'timed_orders'):,.0f}", border=True)
    st.caption("Delivery measures are all-time. The average is weighted by orders with a recorded delivery time.")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Order status distribution")
        st.caption("INR · all time · statuses shown as stored in the Gold model")
        if statuses.empty:
            st.info("No order status records are available.")
        else:
            statuses["total_orders"] = pd.to_numeric(statuses["total_orders"], errors="coerce")
            statuses = statuses.dropna(subset=["total_orders"])
            if len(statuses) > 0:
                fig = px.pie(
                    statuses, names="order_status", values="total_orders", hole=.64,
                    color_discrete_sequence=[ORANGE, "#F6B18A", "#A9AFB7", "#E4E6E8"],
                )
                fig.update_traces(
                    textinfo="percent", hovertemplate="%{label}<br>Orders: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
                )
                fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-.1))
                st.plotly_chart(style_chart(fig, 320), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown("#### Delivery time by city")
        st.caption("Top 10 by average minutes · all time")
        if city_delivery.empty:
            st.info("No city delivery records are available.")
        else:
            city_delivery["avg_delivery_minutes"] = pd.to_numeric(city_delivery["avg_delivery_minutes"], errors="coerce")
            city_delivery = city_delivery.dropna(subset=["avg_delivery_minutes"]).sort_values("avg_delivery_minutes")
            fig = px.bar(
                city_delivery, x="avg_delivery_minutes", y="city", orientation="h",
                color_discrete_sequence=[ORANGE], labels={"avg_delivery_minutes": "Minutes", "city": "City"},
            )
            fig.update_traces(hovertemplate="%{y}<br>Average: %{x:.1f} min<extra></extra>")
            st.plotly_chart(style_chart(fig, 320), width="stretch", config={"displayModeBar": False})


def render_data_status() -> None:
    section_heading("Data status", "Sources & definitions", "Approved read-only Gold sources used by this application.")
    st.info("Athena · `swiggy_gold` · AWS region `ap-southeast-2`", icon=":material/database:")
    st.markdown("#### Dashboard and analytics tables")
    st.dataframe(pd.DataFrame([
        {"Section": "Dashboard", "Gold table": "gld_daily_sales", "Grain / scope": "Date × city × cuisine × currency"},
        {"Section": "Dashboard, restaurants", "Gold table": "gld_restaurant_performance", "Grain / scope": "Restaurant · all time"},
        {"Section": "Customers", "Gold table": "gld_customer_analytics", "Grain / scope": "Customer · all time"},
        {"Section": "Customer ratings", "Gold table": "gld_customer_rating_analysis", "Grain / scope": "Restaurant · completed orders"},
        {"Section": "Delivery", "Gold table": "gld_delivery_performance", "Grain / scope": "Restaurant × city × cuisine × currency"},
        {"Section": "Order status", "Gold table": "gld_order_status_analysis", "Grain / scope": "Status × city × currency"},
    ]), hide_index=True, width="stretch", alt="Gold table sources and aggregation grains")
    st.caption("Dashboard date filters apply to gld_daily_sales. Restaurant, customer, delivery, and status summaries are all-time Gold aggregates.")


def render_assistant_result(rows: list[dict]) -> None:
    result = pd.DataFrame(rows)
    if result.empty:
        st.caption("No rows returned.")
        return
    column_config = {}
    for column in result.columns:
        numeric = pd.to_numeric(result[column], errors="coerce")
        non_null = result[column].notna().sum()
        if non_null and numeric.notna().sum() == non_null:
            result[column] = numeric
            name = column.lower()
            if any(token in name for token in ("sales", "spend", "revenue", "amount", "value")):
                column_config[column] = st.column_config.NumberColumn(format="₹%.2f")
            elif "rating" in name:
                column_config[column] = st.column_config.NumberColumn(format="%.2f")
            elif any(token in name for token in ("minute", "delivery_time")):
                column_config[column] = st.column_config.NumberColumn(format="%.1f")
            else:
                column_config[column] = st.column_config.NumberColumn(format="localized")

    time_columns = [c for c in result.columns if any(t in c.lower() for t in ("date", "week", "month"))]
    measures = [c for c in result.columns if any(t in c.lower() for t in (
        "sales", "orders", "count", "quantity", "spend", "revenue", "delivery_time", "rating",
    ))]
    chart = None
    if time_columns and measures:
        time_col = time_columns[0]
        measure = next((c for c in measures if pd.api.types.is_numeric_dtype(result[c])), None)
        if measure:
            plot_frame = result.copy()
            plot_frame[time_col] = pd.to_datetime(plot_frame[time_col], errors="coerce")
            plot_frame = plot_frame.dropna(subset=[time_col]).sort_values(time_col)
            if not plot_frame.empty:
                chart = px.line(plot_frame, x=time_col, y=measure, markers=True, color_discrete_sequence=[ORANGE])
    elif "order_status" in result.columns and "total_orders" in result.columns and len(result) <= 6:
        chart = px.pie(result, names="order_status", values="total_orders", hole=.62,
                       color_discrete_sequence=[ORANGE, "#F6B18A", "#A9AFB7", "#E4E6E8"])
    else:
        categories = [c for c in result.columns if any(t in c.lower() for t in (
            "city", "cuisine", "restaurant", "category", "status",
        ))]
        measure = next((c for c in measures if pd.api.types.is_numeric_dtype(result[c])), None)
        if categories and measure and len(result) <= 30:
            chart = px.bar(
                result.sort_values(measure), x=measure, y=categories[0], orientation="h",
                color_discrete_sequence=[ORANGE],
            )
    if chart is not None:
        st.plotly_chart(style_chart(chart, 300), width="stretch", config={"displayModeBar": False})
    st.dataframe(result, hide_index=True, width="stretch", alt="Validated Athena query results", column_config=column_config)


def submit_question(question: str) -> None:
    question = question.strip()
    if not question:
        return
    st.session_state.messages.append({"role": "user", "content": question})
    started = time.perf_counter()
    try:
        with st.spinner("Preparing and validating your query…"):
            draft = generate_sql_cached(question)
            if draft.strip().upper().startswith("UNSUPPORTED:"):
                answer = draft.split(":", 1)[1].strip()
                st.session_state.messages.append({"role": "assistant", "content": answer})
                return
            sql = validate_sql(draft)
            rows = execute_chat_sql(sql)
        elapsed = time.perf_counter() - started
        summary = f"Returned **{len(rows):,} row(s)** from `{source_tables(sql)}` in **{elapsed:.1f}s**."
        st.session_state.messages.append({"role": "assistant", "content": summary, "sql": sql, "data": rows})
    except Exception as exc:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "I couldn't complete that analysis. Try asking about sales, orders, restaurants, ratings or delivery.",
            "error": str(exc),
        })


def render_assistant() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    with st.container(key="assistant_conversation"):
        if not st.session_state.messages:
            st.markdown(
                '<div class="assistant-welcome"><div class="eyebrow">Gemini · Amazon Athena</div>'
                '<h1>Ask your Swiggy data anything.</h1>'
                '<p>Explore sales, restaurants, orders and customer trends using natural language.</p></div>',
                unsafe_allow_html=True,
            )
            suggestions = [
                "Which cities generated the highest recorded sales?",
                "Show the weekly sales trend.",
                "Which restaurants have the highest completed-order sales?",
                "Compare sales by cuisine.",
            ]
            cols = st.columns(2)
            for index, (col, prompt) in enumerate(zip(cols * 2, suggestions)):
                with col:
                    if st.button(prompt, key=f"assistant_suggestion_{index}", width="stretch", icon=":material/arrow_outward:"):
                        st.session_state.pending_question = prompt
        else:
            st.markdown('<div class="eyebrow">AI Data Assistant</div>', unsafe_allow_html=True)
            st.subheader("Your conversation")
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("data") is not None:
                        render_assistant_result(msg["data"])
                    if msg.get("sql"):
                        with st.expander("View SQL"):
                            st.code(msg["sql"], language="sql")
                    if msg.get("error"):
                        with st.expander("Technical details"):
                            st.code(msg["error"])
        typed_question = st.chat_input("Ask your Swiggy data anything…", key="assistant_input", max_chars=1000)
    question = st.session_state.pop("pending_question", None) or typed_question
    if question:
        submit_question(question)
        st.rerun()


def main() -> None:
    pages = [
        "Dashboard", "AI Assistant", "Restaurant Analytics",
        "Customer Analytics", "Delivery & Orders", "Data Status",
    ]
    page_icons = {
        "Dashboard": ":material/dashboard:",
        "AI Assistant": ":material/forum:",
        "Restaurant Analytics": ":material/storefront:",
        "Customer Analytics": ":material/groups:",
        "Delivery & Orders": ":material/local_shipping:",
        "Data Status": ":material/database:",
    }
    with st.sidebar:
        st.markdown("### Swiggy BI")
        st.caption("DATA INTELLIGENCE")
        page = st.radio(
            "Navigation", pages,
            format_func=lambda item: f"{page_icons[item]} {item}",
            key="app_page", label_visibility="collapsed",
        )
        st.divider()
        st.markdown("**Connected source**")
        st.caption("Amazon Athena")
        st.caption("Gold database · `swiggy_gold`")
        st.caption("AWS region · `ap-southeast-2`")
        if st.button("Refresh data", icon=":material/refresh:", width="stretch"):
            clear_cache()
            st.rerun()
        st.caption("Cached for up to 5 minutes")

    renderers = {
        "Dashboard": render_dashboard,
        "AI Assistant": render_assistant,
        "Restaurant Analytics": render_restaurant_analytics,
        "Customer Analytics": render_customer_analytics,
        "Delivery & Orders": render_delivery_orders,
        "Data Status": render_data_status,
    }
    renderers[page]()
    st.divider()
    st.caption("Swiggy BI · Gemini + Amazon Athena · Read-only analytics")


main()
