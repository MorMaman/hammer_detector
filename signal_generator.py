"""
Signal Generator Module
THE MAIN GOAL: Detect when a hammer candlestick appears ON or NEAR a trendline
BLUE (resistance) is MORE IMPORTANT than PINK (support)
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from trendline_calculator import (
    Trendline,
    calculate_resistance_trendline,
    calculate_support_trendline,
    calculate_both_trendlines
)
from hammer_detector import HammerSignal, detect_hammers, get_recent_hammers


@dataclass
class TrendlineHammerSignal:
    """
    Represents a signal when hammer appears on/near a trendline.
    This is THE MAIN OUTPUT of the scanner.
    """
    symbol: str                     # Stock symbol
    date: pd.Timestamp              # Date of the signal
    signal_type: str                # 'RESISTANCE_HAMMER' or 'SUPPORT_HAMMER'
    trendline_type: str             # 'resistance' (BLUE) or 'support' (PINK)
    hammer: HammerSignal            # The hammer candlestick
    trendline: Trendline            # The trendline
    distance_pct: float             # Distance from hammer to trendline (%)
    is_touch: bool                  # True if hammer touched the trendline
    strength: str                   # 'STRONG', 'MODERATE', 'WEAK'
    action: str                     # Suggested action


def calculate_hammer_trendline_distance(
    hammer: HammerSignal,
    trendline: Trendline
) -> Tuple[float, bool]:
    """
    Calculate the distance between a hammer and a trendline.

    For RESISTANCE (BLUE): Check if HIGH touched or exceeded the line from below
    For SUPPORT (PINK): Check if LOW touched or went below the line from above

    A "touch" means the price came within 0.5% of the trendline.

    Args:
        hammer: HammerSignal object
        trendline: Trendline object

    Returns:
        Tuple of (distance_percentage, is_touch)
    """
    trendline_price = trendline.get_price_at_index(hammer.index)
    touch_tolerance = 0.005  # 0.5% tolerance for "touch"

    if trendline.is_resistance:
        # For resistance (BLUE), hammer HIGH should approach the line from below
        price_to_check = hammer.high_price
        # Distance: positive = below resistance (good), negative = above (broke through)
        distance = (trendline_price - price_to_check) / trendline_price * 100
        # Touch if high is within 0.5% of resistance (either below or slightly above)
        is_touch = abs(trendline_price - price_to_check) / trendline_price <= touch_tolerance
    else:
        # For support (PINK), hammer LOW should approach the line from above
        price_to_check = hammer.low_price
        # Distance: positive = above support (good), negative = below (broke through)
        distance = (price_to_check - trendline_price) / trendline_price * 100
        # Touch if low is within 0.5% of support (either above or slightly below)
        is_touch = abs(price_to_check - trendline_price) / trendline_price <= touch_tolerance

    return abs(distance), is_touch


def evaluate_signal_strength(
    distance_pct: float,
    is_touch: bool,
    hammer: HammerSignal,
    trendline: Trendline
) -> str:
    """
    Evaluate the strength of a trendline + hammer signal.

    Factors:
    - Distance from trendline (closer = stronger)
    - R-squared of trendline (higher = more reliable)
    - Hammer characteristics

    Returns:
        'STRONG', 'MODERATE', or 'WEAK'
    """
    score = 0

    # Distance scoring
    if is_touch or distance_pct < 0.5:
        score += 3
    elif distance_pct < 1.0:
        score += 2
    elif distance_pct < 2.0:
        score += 1

    # Trendline reliability
    if trendline.r_squared > 0.95:
        score += 2
    elif trendline.r_squared > 0.80:
        score += 1

    # Hammer quality (wick ratio)
    wick_ratio = hammer.lower_wick / (hammer.body_size + 0.001)
    if wick_ratio > 3.0:
        score += 1

    if score >= 5:
        return 'STRONG'
    elif score >= 3:
        return 'MODERATE'
    else:
        return 'WEAK'


def get_action_recommendation(
    trendline: Trendline,
    hammer: HammerSignal,
    strength: str
) -> str:
    """
    Generate action recommendation based on the signal.

    Args:
        trendline: The trendline
        hammer: The hammer pattern
        strength: Signal strength

    Returns:
        Action recommendation string
    """
    if trendline.is_resistance:
        # BLUE resistance + hammer = potential reversal down OR breakout up
        if hammer.is_bullish and strength == 'STRONG':
            return "WATCH FOR BREAKOUT - Bullish hammer at resistance may signal breakout"
        else:
            return "POTENTIAL REVERSAL DOWN - Hammer at resistance may signal rejection"
    else:
        # PINK support + hammer = potential bounce up
        if hammer.is_bullish:
            return "BUY SIGNAL - Bullish hammer at support indicates potential bounce"
        else:
            return "WATCH FOR BOUNCE - Hammer at support may signal reversal up"


def find_hammer_on_resistance(
    df: pd.DataFrame,
    symbol: str = "",
    lookback: int = 10,
    tolerance_pct: float = 2.0
) -> List[TrendlineHammerSignal]:
    """
    Find hammer patterns on or near BLUE resistance trendline.
    THIS IS THE MORE IMPORTANT FUNCTION per user request.

    Args:
        df: DataFrame with OHLCV data
        symbol: Stock symbol
        lookback: Pivot detection lookback
        tolerance_pct: Maximum distance (%) to consider "near" trendline

    Returns:
        List of TrendlineHammerSignal objects
    """
    signals = []

    # Calculate resistance trendline
    resistance = calculate_resistance_trendline(df, lookback=lookback)
    if not resistance:
        return signals

    # Get all hammers
    hammers = detect_hammers(df)

    # Check each hammer against the resistance line
    for hammer in hammers:
        # Only check hammers after the trendline starts
        if hammer.index < resistance.start_index:
            continue

        distance_pct, is_touch = calculate_hammer_trendline_distance(hammer, resistance)

        if distance_pct <= tolerance_pct or is_touch:
            strength = evaluate_signal_strength(distance_pct, is_touch, hammer, resistance)
            action = get_action_recommendation(resistance, hammer, strength)

            signal = TrendlineHammerSignal(
                symbol=symbol,
                date=hammer.date,
                signal_type='RESISTANCE_HAMMER',
                trendline_type='resistance',
                hammer=hammer,
                trendline=resistance,
                distance_pct=distance_pct,
                is_touch=is_touch,
                strength=strength,
                action=action
            )
            signals.append(signal)

    return signals


def find_hammer_on_support(
    df: pd.DataFrame,
    symbol: str = "",
    lookback: int = 10,
    tolerance_pct: float = 2.0
) -> List[TrendlineHammerSignal]:
    """
    Find hammer patterns on or near PINK support trendline.

    Args:
        df: DataFrame with OHLCV data
        symbol: Stock symbol
        lookback: Pivot detection lookback
        tolerance_pct: Maximum distance (%) to consider "near" trendline

    Returns:
        List of TrendlineHammerSignal objects
    """
    signals = []

    # Calculate support trendline
    support = calculate_support_trendline(df, lookback=lookback)
    if not support:
        return signals

    # Get all hammers
    hammers = detect_hammers(df)

    # Check each hammer against the support line
    for hammer in hammers:
        # Only check hammers after the trendline starts
        if hammer.index < support.start_index:
            continue

        distance_pct, is_touch = calculate_hammer_trendline_distance(hammer, support)

        if distance_pct <= tolerance_pct or is_touch:
            strength = evaluate_signal_strength(distance_pct, is_touch, hammer, support)
            action = get_action_recommendation(support, hammer, strength)

            signal = TrendlineHammerSignal(
                symbol=symbol,
                date=hammer.date,
                signal_type='SUPPORT_HAMMER',
                trendline_type='support',
                hammer=hammer,
                trendline=support,
                distance_pct=distance_pct,
                is_touch=is_touch,
                strength=strength,
                action=action
            )
            signals.append(signal)

    return signals


def find_all_trendline_hammer_signals(
    df: pd.DataFrame,
    symbol: str = "",
    lookback: int = 10,
    tolerance_pct: float = 2.0
) -> List[TrendlineHammerSignal]:
    """
    Find all hammer signals on both trendlines.
    Returns RESISTANCE signals first (more important).

    Args:
        df: DataFrame with OHLCV data
        symbol: Stock symbol
        lookback: Pivot detection lookback
        tolerance_pct: Maximum distance (%) to consider "near" trendline

    Returns:
        List of TrendlineHammerSignal objects (resistance first, then support)
    """
    resistance_signals = find_hammer_on_resistance(df, symbol, lookback, tolerance_pct)
    support_signals = find_hammer_on_support(df, symbol, lookback, tolerance_pct)

    # Return resistance signals first (MORE IMPORTANT)
    return resistance_signals + support_signals


def get_latest_signal(
    df: pd.DataFrame,
    symbol: str = "",
    lookback: int = 10,
    tolerance_pct: float = 2.0,
    recent_bars: int = 5
) -> Optional[TrendlineHammerSignal]:
    """
    Get the most recent trendline + hammer signal.

    Args:
        df: DataFrame with OHLCV data
        symbol: Stock symbol
        lookback: Pivot detection lookback
        tolerance_pct: Distance tolerance
        recent_bars: Only consider signals in the last N bars

    Returns:
        Most recent signal or None
    """
    all_signals = find_all_trendline_hammer_signals(df, symbol, lookback, tolerance_pct)

    # Filter to recent bars
    min_index = len(df) - recent_bars
    recent_signals = [s for s in all_signals if s.hammer.index >= min_index]

    if not recent_signals:
        return None

    # Return the most recent
    return max(recent_signals, key=lambda s: s.hammer.index)


def format_signal_report(signal: TrendlineHammerSignal) -> str:
    """
    Format a signal into a readable report.

    Args:
        signal: TrendlineHammerSignal object

    Returns:
        Formatted string report
    """
    trendline_color = "BLUE" if signal.trendline_type == 'resistance' else "PINK"

    report = f"""
{'='*70}
{'HAMMER ON TRENDLINE SIGNAL' if signal.is_touch else 'HAMMER NEAR TRENDLINE SIGNAL'}
{'='*70}
Symbol: {signal.symbol}
Date: {signal.date.strftime('%Y-%m-%d')}
Signal Type: {signal.signal_type}
Trendline: {trendline_color} {signal.trendline_type.upper()}
Strength: {signal.strength}

