from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dc_violations.fetch import FetchConfig, refresh_dataset
from dc_violations.visualize import build_monthly_totals

DATA_PATH = Path("data/violations_monthly_latest.parquet")

st.set_page_config(page_title="DC Moving Violations", layout="wide")
st.title("Washington, DC Moving Violations")
st.caption("Automatically refreshed monthly totals from DC ArcGIS services (2024 + 2025).")


@st.cache_data(ttl=60 * 60 * 12)
def load_data() -> pd.DataFrame:
    if DATA_PATH.exists():
        return pd.read_parquet(DATA_PATH)
    return pd.DataFrame()


def run_refresh() -> pd.DataFrame:
    return refresh_dataset(
        config=FetchConfig(max_workers=2),
        output_path=str(DATA_PATH),
        summary_only=True,
    )


refresh_clicked = st.button("Refresh monthly totals now")
if refresh_clicked:
    with st.spinner("Refreshing monthly totals..."):
        df = run_refresh()
        st.cache_data.clear()
else:
    df = load_data()

if df.empty:
    st.info("No local data yet. Click **Refresh monthly totals now** to fetch the latest counts.")
    st.stop()

monthly = build_monthly_totals(df)

col1, col2 = st.columns(2)
col1.metric("Total violations in window", f"{int(monthly['violations'].sum()):,}")
col2.metric("Months loaded", f"{monthly['year_month'].nunique()}")

fig = px.line(monthly, x="year_month", y="violations", markers=True, title="Monthly moving violations")
fig.update_layout(xaxis_title="Month", yaxis_title="Violations")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Monthly table")
st.dataframe(monthly, use_container_width=True)
