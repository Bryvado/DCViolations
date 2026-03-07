from __future__ import annotations

import pandas as pd


def build_monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["year_month", "violations"])

    if "violations" in df.columns:
        grouped = (
            df[["source_year", "source_month_num", "violations"]]
            .copy()
            .groupby(["source_year", "source_month_num"], dropna=False, as_index=False)["violations"]
            .sum()
            .sort_values(["source_year", "source_month_num"])
        )
    else:
        grouped = (
            df.groupby(["source_year", "source_month_num"], dropna=False)
            .size()
            .reset_index(name="violations")
            .sort_values(["source_year", "source_month_num"])
        )

    grouped["year_month"] = pd.to_datetime(
        grouped["source_year"].astype(int).astype(str)
        + "-"
        + grouped["source_month_num"].astype(int).astype(str).str.zfill(2)
        + "-01"
    )
    return grouped[["year_month", "violations"]]
