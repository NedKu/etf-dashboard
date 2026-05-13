# Stock PER / PBR Trend (Streamlit)

This project provides a Streamlit UI that:

- Downloads price/volume data from Yahoo Finance via `yfinance`
- Detects recent **high-volume breakout** days (vs 3-month average volume)
- Plots price with moving averages + confidence interval bands
- Computes **PER/PBR** using Yahoo Finance snapshot fundamentals (`trailingEps`, `bookValue`) and plots them with statistical bands

> Note: PER/PBR here are **not historical fundamentals**. They are derived from today’s fundamentals applied across the historical price series.

## Project layout

- [`app.py`](app.py:1): Streamlit entrypoint (thin wrapper)
- [`src/stock_per_pbr_trend/`](src/stock_per_pbr_trend/__init__.py:1): package code
  - [`analysis.py`](src/stock_per_pbr_trend/analysis.py:1): data fetch + calculations
  - [`charting.py`](src/stock_per_pbr_trend/charting.py:1): Plotly figure builders
  - [`app_streamlit.py`](src/stock_per_pbr_trend/app_streamlit.py:1): Streamlit UI logic
- [`tests/`](tests/test_analysis_smoke.py:1): minimal pytest smoke tests
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml:1): GitHub Actions CI (ruff + pytest)

## Requirements

- Windows 10
- Python 3.10+ (recommended 3.11)

## Setup: create `.venv_per_pbr`

From the repo root:

```bat
cd STOCK_PER_PBR_Trend
py -m venv .venv_per_pbr
.venv_per_pbr\Scripts\python -m pip install --upgrade pip
.venv_per_pbr\Scripts\pip install -e .
```

### Dev tools (optional)

```bat
.venv_per_pbr\Scripts\pip install -e .[dev]
.venv_per_pbr\Scripts\pre-commit install
```

## Run the app

```bat
cd STOCK_PER_PBR_Trend
.venv_per_pbr\Scripts\streamlit run app.py
```

## Ticker format examples

- Taiwan stocks: `2330.TW`, `0050.TW`
- US stocks/ETFs: `AAPL`, `MSFT`, `SPY`
- Indices: `^STI`
- LSE tickers often end with `.L` (example: `VWRA.L`)

## Troubleshooting

### `ModuleNotFoundError: stock_per_pbr_trend`

Ensure you installed the project in editable mode:

```bat
cd STOCK_PER_PBR_Trend
.venv_per_pbr\Scripts\pip install -e .
```

### PER/PBR not available

Some tickers don’t have `trailingEps` and/or `bookValue` in Yahoo Finance. In that case the app will show a warning and skip PER/PBR plots.

## Lint / test

```bat
cd STOCK_PER_PBR_Trend
.venv_per_pbr\Scripts\ruff check .
.venv_per_pbr\Scripts\ruff format --check .
.venv_per_pbr\Scripts\pytest -q
```
