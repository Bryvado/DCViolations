# DC Violations

Starter project for automatically querying Washington DC moving violations data from ArcGIS and visualizing it in a simple web app.

## Key fix for stability

Default refresh mode now pulls **monthly counts only** (not every row), which avoids out-of-memory kills and keeps Streamlit responsive.

If you truly need full row-level data, use the optional `--raw` flag.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/update_data.py --years 2024 2025
streamlit run app.py
```

## Useful commands

Refresh monthly summary (default):

```bash
python scripts/update_data.py --years 2025 --months 0 1 --output data/violations_monthly_latest.parquet
```

`--months` accepts ArcGIS layer IDs `0..11` and now validates invalid values early.

Full raw pull (heavy; may consume significant memory):

```bash
python scripts/update_data.py --raw --years 2025 --months 0 1 --output data/violations_raw.parquet
```

## Data services used

- `Violations_Moving_2024`
- `Violations_Moving_2025`

Both are queried month-by-month as ArcGIS map layers (`0..11`).
