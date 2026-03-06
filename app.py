from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dc_violations.fetch import FetchConfig, refresh_dataset
from dc_violations.visualize import build_monthly_totals

DATA_PATH = Path("data/violations_latest.parquet")

st.set_page_config(page_title="DC Moving Violations", layout="wide")
st.title("Washington, DC Moving Violations")
st.caption("Automatically refreshed query from DC ArcGIS services (2024 + 2025).")


@st.cache_data(ttl=60 * 60 * 12)
def load_or_refresh_data(force_refresh: bool) -> pd.DataFrame:
    if force_refresh or not DATA_PATH.exists():
        return refresh_dataset(config=FetchConfig(max_workers=6))
    return pd.read_parquet(DATA_PATH)


force = st.button("Refresh now")
with st.spinner("Loading violations data..."):
    df = load_or_refresh_data(force)

if df.empty:
    st.warning("No data found for selected window.")
    st.stop()

monthly = build_monthly_totals(df)

col1, col2 = st.columns(2)
col1.metric("Total violations", f"{len(df):,}")
col2.metric("Months loaded", f"{monthly['year_month'].nunique()}")

fig = px.line(monthly, x="year_month", y="violations", markers=True, title="Monthly moving violations")
fig.update_layout(xaxis_title="Month", yaxis_title="Violations")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Raw sample")
st.dataframe(df.head(100), use_container_width=True)
