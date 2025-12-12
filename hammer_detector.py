"""
Hammer Candlestick Detector Module
Detects hammer and inverted hammer patterns using TA-Lib
Hammer on trendline = potential reversal signal
"""
import numpy as np
import pandas as pd
from typing import List, Optional
from dataclasses import dataclass

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("WARNING: TA-Lib not installed. Using manual hammer detection.")


@dataclass
class HammerSignal:
    """Represents a detected hammer candlestick"""
    index: int              # Index in the dataframe
    date: pd.Timestamp      # Date of the hammer
    open_price: float       # Open price
    high_price: float       # High price
    low_price: float        # Low price
    close_price: float      # Close price
    pattern_type: str       # 'hammer', 'inverted_hammer', 'hanging_man', 'shooting_star'
    is_bullish: bool        # True if bullish signal
    body_size: float        # Size of the candle body
    lower_wick: float       # Size of lower wick
    upper_wick: float       # Size of upper wick


def detect_hammer_talib(df: pd.DataFrame) -> List[HammerSignal]:
    """
    Detect hammer patterns using TA-Lib CDLHAMMER.
    Returns 100 for bullish hammer, 0 for no pattern.

    A hammer has:
    - Small body at the TOP of the candle
    - Long lower wick (at least 2x body size)
    - Little to no upper wick
    - Appears after a downtrend = bullish reversal signal

    Args:
        df: DataFrame with OHLCV data

    Returns:
        List of HammerSignal objects
    """
    if not TALIB_AVAILABLE:
        return detect_hammer_manual(df)

    open_prices = df['Open'].values
    high_prices = df['High'].values
    low_prices = df['Low'].values
    close_prices = df['Close'].values

    # Detect different hammer patterns
    hammers = talib.CDLHAMMER(open_prices, high_prices, low_prices, close_prices)
    inverted_hammers = talib.CDLINVERTEDHAMMER(open_prices, high_prices, low_prices, close_prices)
    hanging_man = talib.CDLHANGINGMAN(open_prices, high_prices, low_prices, close_prices)
    shooting_star = talib.CDLSHOOTINGSTAR(open_prices, high_prices, low_prices, close_prices)

    signals = []

    for i in range(len(df)):
        pattern_type = None
        is_bullish = False

        if hammers[i] != 0:
            pattern_type = 'hammer'
            is_bullish = True
        elif inverted_hammers[i] != 0:
            pattern_type = 'inverted_hammer'
            is_bullish = True
        elif hanging_man[i] != 0:
            pattern_type = 'hanging_man'
            is_bullish = False
        elif shooting_star[i] != 0:
            pattern_type = 'shooting_star'
            is_bullish = False

        if pattern_type:
            o, h, l, c = open_prices[i], high_prices[i], low_prices[i], close_prices[i]
            body = abs(c - o)
            lower_wick = min(o, c) - l
            upper_wick = h - max(o, c)

            signal = HammerSignal(
                index=i,
                date=df.index[i],
                open_price=o,
                high_price=h,
                low_price=l,
                close_price=c,
                pattern_type=pattern_type,
                is_bullish=is_bullish,
                body_size=body,
                lower_wick=lower_wick,
                upper_wick=upper_wick
            )
            signals.append(signal)

    return signals


