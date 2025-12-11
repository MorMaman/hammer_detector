# Trendline Hammer Scanner

Scans stocks for **hammer candlestick patterns touching trendlines** using real Finviz data.

## What It Does

Finds stocks where a hammer candlestick forms at a trendline - a potential reversal signal.

- Fetches **real trendline data** directly from Finviz (not replicated algorithms)
- Detects **hammer patterns** using configurable criteria
- Checks if hammer touches trendline within **2% tolerance**
- Scans last **5 days** for recent signals

## Installation

```bash
cd trendline-scanner
python -m venv venv
source venv/bin/activate
pip install pandas requests scipy yfinance
```

Optional (for better hammer detection):
```bash
pip install TA-Lib
```

## Usage

### Quick Scan
```bash
python run_scanner.py
```

### Scan Specific Pattern
```bash
python run_scanner.py --pattern wedgeup
python run_scanner.py --pattern channeldown
```

### Scan Specific Symbols
```bash
python run_scanner.py AAPL MSFT ASND
```

### Adjust Tolerance
```bash
python run_scanner.py --tolerance 1.5  # 1.5% instead of 2%
```

## Output

```
HAMMERS ON BLUE TRENDLINE - Last 5 Days: 4

  APH    12/11 (TODAY ) Blue=$139.69 Low=$139.14 (-0.4%) - hammer
  AMD    12/11 (TODAY ) Blue=$206.63 Low=$210.19 (+1.7%) - hammer
  NVT    12/11 (TODAY ) Blue=$102.98 Low=$104.94 (+1.9%) - hammer
  ASND   12/10 (1d ago) Blue=$195.21 Low=$192.28 (-1.5%) - hammer
```

## Files

| File | Description |
|------|-------------|
| `run_scanner.py` | Main CLI scanner |
| `finviz_direct.py` | Fetches Finviz trendline data |
| `hammer_detector.py` | Hammer candlestick detection |
| `data_fetcher.py` | Price data from yfinance |
| `INSTRUCTIONS.md` | Detailed technical notes |

## How It Works

1. **Fetch Finviz Patterns** - Scrapes pattern coordinates from Finviz quote pages
2. **Convert Coordinates** - Transforms Finviz Y-coordinates to actual prices (height=400)
3. **Detect Hammers** - Finds hammer patterns in recent price data
4. **Check Proximity** - Determines if hammer low is within 2% of trendline

## Finviz Pattern Types

| Kind | Type | Description |
|------|------|-------------|
| 2 | Upper | Resistance line |
| 3 | Lower | **Support line (BLUE on chart)** |

## Hammer Detection Criteria

- Body size <= 35% of total candle range
- Lower wick >= 1.5x body size
- Upper wick <= 50% of body size
- Total range >= 2% of price (filters noise)
- Body >= 0.5% of price (filters dojis)

## License

MIT
