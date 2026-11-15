import os
import glob
import concurrent.futures
import yfinance as yf
import pandas as pd
from crewai.tools import tool

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
STOCKS_DIR = os.path.join(DATA_DIR, "nifty100")
MASTER_CSV_PATH = os.path.join(DATA_DIR, "nifty100_list.csv")


def clean_existing_data():
    """Removes stale downloaded stock CSVs."""
    if os.path.exists(STOCKS_DIR):
        old_files = glob.glob(os.path.join(STOCKS_DIR, "*.csv"))
        for f in old_files:
            try:
                os.remove(f)
            except Exception:
                pass
        print(f"[Cleanup] Cleared {len(old_files)} previous stock CSV files.", flush=True)


def get_nifty100_symbols() -> list[str]:
    """Reads ticker symbols directly from nifty100_list.csv."""
    if not os.path.exists(MASTER_CSV_PATH):
        raise FileNotFoundError(f"Ticker file not found: {MASTER_CSV_PATH}")

    with open(MASTER_CSV_PATH, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        raise ValueError(f"No tickers found in {MASTER_CSV_PATH}")

    # Ensure symbols end with .NS for Yahoo Finance
    tickers = [sym if sym.endswith(".NS") else f"{sym}.NS" for sym in lines]
    print(f"[Constituents] Loaded {len(tickers)} tickers from {MASTER_CSV_PATH}", flush=True)
    return tickers


def _download_single_ticker(symbol: str, period: str) -> tuple[str, bool, str]:
    """Helper to download a single ticker's data and save to CSV."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if not df.empty and "Close" in df.columns:
            filepath = os.path.join(STOCKS_DIR, f"{symbol}.csv")
            df.to_csv(filepath)
            return symbol, True, f"{len(df)} trading days"
        return symbol, False, "Empty data received"
    except Exception as e:
        return symbol, False, str(e)


@tool("Download Nifty 100 CSVs")
def download_nifty_csvs_tool(period: str = "6mo") -> str:
    """Purges stale data and downloads 6-month price history CSVs for all 100 Nifty constituents."""
    print("\n" + "=" * 65, flush=True)
    print(">>> [TOOL 1/2] STARTING NIFTY 100 DATA DOWNLOAD", flush=True)
    print("=" * 65, flush=True)

    clean_existing_data()
    os.makedirs(STOCKS_DIR, exist_ok=True)

    tickers = get_nifty100_symbols()
    total = len(tickers)
    print(f"[Downloader] Starting parallel download for {total} stocks (period='{period}')...\n", flush=True)

    downloaded = []
    failed = []

    # Parallel download with ThreadPoolExecutor (10 parallel workers for 10x speedup)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {
            executor.submit(_download_single_ticker, sym, period): sym for sym in tickers
        }

        for i, future in enumerate(concurrent.futures.as_completed(future_to_symbol), 1):
            symbol, success, msg = future.result()
            if success:
                downloaded.append(symbol)
                print(f"[{i:02d}/{total:02d}] ✓ {symbol:<16} : {msg}", flush=True)
            else:
                failed.append(symbol)
                print(f"[{i:02d}/{total:02d}] ✗ {symbol:<16} : Failed ({msg})", flush=True)

    summary = (
        f"\n>>> [Download Complete] Successfully saved {len(downloaded)}/{total} "
        f"stock CSV files into: {STOCKS_DIR}"
    )
    if failed:
        summary += f" (Failed: {len(failed)})"
    print(summary, flush=True)
    print("=" * 65 + "\n", flush=True)
    return summary


@tool("Calculate Momentum")
def calculate_momentum_tool(top_n: int = 10) -> str:
    """Reads saved stock CSV files, computes momentum factors,
    and returns a ranked summary table of top momentum stocks.
    """
    print("\n" + "=" * 65, flush=True)
    print(">>> [TOOL 2/2] STARTING QUANTITATIVE MOMENTUM CALCULATION", flush=True)
    print("=" * 65, flush=True)

    results = []

    if not os.path.exists(STOCKS_DIR):
        return f"Stock directory not found: {STOCKS_DIR}. Please run download tool first."

    csv_files = [f for f in os.listdir(STOCKS_DIR) if f.endswith(".csv")]
    print(f"[Analyst] Found {len(csv_files)} CSV files to evaluate...", flush=True)

    for i, file in enumerate(csv_files, 1):
        symbol = file.replace(".csv", "")
        filepath = os.path.join(STOCKS_DIR, file)

        try:
            df = pd.read_csv(filepath)
        except Exception:
            continue

        if "Close" not in df.columns:
            continue

        closes = df["Close"].dropna()
        if len(closes) < 30:
            continue

        # 1. Price Returns
        total_return = ((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]) * 100
        recent_1m = (
            ((closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20]) * 100
            if len(closes) >= 20
            else total_return
        )

        # 2. 14-day RSI
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        current_rsi = (
            float(rsi_series.iloc[-1])
            if not pd.isna(rsi_series.iloc[-1])
            else 50.0
        )

        # 3. 50-day Moving Average Trend
        sma50 = (
            closes.rolling(window=50).mean().iloc[-1]
            if len(closes) >= 50
            else closes.mean()
        )
        above_sma50_pct = ((closes.iloc[-1] - sma50) / sma50) * 100

        # Weighted Composite Momentum Score
        score = (0.5 * total_return) + (0.3 * recent_1m) + (0.2 * (current_rsi - 50))

        results.append({
            "Symbol": symbol,
            "Latest Close": round(float(closes.iloc[-1]), 2),
            "Total Return (%)": round(total_return, 2),
            "1-Month Return (%)": round(recent_1m, 2),
            "14D RSI": round(current_rsi, 2),
            "Vs 50-SMA (%)": round(above_sma50_pct, 2),
            "Momentum Score": round(score, 2),
        })

    if not results:
        print("[Analyst] No valid stock data found to evaluate.", flush=True)
        return "No valid stock CSV data found to evaluate."

    print(f"[Analyst] Evaluated {len(results)} stocks successfully. Ranking top candidates...", flush=True)

    # Rank descending by Momentum Score
    ranked_df = pd.DataFrame(results).sort_values(by="Momentum Score", ascending=False)
    top_candidates = ranked_df.head(top_n)

    print("\n>>> [Preview] Top 5 Momentum Leaders:", flush=True)
    for idx, row in top_candidates.head(5).iterrows():
        print(
            f"   • {row['Symbol']:<15} Score: {row['Momentum Score']:>6.2f} | "
            f"Total Return: {row['Total Return (%)']:>6.2f}% | RSI: {row['14D RSI']:>5.2f}",
            flush=True,
        )

    print("=" * 65 + "\n", flush=True)
    return top_candidates.to_markdown(index=False)