HAMMER DETAILS:
  Pattern: {signal.hammer.pattern_type}
  Open: ${signal.hammer.open_price:.2f}
  High: ${signal.hammer.high_price:.2f}
  Low: ${signal.hammer.low_price:.2f}
  Close: ${signal.hammer.close_price:.2f}
  Bullish: {signal.hammer.is_bullish}

TRENDLINE DETAILS:
  Price at signal: ${signal.trendline.get_price_at_index(signal.hammer.index):.2f}
  Distance: {signal.distance_pct:.2f}%
  Touched: {'YES' if signal.is_touch else 'NO'}
  R-squared: {signal.trendline.r_squared:.4f}
  Slope: {signal.trendline.slope:.4f}

ACTION: {signal.action}
{'='*70}
"""
    return report


if __name__ == "__main__":
    # Test the signal generator
    from data_fetcher import fetch_stock_data

    print("Testing signal generator...")
    print("Main goal: Find hammers on trendlines")
    print("BLUE (resistance) is MORE IMPORTANT than PINK (support)")
    print()

    # Test with multiple symbols
    symbols = ["AAPL", "MSFT", "GOOGL"]

    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"Scanning {symbol}...")
        print(f"{'='*70}")

        try:
            df = fetch_stock_data(symbol, period="6mo")

            # Find all signals
            signals = find_all_trendline_hammer_signals(df, symbol, lookback=10, tolerance_pct=2.0)

            print(f"\nFound {len(signals)} total signals")

            # Count by type
            resistance_signals = [s for s in signals if s.trendline_type == 'resistance']
            support_signals = [s for s in signals if s.trendline_type == 'support']

            print(f"  BLUE (Resistance) signals: {len(resistance_signals)} <- MORE IMPORTANT")
            print(f"  PINK (Support) signals: {len(support_signals)}")

            # Show recent signals
            if signals:
                print("\nMost recent signals:")
                for signal in signals[-3:]:
                    color = "BLUE" if signal.trendline_type == 'resistance' else "PINK"
                    touch = "TOUCH" if signal.is_touch else f"{signal.distance_pct:.1f}%"
                    print(f"  [{signal.date.strftime('%Y-%m-%d')}] {color} {signal.hammer.pattern_type} - {touch} - {signal.strength}")

            # Check for latest actionable signal
            latest = get_latest_signal(df, symbol, recent_bars=5)
            if latest:
                print(f"\n*** RECENT SIGNAL DETECTED ***")
                print(format_signal_report(latest))

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
