#!/usr/bin/env python3
"""
Direct Finviz Trendline Scanner
Fetches actual trendline data from Finviz and checks for hammers
"""
import re
import json
import requests
from dataclasses import dataclass
from typing import Optional, Tuple, List
import pandas as pd
from data_fetcher import fetch_stock_data
from hammer_detector import detect_hammers, HammerSignal


@dataclass
class FinvizPattern:
    """Pattern data directly from Finviz"""
    kind: int          # 1=horizontal, 2=upper trendline, 3=lower trendline, 4=wedge
    strength: float
    status: int
    bounces: int
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class FinvizTrendlines:
    """Trendlines from Finviz"""
    symbol: str
    min_price: float
    max_price: float
    upper: Optional[FinvizPattern]
    lower: Optional[FinvizPattern]
    chart_bars: int  # Usually ~500


def fetch_finviz_patterns(symbol: str) -> Optional[FinvizTrendlines]:
    """
    Fetch pattern data directly from Finviz.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        url = f"https://finviz.com/quote.ashx?t={symbol}"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        html = response.text

        # Extract patterns JSON
        patterns_match = re.search(r'"patterns":\[([^\]]*)\]', html)
        if not patterns_match:
            return None

        patterns_str = '[' + patterns_match.group(1) + ']'
        patterns_data = json.loads(patterns_str)

        # Extract price range
        range_match = re.search(r'"patternsMinRange":([0-9.]+),"patternsMaxRange":([0-9.]+)', html)
        if not range_match:
            return None

        min_price = float(range_match.group(1))
        max_price = float(range_match.group(2))

        # Parse patterns - pick ACTIVE (status=1) with highest strength
        upper = None
        lower = None
        upper_strength = 0
        lower_strength = 0

        for p in patterns_data:
            pattern = FinvizPattern(
                kind=p.get('kind', 0),
                strength=p.get('strength', 0),
                status=p.get('status', 0),
                bounces=p.get('bounces', 0),
                x1=p.get('x1', 0),
                y1=p.get('y1', 0),
                x2=p.get('x2', 0),
                y2=p.get('y2', 0)
            )

            # Only consider ACTIVE patterns (status=1) with higher strength
            if pattern.kind == 2:  # Upper trendline (BLUE)
                if pattern.status == 1 and pattern.strength > upper_strength:
                    upper = pattern
                    upper_strength = pattern.strength
            elif pattern.kind == 3:  # Lower trendline (PINK)
                if pattern.status == 1 and pattern.strength > lower_strength:
                    lower = pattern
                    lower_strength = pattern.strength

        return FinvizTrendlines(
            symbol=symbol,
            min_price=min_price,
            max_price=max_price,
            upper=upper,
            lower=lower,
            chart_bars=500  # Finviz uses ~500 bars
        )

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def y_to_price(y: int, min_price: float, max_price: float, height: int = 400) -> float:
    """Convert Finviz Y coordinate to price. Height=400 matches Finviz chart rendering."""
    return max_price - (y / height) * (max_price - min_price)


def get_trendline_price(pattern: FinvizPattern, bar_index: int,
                         min_price: float, max_price: float) -> float:
    """Get trendline price at a specific bar index"""
    price1 = y_to_price(pattern.y1, min_price, max_price)
    price2 = y_to_price(pattern.y2, min_price, max_price)

    if pattern.x2 == pattern.x1:
        return price1

    slope = (price2 - price1) / (pattern.x2 - pattern.x1)
    return price1 + slope * (bar_index - pattern.x1)


def analyze_symbol(symbol: str) -> dict:
    """
    Analyze a symbol using actual Finviz trendlines.
    """
    result = {
        'symbol': symbol,
        'has_pattern': False,
        'upper_line': None,
        'lower_line': None,
        'upper_distance': None,
        'lower_distance': None,
        'near_upper': False,
        'near_lower': False,
        'hammer_on_upper': False,
        'hammer_on_lower': False,
        'recent_hammers': []
    }

    # Fetch Finviz patterns
    finviz = fetch_finviz_patterns(symbol)
    if not finviz:
        return result

    # Fetch price data
    try:
        df = fetch_stock_data(symbol, period='3mo')
    except:
        return result

    result['has_pattern'] = finviz.upper is not None or finviz.lower is not None
    result['current_price'] = df['Close'].iloc[-1]
    result['current_high'] = df['High'].iloc[-1]
    result['current_low'] = df['Low'].iloc[-1]

    # Calculate current trendline prices (at bar ~500)
    current_bar = 500

    if finviz.upper:
        upper_price = get_trendline_price(finviz.upper, current_bar,
                                           finviz.min_price, finviz.max_price)
        result['upper_line'] = upper_price
        result['upper_distance'] = (df['High'].iloc[-1] - upper_price) / upper_price * 100
        result['near_upper'] = abs(result['upper_distance']) <= 2.0
        result['upper_bounces'] = finviz.upper.bounces

    if finviz.lower:
        lower_price = get_trendline_price(finviz.lower, current_bar,
                                           finviz.min_price, finviz.max_price)
        result['lower_line'] = lower_price
        result['lower_distance'] = (df['Low'].iloc[-1] - lower_price) / lower_price * 100
        result['near_lower'] = abs(result['lower_distance']) <= 2.0
        result['lower_bounces'] = finviz.lower.bounces

    # Check for hammers - only last 2 days for strict recency
    hammers = detect_hammers(df)
    recent_hammers = [h for h in hammers if h.index >= len(df) - 2]
    result['recent_hammers'] = recent_hammers

    # Check if any recent hammer is near trendlines
    for hammer in recent_hammers:
        if result['near_upper']:
            result['hammer_on_upper'] = True
        if result['near_lower']:
            result['hammer_on_lower'] = True

    return result


def scan_finviz_stocks(symbols: List[str]) -> List[dict]:
    """Scan multiple stocks using Finviz trendlines"""
    results = []

    for i, symbol in enumerate(symbols):
        print(f"Scanning {symbol} ({i+1}/{len(symbols)})...", end=' ', flush=True)
        result = analyze_symbol(symbol)

        if result['has_pattern']:
            near = []
            if result['near_upper']:
                near.append(f"UPPER {result['upper_distance']:.1f}%")
            if result['near_lower']:
                near.append(f"LOWER {result['lower_distance']:.1f}%")

            if near:
                print(f"Near: {', '.join(near)}")
            else:
                print(f"Pattern found, not near lines")
        else:
            print("No pattern")

        results.append(result)

    return results


if __name__ == "__main__":
    print("="*70)
    print("FINVIZ DIRECT TRENDLINE SCANNER")
    print("Using ACTUAL Finviz pattern data")
    print("="*70)

    # Fetch wedge up stocks from Finviz
    import subprocess
    cmd = 'curl -s -A "Mozilla/5.0" "https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_avgvol_o1000,ta_pattern_wedgeup&ft=4" | grep -oE "quote\\.ashx\\?t=[A-Z]+" | sed "s/quote.ashx?t=//" | sort -u | head -15'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    symbols = result.stdout.strip().split('\n')

    print(f"\nFound {len(symbols)} wedge up stocks from Finviz")
    print(f"Symbols: {', '.join(symbols[:10])}...")

    print("\n" + "="*70)
    print("SCANNING...")
    print("="*70 + "\n")

    results = scan_finviz_stocks(symbols)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY - Stocks NEAR Trendlines")
    print("="*70)

    near_upper = [r for r in results if r.get('near_upper')]
    near_lower = [r for r in results if r.get('near_lower')]

    print(f"\n>>> NEAR UPPER (BLUE) RESISTANCE ({len(near_upper)} stocks):")
    for r in near_upper:
        print(f"  {r['symbol']}: {r['upper_distance']:.2f}% from upper (${r['upper_line']:.2f})")
        print(f"         Current high: ${r['current_high']:.2f}")
        if r['recent_hammers']:
            print(f"         *** HAS RECENT HAMMER! ***")

    print(f"\n>>> NEAR LOWER (PINK) SUPPORT ({len(near_lower)} stocks):")
    for r in near_lower:
        print(f"  {r['symbol']}: {r['lower_distance']:.2f}% from lower (${r['lower_line']:.2f})")
        print(f"         Current low: ${r['current_low']:.2f}")
        if r['recent_hammers']:
            print(f"         *** HAS RECENT HAMMER! ***")
