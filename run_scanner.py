#!/usr/bin/env python3
"""
TRENDLINE HAMMER SCANNER
Uses REAL Finviz trendline data to find hammers on trendlines
BLUE (resistance) is MORE IMPORTANT than PINK (support)

Usage:
    python run_scanner.py                    # Scan Finviz wedge up stocks
    python run_scanner.py --pattern wedgedown  # Scan wedge down stocks
    python run_scanner.py AAPL MSFT          # Scan specific stocks
"""
import argparse
import subprocess
from typing import List
from finviz_direct import analyze_symbol, fetch_finviz_patterns, get_trendline_price
from data_fetcher import fetch_stock_data
from hammer_detector import detect_hammers


def get_finviz_pattern_stocks(pattern: str = 'wedgeup') -> List[str]:
    """Fetch stocks with a specific pattern from Finviz"""
    pattern_map = {
        'wedgeup': 'ta_pattern_wedgeup',
        'wedgedown': 'ta_pattern_wedgedown',
        'channelup': 'ta_pattern_channelup',
        'channeldown': 'ta_pattern_channeldown',
        'horizontal': 'ta_pattern_horizontal'
    }

    pattern_code = pattern_map.get(pattern, 'ta_pattern_wedgeup')

    cmd = f'curl -s -A "Mozilla/5.0" "https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_avgvol_o1000,{pattern_code}&ft=4" | grep -oE "quote\\.ashx\\?t=[A-Z]+" | sed "s/quote.ashx?t=//" | sort -u'

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    symbols = result.stdout.strip().split('\n')
    return [s for s in symbols if s and len(s) <= 5]


def scan_for_signals(symbols: List[str], tolerance: float = 2.0) -> dict:
    """Scan symbols for hammer on trendline signals"""
    results = {
        'near_upper': [],
        'near_lower': [],
        'hammer_on_upper': [],
        'hammer_on_lower': []
    }

    for i, symbol in enumerate(symbols):
        print(f"Scanning {symbol} ({i+1}/{len(symbols)})...", end=' ', flush=True)

        try:
            r = analyze_symbol(symbol)

            if r.get('near_upper') and abs(r['upper_distance']) <= tolerance:
                results['near_upper'].append(r)
                if r['recent_hammers']:
                    results['hammer_on_upper'].append(r)
                    print(f"UPPER {r['upper_distance']:.1f}% + HAMMER!")
                else:
                    print(f"UPPER {r['upper_distance']:.1f}%")
            elif r.get('near_lower') and abs(r['lower_distance']) <= tolerance:
                results['near_lower'].append(r)
                if r['recent_hammers']:
                    results['hammer_on_lower'].append(r)
                    print(f"LOWER {r['lower_distance']:.1f}% + HAMMER!")
                else:
                    print(f"LOWER {r['lower_distance']:.1f}%")
            elif r.get('has_pattern'):
                print("Pattern found, not near lines")
            else:
                print("No pattern")

        except Exception as e:
            print(f"Error: {e}")

    return results


def print_results(results: dict):
    """Print scan results"""
    print("\n" + "="*70)
    print("SCAN RESULTS")
    print("="*70)

    # HAMMER ON UPPER (MOST IMPORTANT)
    print(f"\n🔥 HAMMER ON BLUE RESISTANCE: {len(results['hammer_on_upper'])} stocks")
    for r in results['hammer_on_upper']:
        print(f"  {r['symbol']}: {r['upper_distance']:.2f}% from ${r['upper_line']:.2f}")
        print(f"         High: ${r['current_high']:.2f}")
        for h in r['recent_hammers']:
            print(f"         Hammer: {h.pattern_type} on {h.date.strftime('%Y-%m-%d')}")

    # HAMMER ON LOWER
    print(f"\n⚡ HAMMER ON PINK SUPPORT: {len(results['hammer_on_lower'])} stocks")
    for r in results['hammer_on_lower']:
        print(f"  {r['symbol']}: {r['lower_distance']:.2f}% from ${r['lower_line']:.2f}")
        print(f"         Low: ${r['current_low']:.2f}")
        for h in r['recent_hammers']:
            print(f"         Hammer: {h.pattern_type} on {h.date.strftime('%Y-%m-%d')}")

    # Near upper (no hammer)
    print(f"\n📊 Near BLUE Resistance (no hammer): {len(results['near_upper']) - len(results['hammer_on_upper'])} stocks")
    for r in results['near_upper']:
        if r not in results['hammer_on_upper']:
            print(f"  {r['symbol']}: {r['upper_distance']:.2f}%")

    # Near lower (no hammer)
    print(f"\n📊 Near PINK Support (no hammer): {len(results['near_lower']) - len(results['hammer_on_lower'])} stocks")
    for r in results['near_lower']:
        if r not in results['hammer_on_lower']:
            print(f"  {r['symbol']}: {r['lower_distance']:.2f}%")


def main():
    parser = argparse.ArgumentParser(description='Trendline Hammer Scanner')
    parser.add_argument('symbols', nargs='*', help='Specific symbols to scan')
    parser.add_argument('--pattern', '-p', default='wedgeup',
                       choices=['wedgeup', 'wedgedown', 'channelup', 'channeldown', 'horizontal'],
                       help='Finviz pattern to scan')
    parser.add_argument('--tolerance', '-t', type=float, default=2.0,
                       help='Distance tolerance %% (default: 2.0)')

    args = parser.parse_args()

    print("="*70)
    print("TRENDLINE HAMMER SCANNER")
    print("Using REAL Finviz trendline data")
    print("BLUE (resistance) MORE IMPORTANT than PINK (support)")
    print("="*70)

    if args.symbols:
        symbols = args.symbols
        print(f"\nScanning {len(symbols)} specified symbols")
    else:
        print(f"\nFetching {args.pattern} stocks from Finviz...")
        symbols = get_finviz_pattern_stocks(args.pattern)
        print(f"Found {len(symbols)} stocks")

    print("\n" + "-"*70 + "\n")

    results = scan_for_signals(symbols, args.tolerance)
    print_results(results)


if __name__ == "__main__":
    main()
