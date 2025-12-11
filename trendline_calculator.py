"""
Trendline Calculator Module
Calculates trendlines using linear regression - Finviz style
BLUE (resistance) is MORE IMPORTANT than PINK (support)
"""
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from dataclasses import dataclass
from pivot_detector import PivotPoint, detect_pivot_highs, detect_pivot_lows, get_last_n_pivots


@dataclass
class Trendline:
    """Represents a calculated trendline"""
    slope: float              # Slope of the line (price change per bar)
    intercept: float          # Y-intercept (price at bar 0)
    start_index: int          # Starting bar index
    end_index: int            # Ending bar index
    start_price: float        # Price at start
    end_price: float          # Price at end
    pivot_points: List[PivotPoint]  # Pivot points used to draw the line
    is_resistance: bool       # True for BLUE resistance, False for PINK support
    r_squared: float          # R-squared value (goodness of fit)
    angle_degrees: float      # Angle in degrees

    def get_price_at_index(self, index: int) -> float:
        """Get the trendline price at any bar index"""
        return self.slope * index + self.intercept

    def get_price_at_bar(self, bar_index: int) -> float:
        """Get the trendline price at a specific bar index"""
        return self.slope * bar_index + self.intercept

    def is_broken(self, price: float, index: int, tolerance: float = 0.002) -> bool:
        """
        Check if the trendline is broken at a given price and index.
        Uses 0.2% tolerance like Finviz to avoid false breaks.

        For resistance (BLUE): broken if price > trendline_price * (1 + tolerance)
        For support (PINK): broken if price < trendline_price * (1 - tolerance)
        """
        trendline_price = self.get_price_at_index(index)

        if self.is_resistance:
            return price > trendline_price * (1 + tolerance)
        else:
            return price < trendline_price * (1 - tolerance)

    def distance_from_line(self, price: float, index: int) -> float:
        """Calculate distance from price to trendline (positive = above, negative = below)"""
        trendline_price = self.get_price_at_index(index)
        return price - trendline_price

    def percentage_distance(self, price: float, index: int) -> float:
        """Calculate percentage distance from trendline"""
        trendline_price = self.get_price_at_index(index)
        return ((price - trendline_price) / trendline_price) * 100


