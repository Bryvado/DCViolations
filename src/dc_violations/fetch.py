from __future__ import annotations

import argparse
import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

SERVICE_URLS = {
    2024: "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Violations_Moving_2024/MapServer",
    2025: "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Violations_Moving_2025/MapServer",
}

MONTHS = {
    0: "January",
    1: "February",
    2: "March",
    3: "April",
    4: "May",
    5: "June",
    6: "July",
    7: "August",
    8: "September",
    9: "October",
    10: "November",
    11: "December",
}


@dataclass
class FetchConfig:
    page_size: int = 2000
    timeout_seconds: int = 120
    max_retries: int = 5
    pause_between_pages_seconds: float = 0.0
    max_workers: int = 2


def normalize_month_ids(month_ids: Iterable[int] | None) -> list[int]:
    if month_ids is None:
        return list(MONTHS.keys())

    normalized = sorted(set(month_ids))
    invalid = [month_id for month_id in normalized if month_id not in MONTHS]
    if invalid:
        raise ValueError(f"Invalid month layer IDs: {invalid}. Expected values in 0..11")
    return normalized


def arcgis_get(url: str, params: dict, timeout: int = 120, max_retries: int = 5) -> dict:
    """Retry wrapper for ArcGIS REST requests."""
    last_err = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            sleep_seconds = min(2**attempt, 20)
            print(f"Retry {attempt + 1}/{max_retries} for {url} after error: {exc}")
            time.sleep(sleep_seconds)

    if last_err is None:
        raise RuntimeError("ArcGIS request failed without details")
    raise last_err


def fetch_layer_count(
    service_url: str,
    layer_id: int,
    where: str = "1=1",
    timeout: int = 120,
    max_retries: int = 5,
) -> int:
    query_url = f"{service_url}/{layer_id}/query"
    count_params = {
        "f": "json",
        "where": where,
        "returnCountOnly": "true",
    }
    count_data = arcgis_get(query_url, count_params, timeout=timeout, max_retries=max_retries)
    return int(count_data.get("count", 0))


