#!/usr/bin/env python3
"""
Trendline Scanner - Main Module
Scans stocks for hammer candlesticks on trendlines (Finviz style)
BLUE (resistance) is MORE IMPORTANT than PINK (support)

Usage:
    python scanner.py AAPL                    # Scan single stock
    python scanner.py AAPL MSFT GOOGL         # Scan multiple stocks
    python scanner.py --watchlist tech        # Scan predefined watchlist
    python scanner.py AAPL --plot             # Scan and show chart
"""
import argparse
import sys
from typing import List, Optional
import pandas as pd

from data_fetcher import fetch_stock_data
from pivot_detector import detect_all_pivots
from trendline_calculator import calculate_both_trendlines, Trendline
from hammer_detector import detect_hammers, HammerSignal
from signal_generator import (
    find_all_trendline_hammer_signals,
    get_latest_signal,
    format_signal_report,
    TrendlineHammerSignal
)

# Predefined watchlists
WATCHLISTS = {
    'tech': ['AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'AMD', 'TSLA'],
    'finance': ['JPM', 'BAC', 'GS', 'MS', 'C', 'WFC', 'BLK', 'SCHW'],
    'healthcare': ['JNJ', 'PFE', 'UNH', 'MRK', 'ABBV', 'TMO', 'ABT', 'LLY'],
    'sp500_top': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'BRK-B', 'JPM', 'V', 'JNJ']
}


