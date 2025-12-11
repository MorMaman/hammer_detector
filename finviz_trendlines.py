"""
Finviz-Style Trendline Calculator V2
Uses envelope fitting on price channel like Finviz
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import argrelextrema
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FinvizTrendline:
    """Represents a Finviz-style trendline"""
    slope: float
    intercept: float
    start_index: int
    end_index: int
    touches: int
    is_upper: bool
    r_squared: float

    def get_price_at_index(self, idx: int) -> float:
        return self.slope * idx + self.intercept

    def distance_pct(self, price: float, idx: int) -> float:
        line_price = self.get_price_at_index(idx)
        if line_price <= 0:
            return 999
        return ((price - line_price) / line_price) * 100


def find_significant_highs(df: pd.DataFrame, window: int = 10) -> List[Tuple[int, float]]:
    """Find significant high points"""
    highs = df['High'].values
    indices = argrelextrema(highs, np.greater_equal, order=window)[0]
    return [(i, highs[i]) for i in indices]


def find_significant_lows(df: pd.DataFrame, window: int = 10) -> List[Tuple[int, float]]:
    """Find significant low points"""
    lows = df['Low'].values
    indices = argrelextrema(lows, np.less_equal, order=window)[0]
    return [(i, lows[i]) for i in indices]


def fit_upper_envelope(
    df: pd.DataFrame,
    lookback: int = 100,
    min_touches: int = 2
) -> Optional[FinvizTrendline]:
    """
    Fit upper envelope trendline (BLUE resistance).

    Method: Find swing highs and fit a line that best represents
    the upper boundary of price action.
    """
    # Work with recent data
    start_idx = max(0, len(df) - lookback)
    df_work = df.iloc[start_idx:].copy()
    df_work = df_work.reset_index(drop=True)

    # Find swing highs with multiple window sizes
    all_highs = []
    for w in [5, 10, 15]:
        highs = find_significant_highs(df_work, window=w)
        all_highs.extend(highs)

    # Remove duplicates and sort
    seen = set()
    unique_highs = []
    for idx, price in sorted(all_highs):
        if idx not in seen:
            seen.add(idx)
            unique_highs.append((idx, price))

    if len(unique_highs) < 2:
        return None

    # Try fitting line through different combinations of highs
    best_line = None
    best_score = -float('inf')

    n_points = len(unique_highs)

    for i in range(n_points - 1):
        for j in range(i + 1, n_points):
            idx1, price1 = unique_highs[i]
            idx2, price2 = unique_highs[j]

            if idx2 == idx1:
                continue

            # Calculate line through these two points
            slope = (price2 - price1) / (idx2 - idx1)
            intercept = price1 - slope * idx1

            # Count how many highs are ON or BELOW this line (valid for upper envelope)
            touches = 0
            violations = 0

            for idx, price in unique_highs:
                line_price = slope * idx + intercept
                diff_pct = (price - line_price) / line_price * 100 if line_price > 0 else 0

                if diff_pct >= -1.5 and diff_pct <= 1.5:  # Within 1.5%
                    touches += 1
                elif diff_pct > 1.5:  # Price above line = violation
                    violations += 1

            # Score: more touches, fewer violations
            score = touches * 10 - violations * 20

            if touches >= min_touches and score > best_score:
                best_score = score
                best_line = FinvizTrendline(
                    slope=slope,
                    intercept=intercept,
                    start_index=start_idx + idx1,
                    end_index=len(df) - 1,
                    touches=touches,
                    is_upper=True,
                    r_squared=0.9  # Simplified
                )

    return best_line


def fit_lower_envelope(
    df: pd.DataFrame,
    lookback: int = 100,
    min_touches: int = 2
) -> Optional[FinvizTrendline]:
    """
    Fit lower envelope trendline (PINK support).
    """
    start_idx = max(0, len(df) - lookback)
    df_work = df.iloc[start_idx:].copy()
    df_work = df_work.reset_index(drop=True)

    # Find swing lows
    all_lows = []
    for w in [5, 10, 15]:
        lows = find_significant_lows(df_work, window=w)
        all_lows.extend(lows)

    seen = set()
    unique_lows = []
    for idx, price in sorted(all_lows):
        if idx not in seen:
            seen.add(idx)
            unique_lows.append((idx, price))

    if len(unique_lows) < 2:
        return None

    best_line = None
    best_score = -float('inf')

    n_points = len(unique_lows)

    for i in range(n_points - 1):
        for j in range(i + 1, n_points):
            idx1, price1 = unique_lows[i]
            idx2, price2 = unique_lows[j]

            if idx2 == idx1:
                continue

            slope = (price2 - price1) / (idx2 - idx1)
            intercept = price1 - slope * idx1

            touches = 0
            violations = 0

            for idx, price in unique_lows:
                line_price = slope * idx + intercept
                if line_price <= 0:
                    continue
                diff_pct = (price - line_price) / line_price * 100

                if diff_pct >= -1.5 and diff_pct <= 1.5:
                    touches += 1
                elif diff_pct < -1.5:  # Price below line = violation
                    violations += 1

            score = touches * 10 - violations * 20

            if touches >= min_touches and score > best_score:
                best_score = score
                best_line = FinvizTrendline(
                    slope=slope,
                    intercept=intercept,
                    start_index=start_idx + idx1,
                    end_index=len(df) - 1,
                    touches=touches,
                    is_upper=False,
                    r_squared=0.9
                )

    return best_line


def analyze_stock(symbol: str, df: pd.DataFrame) -> dict:
    """
    Analyze a stock for trendlines and proximity.
    """
    upper = fit_upper_envelope(df, lookback=150)
    lower = fit_lower_envelope(df, lookback=150)

    current_high = df['High'].iloc[-1]
    current_low = df['Low'].iloc[-1]
    current_close = df['Close'].iloc[-1]
    current_idx = len(df) - 1

    result = {
        'symbol': symbol,
        'current_close': current_close,
        'upper_line': None,
        'lower_line': None,
        'upper_distance': None,
        'lower_distance': None,
        'near_upper': False,
        'near_lower': False
    }

    if upper:
        upper_price = upper.get_price_at_index(current_idx)
        upper_dist = (current_high - upper_price) / upper_price * 100 if upper_price > 0 else 999
        result['upper_line'] = upper_price
        result['upper_distance'] = upper_dist
        result['near_upper'] = abs(upper_dist) <= 2.0
        result['upper_slope'] = upper.slope
        result['upper_touches'] = upper.touches

    if lower:
        lower_price = lower.get_price_at_index(current_idx)
        lower_dist = (current_low - lower_price) / lower_price * 100 if lower_price > 0 else 999
        result['lower_line'] = lower_price
        result['lower_distance'] = lower_dist
        result['near_lower'] = abs(lower_dist) <= 2.0
        result['lower_slope'] = lower.slope
        result['lower_touches'] = lower.touches

    return result


if __name__ == "__main__":
    from data_fetcher import fetch_stock_data

    print("="*70)
    print("Finviz-Style Trendline Analysis")
    print("Testing with REAL Finviz Wedge Up stocks")
    print("="*70)

    # Real Finviz wedge up stocks
    stocks = ['AMAT', 'AVGO', 'BAC', 'AXP', 'ASML', 'AZN']

    for symbol in stocks:
        print(f"\n{symbol}")
        print("-"*50)

        try:
            df = fetch_stock_data(symbol, period='1y')
            result = analyze_stock(symbol, df)

            print(f"Current close: ${result['current_close']:.2f}")

            if result['upper_line']:
                print(f"\nUPPER (BLUE) Resistance:")
                print(f"  Line at: ${result['upper_line']:.2f}")
                print(f"  High distance: {result['upper_distance']:.2f}%")
                print(f"  Slope: {result.get('upper_slope', 0):.4f}")
                print(f"  Touches: {result.get('upper_touches', 0)}")
                if result['near_upper']:
                    print(f"  >>> NEAR RESISTANCE <<<")

            if result['lower_line']:
                print(f"\nLOWER (PINK) Support:")
                print(f"  Line at: ${result['lower_line']:.2f}")
                print(f"  Low distance: {result['lower_distance']:.2f}%")
                print(f"  Slope: {result.get('lower_slope', 0):.4f}")
                print(f"  Touches: {result.get('lower_touches', 0)}")
                if result['near_lower']:
                    print(f"  >>> NEAR SUPPORT <<<")

        except Exception as e:
            print(f"Error: {e}")
