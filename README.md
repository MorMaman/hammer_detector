# Trendline Hammer Scanner

Scans stocks for **hammer candlestick patterns touching trendlines** using real Finviz data.

## What It Does

Finds stocks where a hammer candlestick forms at a trendline - a potential reversal signal.

- Fetches **real trendline data** directly from Finviz (not replicated algorithms)
- Detects **hammer patterns** using configurable criteria
- Checks if hammer touches trendline within **2% tolerance**
- Scans last **5 days** for recent signals
- **Telegram bot** for alerts and on-demand scans

## Installation

```bash
cd trendline-scanner
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### CLI Scanner
```bash
python run_scanner.py                    # Scan all patterns
python run_scanner.py --pattern wedgeup  # Scan specific pattern
python run_scanner.py AAPL MSFT ASND     # Scan specific symbols
python run_scanner.py --tolerance 1.5    # Adjust tolerance
```

### Telegram Bot

1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the token
3. Create `.env` file:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_ADMIN_CHAT_ID=your_chat_id  # Optional, for admin alerts
   ```
4. Run the bot:
   ```bash
   python telegram_bot.py
   ```

#### Bot Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome message and help |
| `/scan` | Full scan (5 days, all patterns) |
| `/quick` | Quick scan (today only) |
| `/settings` | Adjust tolerance, patterns, lookback |
| `/alerts` | Toggle alert notifications |

#### Bot Features
- **Inline keyboards** for pattern selection
- **Tolerance adjustment** (1%, 1.5%, 2%, 3%)
- **Lookback settings** (1, 3, 5, 7 days)
- **Scheduled scans** - Hourly during market hours
- **Daily reports** - 4:30 PM ET

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
| `telegram_bot.py` | Telegram bot with commands and scheduled scans |
| `scanner_service.py` | Scanner wrapper for bot integration |
| `run_scanner.py` | CLI scanner |
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