def detect_hammer_manual(
    df: pd.DataFrame,
    body_ratio: float = 0.35,
    wick_ratio: float = 1.5,
    min_range_pct: float = 2.0,
    min_body_pct: float = 0.5
) -> List[HammerSignal]:
    """
    Manual hammer detection without TA-Lib.

    Hammer criteria:
    - Total range is at least 3% of the price (filters tiny candles)
    - Body is at least 1% of the price (filters insignificant bodies)
    - Body is in the upper 35% of the candle range
    - Lower wick is at least 1.5x the body size (relaxed from 2x to match Finviz)
    - Upper wick is less than 50% of the body

    Args:
        df: DataFrame with OHLCV data
        body_ratio: Maximum body size as ratio of total range
        wick_ratio: Minimum lower wick size as multiple of body
        min_range_pct: Minimum total range as percentage of price (filters tiny candles)
        min_body_pct: Minimum body size as percentage of price

    Returns:
        List of HammerSignal objects
    """
    signals = []

    for i in range(len(df)):
        o = df['Open'].iloc[i]
        h = df['High'].iloc[i]
        l = df['Low'].iloc[i]
        c = df['Close'].iloc[i]

        # Calculate candle components
        total_range = h - l
        if total_range == 0:
            continue

        body = abs(c - o)

        # Filter out tiny candles - range must be at least min_range_pct of price
        # This filters noise like ALLY ($0.67 range on $42 stock = 1.6%)
        # but keeps real hammers like ASND ($9.61 range on $200 stock = 4.8%)
        range_pct = (total_range / c) * 100
        if range_pct < min_range_pct:
            continue

        # Filter out insignificant body sizes
        # ASND: body=$3.23 (1.6% of $200) = significant
        # AAOI: body=$0.35 (1.3% of $27) = borderline, but range is small
        body_pct = (body / c) * 100
        if body_pct < min_body_pct:
            continue

        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)

        # Check for hammer pattern
        is_hammer = (
            body <= total_range * body_ratio and  # Small body
            lower_wick >= body * wick_ratio and   # Long lower wick
            upper_wick <= body * 0.5               # Short upper wick
        )

        # Check for inverted hammer pattern
        is_inverted = (
            body <= total_range * body_ratio and  # Small body
            upper_wick >= body * wick_ratio and   # Long upper wick
            lower_wick <= body * 0.5               # Short lower wick
        )

        if is_hammer or is_inverted:
            # Determine if bullish based on context (simplified)
            # For proper context, we'd look at prior trend
            is_bullish = c > o  # Green candle is more bullish

            signal = HammerSignal(
                index=i,
                date=df.index[i],
                open_price=o,
                high_price=h,
                low_price=l,
                close_price=c,
                pattern_type='inverted_hammer' if is_inverted else 'hammer',
                is_bullish=is_bullish,
                body_size=body,
                lower_wick=lower_wick,
                upper_wick=upper_wick
            )
            signals.append(signal)

    return signals


def detect_hammers(df: pd.DataFrame) -> List[HammerSignal]:
    """
    Main hammer detection function. Uses TA-Lib if available, else manual.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        List of HammerSignal objects
    """
    if TALIB_AVAILABLE:
        return detect_hammer_talib(df)
    else:
        return detect_hammer_manual(df)


def get_recent_hammers(
    df: pd.DataFrame,
    lookback_bars: int = 20
) -> List[HammerSignal]:
    """
    Get hammer patterns from the last N bars.

    Args:
        df: DataFrame with OHLCV data
        lookback_bars: Number of bars to look back

    Returns:
        List of recent HammerSignal objects
    """
    all_hammers = detect_hammers(df)
    min_index = len(df) - lookback_bars

    return [h for h in all_hammers if h.index >= min_index]


def add_hammer_column_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a hammer pattern column to the dataframe for visualization.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        DataFrame with added 'hammer' column (NaN or pattern type)
    """
    df = df.copy()
    df['hammer'] = None

    hammers = detect_hammers(df)

    for h in hammers:
        df.loc[df.index[h.index], 'hammer'] = h.pattern_type

    return df


def is_hammer_near_price(
    hammer: HammerSignal,
    target_price: float,
    tolerance_pct: float = 1.0
) -> bool:
    """
    Check if a hammer candle is near a target price (like a trendline).

    Args:
        hammer: HammerSignal object
        target_price: Price to check against (e.g., trendline price)
        tolerance_pct: Percentage tolerance for "near"

    Returns:
        True if hammer is near the target price
    """
    # Check if any part of the hammer is near the target price
    prices = [hammer.high_price, hammer.low_price, hammer.close_price, hammer.open_price]

    for price in prices:
        pct_diff = abs(price - target_price) / target_price * 100
        if pct_diff <= tolerance_pct:
            return True

    return False


if __name__ == "__main__":
    # Test the hammer detector
    from data_fetcher import fetch_stock_data

    print("Testing hammer detector...")
    print(f"TA-Lib available: {TALIB_AVAILABLE}")

    df = fetch_stock_data("AAPL", period="6mo")
    print(f"\nData shape: {df.shape}")

    hammers = detect_hammers(df)
    print(f"\nFound {len(hammers)} hammer patterns total")

    # Show recent hammers
    recent = get_recent_hammers(df, lookback_bars=30)
    print(f"Found {len(recent)} hammers in last 30 bars")

    if hammers:
        print("\nLast 5 hammer patterns:")
        for h in hammers[-5:]:
            print(f"  {h.date.strftime('%Y-%m-%d')}: {h.pattern_type}")
            print(f"    O: ${h.open_price:.2f}, H: ${h.high_price:.2f}, L: ${h.low_price:.2f}, C: ${h.close_price:.2f}")
            print(f"    Body: ${h.body_size:.2f}, Lower wick: ${h.lower_wick:.2f}, Upper wick: ${h.upper_wick:.2f}")
            print(f"    Bullish: {h.is_bullish}")