def fetch_layer_records(
    service_url: str,
    layer_id: int,
    where: str = "1=1",
    page_size: int = 2000,
    pause: float = 0,
    timeout: int = 120,
    max_retries: int = 5,
) -> pd.DataFrame:
    """Download one ArcGIS layer using resultOffset/resultRecordCount pagination."""
    query_url = f"{service_url}/{layer_id}/query"

    total = fetch_layer_count(service_url, layer_id, where=where, timeout=timeout, max_retries=max_retries)
    print(f"Layer {layer_id}: {total:,} rows")

    frames: list[pd.DataFrame] = []
    offset = 0

    while offset < total:
        params = {
            "f": "json",
            "where": where,
            "outFields": "*",
            "returnGeometry": "false",
            "orderByFields": "OBJECTID ASC",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        data = arcgis_get(query_url, params, timeout=timeout, max_retries=max_retries)
        features = data.get("features", [])

        if not features:
            break

        rows = [feature.get("attributes", {}) for feature in features]
        if rows:
            frames.append(pd.DataFrame(rows))

        offset += len(rows)
        print(f"  downloaded {offset:,} / {total:,}")
        time.sleep(pause)

    non_empty_frames = [frame for frame in frames if not frame.empty and not frame.isna().all(axis=1).all()]
    if non_empty_frames:
        return pd.concat(non_empty_frames, ignore_index=True)
    return pd.DataFrame()


def fetch_month(year: int, layer_id: int, config: FetchConfig, where: str = "1=1") -> pd.DataFrame:
    df = fetch_layer_records(
        SERVICE_URLS[year],
        layer_id,
        where=where,
        page_size=config.page_size,
        pause=config.pause_between_pages_seconds,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )
    if df.empty:
        return df

    df["source_year"] = year
    df["source_month"] = MONTHS[layer_id]
    df["source_month_num"] = layer_id + 1
    df["source_layer_id"] = layer_id
    return df


def fetch_month_summary(year: int, layer_id: int, config: FetchConfig, where: str = "1=1") -> pd.DataFrame:
    count = fetch_layer_count(
        SERVICE_URLS[year],
        layer_id,
        where=where,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )
    return pd.DataFrame(
        {
            "source_year": [year],
            "source_month": [MONTHS[layer_id]],
            "source_month_num": [layer_id + 1],
            "source_layer_id": [layer_id],
            "violations": [count],
        }
    )


def fetch_year_parallel(
    year: int,
    config: FetchConfig,
    where: str = "1=1",
    month_ids: Iterable[int] | None = None,
    summary_only: bool = True,
) -> pd.DataFrame:
    if year not in SERVICE_URLS:
        raise KeyError(f"No ArcGIS service configured for year={year}")

    frames = []
    selected_months = normalize_month_ids(month_ids)
    max_workers = max(1, min(config.max_workers, len(selected_months)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if summary_only:
            futures = {
                executor.submit(fetch_month_summary, year, month_id, config, where): month_id
                for month_id in selected_months
            }
        else:
            futures = {
                executor.submit(fetch_month, year, month_id, config, where): month_id
                for month_id in selected_months
            }

        for future in as_completed(futures):
            month_id = futures[future]
            month_name = MONTHS.get(month_id, f"month-{month_id}")
            try:
                df = future.result()
                if summary_only:
                    month_count = int(df["violations"].iloc[0]) if not df.empty else 0
                    print(f"Finished {month_name} {year}: {month_count:,} rows")
                else:
                    print(f"Finished {month_name} {year}: {len(df):,} rows")
                if not df.empty:
                    frames.append(df)
            except Exception as exc:  # noqa: BLE001
                print(f"Failed {month_name} {year}: {exc}")

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["source_year", "source_month_num"])


def available_years() -> list[int]:
    return sorted(SERVICE_URLS.keys())


def default_year_window() -> list[int]:
    now = dt.datetime.now(dt.timezone.utc)
    valid_years = available_years()
    if now.year in valid_years:
        previous_year = now.year - 1
        return [year for year in [previous_year, now.year] if year in valid_years]
    return valid_years[-2:] if len(valid_years) > 1 else valid_years


def refresh_dataset(
    years: Iterable[int] | None = None,
    output_path: str = "data/violations_monthly_latest.parquet",
    where: str = "1=1",
    month_ids: Iterable[int] | None = None,
    config: FetchConfig | None = None,
    summary_only: bool = True,
) -> pd.DataFrame:
    config = config or FetchConfig()
    years_to_pull = list(years) if years is not None else default_year_window()

    frames = [
        fetch_year_parallel(year, config=config, where=where, month_ids=month_ids, summary_only=summary_only)
        for year in years_to_pull
    ]
    frames = [frame for frame in frames if not frame.empty]

    if not frames:
        raise RuntimeError("No rows downloaded for the requested year/month window")

    combined = pd.concat(frames, ignore_index=True)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output, index=False)
    print(f"Saved {len(combined):,} rows to {output}")
    return combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download DC moving violations data and persist parquet output")
    parser.add_argument("--years", nargs="+", type=int, default=None, help="Year list, e.g. --years 2024 2025")
    parser.add_argument(
        "--months",
        nargs="+",
        type=int,
        default=None,
        help="Optional month layer IDs in [0..11], e.g. --months 0 1 2",
    )
    parser.add_argument("--where", default="1=1", help="ArcGIS where clause")
    parser.add_argument("--output", default="data/violations_monthly_latest.parquet", help="Parquet output path")
    parser.add_argument("--page-size", type=int, default=2000)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Fetch full row-level data instead of monthly counts (uses much more memory)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = FetchConfig(
        page_size=args.page_size,
        timeout_seconds=args.timeout,
        max_retries=args.max_retries,
        max_workers=args.max_workers,
    )
    refresh_dataset(
        years=args.years,
        output_path=args.output,
        where=args.where,
        month_ids=args.months,
        config=config,
        summary_only=not args.raw,
    )


if __name__ == "__main__":
    main()
