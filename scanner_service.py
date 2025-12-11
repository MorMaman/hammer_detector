#!/usr/bin/env python3
"""
Scanner Service - Wrapper for hammer scanner to be used by Telegram bot
Scans for hammers on BLUE trendline (kind=3 lower/support in Finviz)
"""
import subprocess
from typing import List, Dict, Optional
from dataclasses import dataclass
from finviz_direct import fetch_finviz_patterns, y_to_price
from data_fetcher import fetch_stock_data
from hammer_detector import detect_hammers


@dataclass
class HammerSignal:
    """Represents a hammer on trendline signal"""
    symbol: str
    date: str
    line_type: str  # 'blue' or 'upper'
    line_price: float
    price: float  # high or low depending on line type
    distance: float
    days_ago: int
    hammer_type: str


def get_finviz_stocks(patterns: List[str] = None) -> List[str]:
    """
    Get stocks from Finviz screener with specified patterns.
    Also includes stocks with hammer candlestick filter.
    """
    if patterns is None:
        patterns = ['wedgeup', 'wedgedown', 'channelup', 'channeldown', 'horizontal']

    all_symbols = set()

    for pattern in patterns:
        pattern_code = f'ta_pattern_{pattern}'
        cmd = f'curl -s -A "Mozilla/5.0" "https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_avgvol_o1000,{pattern_code}&ft=4" | grep -oE "quote\\.ashx\\?t=[A-Z]+" | sed "s/quote.ashx?t=//" | sort -u'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        symbols = [s for s in result.stdout.strip().split('\n') if s and len(s) <= 5]
        all_symbols.update(symbols)

    # Also add stocks with hammer filter
    cmd = 'curl -s -A "Mozilla/5.0" "https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_avgvol_o1000,ta_candlestick_h&ft=4" | grep -oE "quote\\.ashx\\?t=[A-Z]+" | sed "s/quote.ashx?t=//" | sort -u'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    hammer_symbols = [s for s in result.stdout.strip().split('\n') if s and len(s) <= 5]
    all_symbols.update(hammer_symbols)

    return sorted(list(all_symbols))


def scan_for_hammers(
    symbols: List[str] = None,
    patterns: List[str] = None,
    lookback_days: int = 5,
    tolerance: float = 2.0
) -> Dict[str, List[HammerSignal]]:
    """
    Scan stocks for hammers on trendlines.

    Args:
        symbols: List of symbols to scan (if None, fetches from Finviz)
        patterns: List of patterns to filter by (wedgeup, wedgedown, etc.)
        lookback_days: Number of days to look back for hammers
        tolerance: Distance tolerance percentage for "near" trendline

    Returns:
        Dict with 'blue' and 'upper' keys, each containing list of HammerSignal
    """
    if symbols is None:
        symbols = get_finviz_stocks(patterns)

    results = {
        'blue': [],   # Lower/support trendline (kind=3) - WHAT MASTER WANTS
        'upper': []   # Upper/resistance trendline (kind=2)
    }

    for symbol in symbols:
        try:
            finviz = fetch_finviz_patterns(symbol)
            if not finviz:
                continue

            df = fetch_stock_data(symbol, period='3mo')
            if len(df) < 10:
                continue

            hammers = detect_hammers(df)

            for day_offset in range(lookback_days):
                bar_idx = len(df) - 1 - day_offset
                if bar_idx < 0:
                    continue

                check_date = df.index[bar_idx]
                day_hammers = [h for h in hammers if h.index == bar_idx]
                if not day_hammers:
                    continue

                day_high = df['High'].iloc[bar_idx]
                day_low = df['Low'].iloc[bar_idx]
                finviz_bar = 500 - day_offset

                # Check BLUE (lower/support) line - kind=3 - THIS IS WHAT MASTER WANTS
                if finviz.lower:
                    lower = finviz.lower
                    lower_slope = (lower.y2 - lower.y1) / (lower.x2 - lower.x1)
                    lower_y = lower.y1 + lower_slope * (finviz_bar - lower.x1)
                    lower_price = y_to_price(lower_y, finviz.min_price, finviz.max_price)
                    lower_dist = (day_low - lower_price) / lower_price * 100

                    if abs(lower_dist) <= tolerance:
                        results['blue'].append(HammerSignal(
                            symbol=symbol,
                            date=check_date.strftime('%Y-%m-%d'),
                            line_type='blue',
                            line_price=lower_price,
                            price=day_low,
                            distance=lower_dist,
                            days_ago=day_offset,
                            hammer_type=day_hammers[0].pattern_type
                        ))

                # Check UPPER (resistance) line - kind=2
                if finviz.upper:
                    upper = finviz.upper
                    upper_slope = (upper.y2 - upper.y1) / (upper.x2 - upper.x1)
                    upper_y = upper.y1 + upper_slope * (finviz_bar - upper.x1)
                    upper_price = y_to_price(upper_y, finviz.min_price, finviz.max_price)
                    upper_dist = (day_high - upper_price) / upper_price * 100

                    if abs(upper_dist) <= tolerance:
                        results['upper'].append(HammerSignal(
                            symbol=symbol,
                            date=check_date.strftime('%Y-%m-%d'),
                            line_type='upper',
                            line_price=upper_price,
                            price=day_high,
                            distance=upper_dist,
                            days_ago=day_offset,
                            hammer_type=day_hammers[0].pattern_type
                        ))

        except Exception as e:
            continue

    # Sort by days_ago (most recent first)
    results['blue'] = sorted(results['blue'], key=lambda x: (x.days_ago, x.symbol))
    results['upper'] = sorted(results['upper'], key=lambda x: (x.days_ago, x.symbol))

    return results


def format_results_for_telegram(results: Dict[str, List[HammerSignal]]) -> str:
    """Format scan results for Telegram message"""
    lines = []

    # BLUE (support) - MOST IMPORTANT
    lines.append("🔵 *HAMMERS ON BLUE TRENDLINE*")
    lines.append(f"Found: {len(results['blue'])} signals")
    lines.append("")

    if results['blue']:
        for signal in results['blue']:
            days_label = "TODAY" if signal.days_ago == 0 else f"{signal.days_ago}d ago"
            lines.append(
                f"• *{signal.symbol}* ({days_label})\n"
                f"  Blue: ${signal.line_price:.2f} | Low: ${signal.price:.2f}\n"
                f"  Distance: {signal.distance:+.1f}% | {signal.hammer_type}"
            )
    else:
        lines.append("_No signals found_")

    lines.append("")
    lines.append("─" * 30)
    lines.append("")

    # UPPER (resistance)
    lines.append("🔴 *HAMMERS ON UPPER RESISTANCE*")
    lines.append(f"Found: {len(results['upper'])} signals")
    lines.append("")

    if results['upper']:
        for signal in results['upper']:
            days_label = "TODAY" if signal.days_ago == 0 else f"{signal.days_ago}d ago"
            lines.append(
                f"• *{signal.symbol}* ({days_label})\n"
                f"  Upper: ${signal.line_price:.2f} | High: ${signal.price:.2f}\n"
                f"  Distance: {signal.distance:+.1f}% | {signal.hammer_type}"
            )
    else:
        lines.append("_No signals found_")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Running scanner service test...")
    results = scan_for_hammers(lookback_days=5, tolerance=2.0)
    print(format_results_for_telegram(results))
