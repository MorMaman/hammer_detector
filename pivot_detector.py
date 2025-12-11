"""
Pivot Point Detector Module
Detects swing highs (resistance pivots) and swing lows (support pivots)
using scipy's argrelextrema function - Finviz style
"""
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class PivotPoint:
    """Represents a pivot point (swing high or swing low)"""
    index: int          # Index in the dataframe
    date: pd.Timestamp  # Date of the pivot
    price: float        # Price at the pivot
    is_high: bool       # True for swing high (resistance), False for swing low (support)


def detect_pivot_highs(
    df: pd.DataFrame,
    lookback: int = 10,
    column: str = 'High',
    exclude_recent: bool = True
) -> List[PivotPoint]:
    """
    Detect swing highs (resistance pivots) - these form the BLUE trendline.
    A swing high is a point where the high is greater than 'lookback' bars on both sides.

    Args:
        df: DataFrame with OHLCV data
        lookback: Number of bars to look on each side (default 10 like Finviz)
        column: Column to use for detection ('High' for resistance)
        exclude_recent: If True, exclude pivots in the last 'lookback' bars (not yet confirmed)

    Returns:
        List of PivotPoint objects for swing highs
    """
    highs = df[column].values

    # Find local maxima
    pivot_indices = argrelextrema(highs, np.greater_equal, order=lookback)[0]

    # A pivot is only CONFIRMED if we have 'lookback' bars AFTER it
    # So we exclude any pivot in the last 'lookback' bars
    max_valid_index = len(df) - lookback - 1 if exclude_recent else len(df) - 1

    pivots = []
    for idx in pivot_indices:
        if idx <= max_valid_index:
            pivot = PivotPoint(
                index=idx,
                date=df.index[idx],
                price=highs[idx],
                is_high=True
            )
            pivots.append(pivot)

    return pivots


def detect_pivot_lows(
    df: pd.DataFrame,
    lookback: int = 10,
    column: str = 'Low',
    exclude_recent: bool = True
) -> List[PivotPoint]:
    """
    Detect swing lows (support pivots) - these form the PINK trendline.
    A swing low is a point where the low is less than 'lookback' bars on both sides.

    Args:
        df: DataFrame with OHLCV data
        lookback: Number of bars to look on each side (default 10 like Finviz)
        column: Column to use for detection ('Low' for support)
        exclude_recent: If True, exclude pivots in the last 'lookback' bars (not yet confirmed)

    Returns:
        List of PivotPoint objects for swing lows
    """
    lows = df[column].values

    # Find local minima
    pivot_indices = argrelextrema(lows, np.less_equal, order=lookback)[0]

    # A pivot is only CONFIRMED if we have 'lookback' bars AFTER it
    # So we exclude any pivot in the last 'lookback' bars
    max_valid_index = len(df) - lookback - 1 if exclude_recent else len(df) - 1

    pivots = []
    for idx in pivot_indices:
        if idx <= max_valid_index:
            pivot = PivotPoint(
                index=idx,
                date=df.index[idx],
                price=lows[idx],
                is_high=False
            )
            pivots.append(pivot)

    return pivots


def detect_all_pivots(
    df: pd.DataFrame,
    lookback: int = 10
) -> Tuple[List[PivotPoint], List[PivotPoint]]:
    """
    Detect both swing highs and swing lows.

    Args:
        df: DataFrame with OHLCV data
        lookback: Number of bars to look on each side

    Returns:
        Tuple of (pivot_highs, pivot_lows)
    """
    pivot_highs = detect_pivot_highs(df, lookback)
    pivot_lows = detect_pivot_lows(df, lookback)

    return pivot_highs, pivot_lows


def get_last_n_pivots(
    pivots: List[PivotPoint],
    n: int = 2,
    before_index: Optional[int] = None
) -> List[PivotPoint]:
    """
    Get the last N pivot points.
    For Finviz-style trendlines, we typically want the last 2 pivots.

    Args:
        pivots: List of PivotPoint objects
        n: Number of pivots to return
        before_index: Only consider pivots before this index (for historical analysis)

    Returns:
        List of the last N pivots, sorted by index (oldest first)
    """
    if before_index is not None:
        filtered = [p for p in pivots if p.index < before_index]
    else:
        filtered = pivots

    # Get last N pivots
    last_n = filtered[-n:] if len(filtered) >= n else filtered

    # Return sorted by index (oldest first)
    return sorted(last_n, key=lambda x: x.index)


def validate_pivots_for_trendline(
    pivots: List[PivotPoint],
    min_pivots: int = 2,
    min_bar_distance: int = 5
) -> bool:
    """
    Validate that pivots are suitable for drawing a trendline.

    Args:
        pivots: List of PivotPoint objects
        min_pivots: Minimum number of pivots required
        min_bar_distance: Minimum bars between pivots

    Returns:
        True if valid, False otherwise
    """
    if len(pivots) < min_pivots:
        return False

    # Check minimum distance between consecutive pivots
    for i in range(1, len(pivots)):
        if pivots[i].index - pivots[i-1].index < min_bar_distance:
            return False

    return True


def add_pivot_columns_to_df(df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
    """
    Add pivot point columns to the dataframe for easy visualization.

    Args:
        df: DataFrame with OHLCV data
        lookback: Lookback period for pivot detection

    Returns:
        DataFrame with added 'pivot_high' and 'pivot_low' columns
    """
    df = df.copy()
    df['pivot_high'] = np.nan
    df['pivot_low'] = np.nan

    pivot_highs = detect_pivot_highs(df, lookback)
    pivot_lows = detect_pivot_lows(df, lookback)

    for pivot in pivot_highs:
        df.loc[df.index[pivot.index], 'pivot_high'] = pivot.price

    for pivot in pivot_lows:
        df.loc[df.index[pivot.index], 'pivot_low'] = pivot.price

    return df


if __name__ == "__main__":
    # Test the pivot detector
    from data_fetcher import fetch_stock_data

    print("Testing pivot detector...")

    df = fetch_stock_data("AAPL", period="6mo")
    print(f"\nData shape: {df.shape}")

    pivot_highs, pivot_lows = detect_all_pivots(df, lookback=10)

    print(f"\nFound {len(pivot_highs)} swing highs (BLUE resistance pivots)")
    print(f"Found {len(pivot_lows)} swing lows (PINK support pivots)")

    print("\nLast 3 swing HIGHS (for BLUE resistance line):")
    for pivot in pivot_highs[-3:]:
        print(f"  Date: {pivot.date.strftime('%Y-%m-%d')}, Price: ${pivot.price:.2f}")

    print("\nLast 3 swing LOWS (for PINK support line):")
    for pivot in pivot_lows[-3:]:
        print(f"  Date: {pivot.date.strftime('%Y-%m-%d')}, Price: ${pivot.price:.2f}")

    # Test getting last 2 pivots for trendline
    last_2_highs = get_last_n_pivots(pivot_highs, n=2)
    print(f"\nLast 2 highs for BLUE resistance trendline:")
    for p in last_2_highs:
        print(f"  {p.date.strftime('%Y-%m-%d')}: ${p.price:.2f}")
