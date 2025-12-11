"""
Data Fetcher Module
Fetches OHLCV data from Yahoo Finance using yfinance
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


def fetch_stock_data(
    symbol: str,
    period: str = "6mo",
    interval: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Fetch OHLCV data for a stock symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
        period: Time period to fetch (e.g., '1mo', '3mo', '6mo', '1y', '2y', '5y')
        interval: Data interval ('1d', '1h', '5m', etc.)
        start_date: Optional start date (YYYY-MM-DD format)
        end_date: Optional end date (YYYY-MM-DD format)

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    ticker = yf.Ticker(symbol)

    if start_date and end_date:
        df = ticker.history(start=start_date, end=end_date, interval=interval)
    else:
        df = ticker.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No data found for symbol: {symbol}")

    # Clean up the dataframe
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize(None)  # Remove timezone info for easier handling

    return df


def fetch_multiple_stocks(
    symbols: list,
    period: str = "6mo",
    interval: str = "1d"
) -> dict:
    """
    Fetch data for multiple stock symbols.

    Args:
        symbols: List of stock ticker symbols
        period: Time period to fetch
        interval: Data interval

    Returns:
        Dictionary mapping symbol -> DataFrame
    """
    results = {}

    for symbol in symbols:
        try:
            df = fetch_stock_data(symbol, period=period, interval=interval)
            results[symbol] = df
            print(f"Fetched {len(df)} bars for {symbol}")
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            results[symbol] = None

    return results


def get_latest_bars(symbol: str, num_bars: int = 100) -> pd.DataFrame:
    """
    Get the latest N bars for a symbol.

    Args:
        symbol: Stock ticker symbol
        num_bars: Number of bars to fetch

    Returns:
        DataFrame with the latest bars
    """
    # Fetch extra data to ensure we have enough after market hours filtering
    df = fetch_stock_data(symbol, period="1y", interval="1d")
    return df.tail(num_bars)


if __name__ == "__main__":
    # Test the data fetcher
    print("Testing data fetcher...")

    # Test single stock
    df = fetch_stock_data("AAPL", period="3mo")
    print(f"\nAAPL data shape: {df.shape}")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"\nLast 5 bars:")
    print(df.tail())
