#!/bin/bash
cd /Users/mormaman/Desktop/dev/trendline-scanner
source venv/bin/activate
nohup python telegram_bot.py > bot.log 2>&1 &
echo $! > bot.pid
echo "Bot started with PID $(cat bot.pid)"
