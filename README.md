# DC Violations

Basic starter project for automatically querying Washington DC moving violations data from ArcGIS and visualizing it in a simple web app.

## What this includes

- ArcGIS downloader with retries + pagination.
- Parallel month-level fetch for yearly services.
- CLI script to refresh local parquet data.
- Streamlit app with a very basic monthly trend line.
- GitHub Actions workflow to refresh data on a daily schedule.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/update_data.py --years 2024 2025
streamlit run app.py
```

## Useful commands

Refresh only a few months while testing:

```bash
python scripts/update_data.py --years 2025 --months 0 1 --output data/test.parquet
```

Change the ArcGIS filter window with `--where`:

```bash
python scripts/update_data.py --where "TICKETISSUEDATE >= DATE '2025-01-01'"
```

## Data services used

- `Violations_Moving_2024`
- `Violations_Moving_2025`

Both are queried month-by-month as ArcGIS map layers (`0..11`).
