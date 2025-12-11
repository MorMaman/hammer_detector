# Trendline Scanner Instructions

## What This Scanner Does
Finds stocks with **hammer candlesticks touching trendlines** using real Finviz data.

## Key Terminology (IMPORTANT!)

### Finviz Pattern Types
- **kind=2** = Upper trendline (Finviz calls it "upper")
- **kind=3** = Lower trendline (Finviz calls it "lower") = **THIS IS THE BLUE LINE ON THE CHART**

### What Master Wants
When Master says **"BLUE trendline"** or **"hammer on blue"**, he means:
- The **lower/support trendline** (kind=3 in Finviz data)
- This appears as BLUE on the Finviz chart
- Check if hammer's **LOW** price is near this line

### The Scanner Should Find
1. **Hammers on BLUE (support)** - Primary focus, MORE IMPORTANT
2. Hammers touching the trendline within **2% tolerance**
3. Look back **5 days** (including today) for recent hammers

## Technical Details

### Finviz Chart Height
- Use **height=400** for Y-coordinate to price conversion
- Formula: `price = max_price - (y / 400) * (max_price - min_price)`

### Pattern Selection
- Only use **ACTIVE patterns** (status=1)
- If multiple patterns of same kind, pick the one with **highest strength**

### Hammer Detection Parameters
- `body_ratio = 0.35` (body <= 35% of total range)
- `wick_ratio = 1.5` (lower wick >= 1.5x body size)
- `min_range_pct = 2.0%` (filters tiny candles)
- `min_body_pct = 0.5%` (filters insignificant bodies)

### Distance Calculation
- For BLUE (lower/support): Compare hammer's **LOW** to trendline price
- Near = within **2%** of trendline

## How to Run

```bash
cd /Users/mormaman/Desktop/dev/trendline-scanner
source venv/bin/activate
python run_scanner.py
```

## Expected Output Format

```
HAMMERS ON BLUE TRENDLINE - Last 5 Days:
  SYMBOL  DATE    (Xd ago) Blue=$XXX.XX Low=$XXX.XX (+/-X.X%) - hammer
```

## File Structure
- `finviz_direct.py` - Fetches Finviz pattern data, calculates trendline prices
- `hammer_detector.py` - Detects hammer candlestick patterns
- `run_scanner.py` - Main scanner CLI
- `data_fetcher.py` - Fetches price data from yfinance

## Remember
- **BLUE line = Lower/Support trendline (kind=3)**
- **Height = 400** for Y-to-price conversion
- **2% tolerance** for "near" trendline
- **5 days lookback** for recent hammers
- Check hammer **LOW** against blue line price