class TrendlineScanner:
    """Main scanner class for finding hammers on trendlines"""

    def __init__(
        self,
        pivot_lookback: int = 5,  # Changed from 10 to 5 to match Finviz style
        tolerance_pct: float = 2.0,
        period: str = "6mo"
    ):
        """
        Initialize the scanner.

        Args:
            pivot_lookback: Lookback period for pivot detection
            tolerance_pct: Maximum distance (%) to consider "near" trendline
            period: Data period to fetch
        """
        self.pivot_lookback = pivot_lookback
        self.tolerance_pct = tolerance_pct
        self.period = period

    def scan_symbol(self, symbol: str) -> dict:
        """
        Scan a single symbol for trendline hammer signals.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with scan results
        """
        result = {
            'symbol': symbol,
            'status': 'success',
            'error': None,
            'data': None,
            'resistance_trendline': None,
            'support_trendline': None,
            'all_signals': [],
            'resistance_signals': [],
            'support_signals': [],
            'latest_signal': None,
            'current_price': None
        }

        try:
            # Fetch data
            df = fetch_stock_data(symbol, period=self.period)
            result['data'] = df
            result['current_price'] = df['Close'].iloc[-1]

            # Calculate trendlines
            resistance, support = calculate_both_trendlines(
                df,
                lookback=self.pivot_lookback,
                num_pivots=2
            )
            result['resistance_trendline'] = resistance
            result['support_trendline'] = support

            # Find signals
            all_signals = find_all_trendline_hammer_signals(
                df, symbol,
                lookback=self.pivot_lookback,
                tolerance_pct=self.tolerance_pct
            )
            result['all_signals'] = all_signals
            result['resistance_signals'] = [s for s in all_signals if s.trendline_type == 'resistance']
            result['support_signals'] = [s for s in all_signals if s.trendline_type == 'support']

            # Get latest signal
            result['latest_signal'] = get_latest_signal(
                df, symbol,
                lookback=self.pivot_lookback,
                tolerance_pct=self.tolerance_pct,
                recent_bars=5
            )

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)

        return result

    def scan_multiple(self, symbols: List[str]) -> List[dict]:
        """
        Scan multiple symbols.

        Args:
            symbols: List of stock ticker symbols

        Returns:
            List of scan results
        """
        results = []

        for i, symbol in enumerate(symbols):
            print(f"Scanning {symbol} ({i+1}/{len(symbols)})...", end=' ', flush=True)
            result = self.scan_symbol(symbol)

            if result['status'] == 'success':
                sig_count = len(result['all_signals'])
                recent = "RECENT SIGNAL!" if result['latest_signal'] else ""
                print(f"Found {sig_count} signals. {recent}")
            else:
                print(f"Error: {result['error']}")

            results.append(result)

        return results

    def scan_watchlist(self, watchlist_name: str) -> List[dict]:
        """
        Scan a predefined watchlist.

        Args:
            watchlist_name: Name of the watchlist

        Returns:
            List of scan results
        """
        if watchlist_name not in WATCHLISTS:
            raise ValueError(f"Unknown watchlist: {watchlist_name}. Available: {list(WATCHLISTS.keys())}")

        symbols = WATCHLISTS[watchlist_name]
        print(f"Scanning {watchlist_name} watchlist ({len(symbols)} symbols)...")
        return self.scan_multiple(symbols)

    def print_summary(self, results: List[dict]):
        """
        Print a summary of scan results.

        Args:
            results: List of scan results
        """
        print("\n" + "="*80)
        print("SCAN SUMMARY")
        print("="*80)

        # Count totals
        successful = [r for r in results if r['status'] == 'success']
        with_signals = [r for r in successful if r['all_signals']]
        with_recent = [r for r in successful if r['latest_signal']]

        print(f"\nScanned: {len(results)} symbols")
        print(f"Successful: {len(successful)}")
        print(f"With any signals: {len(with_signals)}")
        print(f"With RECENT signals (last 5 bars): {len(with_recent)}")

        # Show resistance signals first (MORE IMPORTANT)
        print("\n" + "-"*80)
        print("BLUE RESISTANCE SIGNALS (MORE IMPORTANT)")
        print("-"*80)

        for r in successful:
            if r['resistance_signals']:
                recent_res = [s for s in r['resistance_signals'] if s.hammer.index >= len(r['data']) - 10]
                if recent_res:
                    for sig in recent_res[-3:]:
                        touch = "TOUCH" if sig.is_touch else f"{sig.distance_pct:.1f}% away"
                        print(f"  {r['symbol']}: {sig.date.strftime('%Y-%m-%d')} - {sig.hammer.pattern_type} - {touch} - {sig.strength}")

        # Show support signals
        print("\n" + "-"*80)
        print("PINK SUPPORT SIGNALS")
        print("-"*80)

        for r in successful:
            if r['support_signals']:
                recent_sup = [s for s in r['support_signals'] if s.hammer.index >= len(r['data']) - 10]
                if recent_sup:
                    for sig in recent_sup[-3:]:
                        touch = "TOUCH" if sig.is_touch else f"{sig.distance_pct:.1f}% away"
                        print(f"  {r['symbol']}: {sig.date.strftime('%Y-%m-%d')} - {sig.hammer.pattern_type} - {touch} - {sig.strength}")

        # Show detailed recent signals
        if with_recent:
            print("\n" + "="*80)
            print("DETAILED RECENT SIGNALS (Last 5 bars)")
            print("="*80)
            for r in with_recent:
                print(format_signal_report(r['latest_signal']))