def calculate_linear_regression(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """
    Calculate linear regression using least squares method.
    Formula: y = mx + b
    slope (m) = (N*sum(xy) - sum(x)*sum(y)) / (N*sum(x^2) - (sum(x))^2)
    intercept (b) = (sum(y) - m*sum(x)) / N

    Args:
        x: Array of x values (bar indices)
        y: Array of y values (prices)

    Returns:
        Tuple of (slope, intercept, r_squared)
    """
    n = len(x)

    if n < 2:
        raise ValueError("Need at least 2 points for linear regression")

    sum_x = np.sum(x)
    sum_y = np.sum(y)
    sum_xy = np.sum(x * y)
    sum_x_sq = np.sum(x ** 2)
    sum_y_sq = np.sum(y ** 2)

    # Calculate slope
    denominator = n * sum_x_sq - sum_x ** 2
    if denominator == 0:
        slope = 0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator

    # Calculate intercept
    intercept = (sum_y - slope * sum_x) / n

    # Calculate R-squared (coefficient of determination)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    if ss_tot == 0:
        r_squared = 1.0
    else:
        r_squared = 1 - (ss_res / ss_tot)

    return slope, intercept, r_squared


def calculate_angle_degrees(slope: float, price_scale: float = 1.0) -> float:
    """
    Calculate the angle of the trendline in degrees.
    Note: This is a simplified calculation. True visual angle depends on chart scaling.

    Args:
        slope: Slope of the trendline
        price_scale: Optional price scaling factor

    Returns:
        Angle in degrees (-90 to 90)
    """
    # Normalize slope to get meaningful angle
    # Typical good trendlines have 30-45 degree angles
    angle_rad = np.arctan(slope * price_scale * 100)  # Scale factor for visualization
    return np.degrees(angle_rad)


def calculate_resistance_trendline(
    df: pd.DataFrame,
    lookback: int = 10,
    num_pivots: int = 2,
    extend_bars: int = 10
) -> Optional[Trendline]:
    """
    Calculate BLUE resistance trendline from swing highs.
    This is the MORE IMPORTANT trendline per user request.

    Finviz style: Connect the last 2 swing highs.

    Args:
        df: DataFrame with OHLCV data
        lookback: Pivot detection lookback period
        num_pivots: Number of pivot points to use (default 2 for Finviz style)
        extend_bars: Number of bars to extend the line into the future

    Returns:
        Trendline object or None if insufficient pivots
    """
    pivot_highs = detect_pivot_highs(df, lookback)

    if len(pivot_highs) < num_pivots:
        return None

    # Get the last N pivot highs
    pivots = get_last_n_pivots(pivot_highs, n=num_pivots)

    # Extract x (indices) and y (prices) for regression
    x = np.array([p.index for p in pivots])
    y = np.array([p.price for p in pivots])

    # Calculate linear regression
    slope, intercept, r_squared = calculate_linear_regression(x, y)

    # Calculate angle
    avg_price = np.mean(y)
    angle = calculate_angle_degrees(slope / avg_price)

    # Calculate extended end point
    end_index = len(df) - 1 + extend_bars
    end_price = slope * end_index + intercept

    return Trendline(
        slope=slope,
        intercept=intercept,
        start_index=pivots[0].index,
        end_index=end_index,
        start_price=pivots[0].price,
        end_price=end_price,
        pivot_points=pivots,
        is_resistance=True,
        r_squared=r_squared,
        angle_degrees=angle
    )


def calculate_support_trendline(
    df: pd.DataFrame,
    lookback: int = 10,
    num_pivots: int = 2,
    extend_bars: int = 10
) -> Optional[Trendline]:
    """
    Calculate PINK support trendline from swing lows.

    Finviz style: Connect the last 2 swing lows.

    Args:
        df: DataFrame with OHLCV data
        lookback: Pivot detection lookback period
        num_pivots: Number of pivot points to use (default 2 for Finviz style)
        extend_bars: Number of bars to extend the line into the future

    Returns:
        Trendline object or None if insufficient pivots
    """
    pivot_lows = detect_pivot_lows(df, lookback)

    if len(pivot_lows) < num_pivots:
        return None

    # Get the last N pivot lows
    pivots = get_last_n_pivots(pivot_lows, n=num_pivots)

    # Extract x (indices) and y (prices) for regression
    x = np.array([p.index for p in pivots])
    y = np.array([p.price for p in pivots])

    # Calculate linear regression
    slope, intercept, r_squared = calculate_linear_regression(x, y)

    # Calculate angle
    avg_price = np.mean(y)
    angle = calculate_angle_degrees(slope / avg_price)

    # Calculate extended end point
    end_index = len(df) - 1 + extend_bars
    end_price = slope * end_index + intercept

    return Trendline(
        slope=slope,
        intercept=intercept,
        start_index=pivots[0].index,
        end_index=end_index,
        start_price=pivots[0].price,
        end_price=end_price,
        pivot_points=pivots,
        is_resistance=False,
        r_squared=r_squared,
        angle_degrees=angle
    )


def calculate_both_trendlines(
    df: pd.DataFrame,
    lookback: int = 10,
    num_pivots: int = 2,
    extend_bars: int = 10
) -> Tuple[Optional[Trendline], Optional[Trendline]]:
    """
    Calculate both resistance (BLUE) and support (PINK) trendlines.

    Args:
        df: DataFrame with OHLCV data
        lookback: Pivot detection lookback period
        num_pivots: Number of pivot points to use
        extend_bars: Number of bars to extend lines

    Returns:
        Tuple of (resistance_trendline, support_trendline)
    """
    resistance = calculate_resistance_trendline(df, lookback, num_pivots, extend_bars)
    support = calculate_support_trendline(df, lookback, num_pivots, extend_bars)

    return resistance, support


def get_trendline_values_for_df(
    df: pd.DataFrame,
    trendline: Trendline
) -> pd.Series:
    """
    Get trendline values for each bar in the dataframe.

    Args:
        df: DataFrame with OHLCV data
        trendline: Trendline object

    Returns:
        Series with trendline values for each bar
    """
    indices = np.arange(len(df))
    values = trendline.slope * indices + trendline.intercept

    # Set NaN for bars before the trendline starts
    values[:trendline.start_index] = np.nan

    return pd.Series(values, index=df.index)


def add_trendline_columns_to_df(
    df: pd.DataFrame,
    lookback: int = 10,
    num_pivots: int = 2
) -> pd.DataFrame:
    """
    Add trendline columns to the dataframe for visualization.

    Args:
        df: DataFrame with OHLCV data
        lookback: Pivot detection lookback period
        num_pivots: Number of pivot points to use

    Returns:
        DataFrame with added 'resistance_line' and 'support_line' columns
    """
    df = df.copy()

    resistance, support = calculate_both_trendlines(df, lookback, num_pivots, extend_bars=0)

    if resistance:
        df['resistance_line'] = get_trendline_values_for_df(df, resistance)
    else:
        df['resistance_line'] = np.nan

    if support:
        df['support_line'] = get_trendline_values_for_df(df, support)
    else:
        df['support_line'] = np.nan

    return df


if __name__ == "__main__":
    # Test the trendline calculator
    from data_fetcher import fetch_stock_data

    print("Testing trendline calculator...")
    print("NOTE: BLUE (resistance) is MORE IMPORTANT than PINK (support)")

    df = fetch_stock_data("AAPL", period="6mo")
    print(f"\nData shape: {df.shape}")
    print(f"Price range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")

    resistance, support = calculate_both_trendlines(df, lookback=10, num_pivots=2)

    print("\n" + "="*60)
    print("BLUE RESISTANCE TRENDLINE (MORE IMPORTANT)")
    print("="*60)
    if resistance:
        print(f"Slope: {resistance.slope:.4f} ($/bar)")
        print(f"R-squared: {resistance.r_squared:.4f}")
        print(f"Angle: {resistance.angle_degrees:.1f} degrees")
        print(f"Start: Bar {resistance.start_index}, ${resistance.start_price:.2f}")
        print(f"Current trendline price: ${resistance.get_price_at_index(len(df)-1):.2f}")
        print("Pivot points used:")
        for p in resistance.pivot_points:
            print(f"  {p.date.strftime('%Y-%m-%d')}: ${p.price:.2f}")
    else:
        print("Not enough pivot highs to calculate resistance trendline")

    print("\n" + "-"*60)
    print("PINK SUPPORT TRENDLINE")
    print("-"*60)
    if support:
        print(f"Slope: {support.slope:.4f} ($/bar)")
        print(f"R-squared: {support.r_squared:.4f}")
        print(f"Angle: {support.angle_degrees:.1f} degrees")
        print(f"Start: Bar {support.start_index}, ${support.start_price:.2f}")
        print(f"Current trendline price: ${support.get_price_at_index(len(df)-1):.2f}")
        print("Pivot points used:")
        for p in support.pivot_points:
            print(f"  {p.date.strftime('%Y-%m-%d')}: ${p.price:.2f}")
    else:
        print("Not enough pivot lows to calculate support trendline")

    # Show current price relative to trendlines
    current_close = df['Close'].iloc[-1]
    print(f"\n{'='*60}")
    print(f"Current close price: ${current_close:.2f}")

    if resistance:
        res_price = resistance.get_price_at_index(len(df)-1)
        dist = resistance.percentage_distance(current_close, len(df)-1)
        print(f"Distance from BLUE resistance: {dist:+.2f}%")

    if support:
        sup_price = support.get_price_at_index(len(df)-1)
        dist = support.percentage_distance(current_close, len(df)-1)
        print(f"Distance from PINK support: {dist:+.2f}%")