def plot_with_trendlines(result: dict, save_path: str = None):
    """
    Plot the stock chart with trendlines and hammer signals.

    Args:
        result: Scan result dictionary
        save_path: Optional path to save the plot
    """
    try:
        import matplotlib.pyplot as plt
        import mplfinance as mpf
    except ImportError:
        print("Error: matplotlib and mplfinance required for plotting")
        print("Install with: pip install matplotlib mplfinance")
        return

    df = result['data']
    symbol = result['symbol']

    # Prepare additional plots
    addplots = []

    # Add resistance trendline (BLUE)
    if result['resistance_trendline']:
        tl = result['resistance_trendline']
        tl_values = []
        for i in range(len(df)):
            if i >= tl.start_index:
                tl_values.append(tl.get_price_at_index(i))
            else:
                tl_values.append(float('nan'))

        addplots.append(mpf.make_addplot(
            tl_values,
            color='#3B82F6',  # Blue
            linestyle='--',
            width=2,
            label='Resistance (BLUE)'
        ))

    # Add support trendline (PINK)
    if result['support_trendline']:
        tl = result['support_trendline']
        tl_values = []
        for i in range(len(df)):
            if i >= tl.start_index:
                tl_values.append(tl.get_price_at_index(i))
            else:
                tl_values.append(float('nan'))

        addplots.append(mpf.make_addplot(
            tl_values,
            color='#EC4899',  # Pink
            linestyle='--',
            width=2,
            label='Support (PINK)'
        ))

    # Mark hammer signals
    if result['all_signals']:
        hammer_highs = [float('nan')] * len(df)
        hammer_lows = [float('nan')] * len(df)

        for sig in result['all_signals']:
            idx = sig.hammer.index
            if sig.trendline_type == 'resistance':
                hammer_highs[idx] = df['High'].iloc[idx] * 1.01
            else:
                hammer_lows[idx] = df['Low'].iloc[idx] * 0.99

        # Resistance hammers (triangles pointing down)
        if any(not pd.isna(x) for x in hammer_highs):
            addplots.append(mpf.make_addplot(
                hammer_highs,
                type='scatter',
                marker='v',
                markersize=100,
                color='#3B82F6'
            ))

        # Support hammers (triangles pointing up)
        if any(not pd.isna(x) for x in hammer_lows):
            addplots.append(mpf.make_addplot(
                hammer_lows,
                type='scatter',
                marker='^',
                markersize=100,
                color='#EC4899'
            ))

    # Create the plot
    style = mpf.make_mpf_style(
        base_mpf_style='charles',
        gridstyle='',
        y_on_right=True
    )

    fig, axes = mpf.plot(
        df,
        type='candle',
        style=style,
        title=f'\n{symbol} - Trendline Scanner',
        ylabel='Price ($)',
        volume=True,
        addplot=addplots if addplots else None,
        figsize=(14, 8),
        returnfig=True
    )

    # Add legend manually
    ax = axes[0]
    ax.legend(['Resistance (BLUE)', 'Support (PINK)'], loc='upper left')

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Chart saved to: {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Scan stocks for hammer candlesticks on trendlines (Finviz style)'
    )
    parser.add_argument(
        'symbols',
        nargs='*',
        help='Stock symbols to scan (e.g., AAPL MSFT GOOGL)'
    )
    parser.add_argument(
        '--watchlist', '-w',
        choices=list(WATCHLISTS.keys()),
        help='Use a predefined watchlist'
    )
    parser.add_argument(
        '--period', '-p',
        default='6mo',
        help='Data period to fetch (default: 6mo)'
    )
    parser.add_argument(
        '--lookback', '-l',
        type=int,
        default=5,
        help='Pivot detection lookback (default: 5, Finviz style)'
    )
    parser.add_argument(
        '--tolerance', '-t',
        type=float,
        default=2.0,
        help='Distance tolerance %% (default: 2.0)'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Show chart with trendlines'
    )
    parser.add_argument(
        '--save-plot', '-s',
        help='Save chart to file'
    )

    args = parser.parse_args()

    # Determine symbols to scan
    if args.watchlist:
        symbols = WATCHLISTS[args.watchlist]
    elif args.symbols:
        symbols = args.symbols
    else:
        print("Error: Please provide symbols or use --watchlist")
        print("Example: python scanner.py AAPL MSFT")
        print("Example: python scanner.py --watchlist tech")
        sys.exit(1)

    # Create scanner
    scanner = TrendlineScanner(
        pivot_lookback=args.lookback,
        tolerance_pct=args.tolerance,
        period=args.period
    )

    # Run scan
    print("="*80)
    print("TRENDLINE SCANNER - Hammer on Trendline Detection")
    print("BLUE (Resistance) is MORE IMPORTANT than PINK (Support)")
    print("="*80 + "\n")

    results = scanner.scan_multiple(symbols)

    # Print summary
    scanner.print_summary(results)

    # Plot if requested (only for single symbol or first symbol)
    if args.plot or args.save_plot:
        result = results[0]
        if result['status'] == 'success':
            plot_with_trendlines(result, save_path=args.save_plot)
        else:
            print(f"Cannot plot: {result['error']}")


if __name__ == "__main__":
    main()
