#!/usr/bin/env python3
"""
Telegram Bot for Hammer Scanner
Sends alerts when hammers on blue trendline are detected
Includes market open/close notifications
"""
import os
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any, Set
from dotenv import load_dotenv
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    JobQueue
)

from scanner_service import scan_for_hammers, format_results_for_telegram

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('TELEGRAM_ADMIN_CHAT_ID')  # Your chat ID for alerts

# Timezone for US market
ET = pytz.timezone('America/New_York')

# Market hours (Eastern Time)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# User settings storage (in production, use a database)
user_settings: Dict[int, Dict[str, Any]] = {}
# Store all users who have interacted with the bot
registered_users: Set[int] = set()

def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Get user settings with defaults"""
    registered_users.add(user_id)
    if user_id not in user_settings:
        user_settings[user_id] = {
            'tolerance': 2.0,
            'patterns': ['wedgeup', 'wedgedown', 'channelup', 'channeldown'],
            'alerts_enabled': True,
            'lookback_days': 5,
            'market_alerts': True  # New: market open/close alerts
        }
    return user_settings[user_id]


def is_market_open() -> bool:
    """Check if US stock market is currently open"""
    now = datetime.now(ET)

    # Market is closed on weekends
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Check if within market hours
    market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0, microsecond=0)
    market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)

    return market_open <= now <= market_close


def get_next_market_event() -> tuple:
    """Get the next market open or close event"""
    now = datetime.now(ET)
    today = now.date()

    market_open_today = ET.localize(datetime.combine(today, time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)))
    market_close_today = ET.localize(datetime.combine(today, time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)))

    # If it's a weekday
    if now.weekday() < 5:
        if now < market_open_today:
            return ('open', market_open_today)
        elif now < market_close_today:
            return ('close', market_close_today)

    # Find next trading day
    next_day = today + timedelta(days=1)
    while next_day.weekday() >= 5:  # Skip weekends
        next_day += timedelta(days=1)

    next_open = ET.localize(datetime.combine(next_day, time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)))
    return ('open', next_open)


# Command Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when /start is issued"""
    user_id = update.effective_user.id
    get_user_settings(user_id)  # Register user

    # Check market status
    market_status = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
    event_type, event_time = get_next_market_event()
    next_event = f"Next {event_type}: {event_time.strftime('%a %I:%M %p ET')}"

    welcome_text = (
        "🔨 *Hammer Scanner Bot*\n\n"
        f"Market Status: {market_status}\n"
        f"_{next_event}_\n\n"
        "I scan stocks for hammer candlesticks touching trendlines using real Finviz data.\n\n"
        "*Commands:*\n"
        "/scan - Run a full scan now\n"
        "/quick - Quick scan (today only)\n"
        "/market - Check market status\n"
        "/settings - Adjust scan settings\n"
        "/alerts - Toggle alert notifications\n"
        "/help - Show this help message\n\n"
        "_Blue trendline = Support line (kind=3 in Finviz)_\n"
        "_Looking for hammers within 2% of trendline_"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message"""
    await start(update, context)


async def market_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current market status"""
    now = datetime.now(ET)
    is_open = is_market_open()
    event_type, event_time = get_next_market_event()

    if is_open:
        time_to_close = event_time - now
        hours, remainder = divmod(int(time_to_close.total_seconds()), 3600)
        minutes = remainder // 60
        status_text = (
            "🟢 *Market is OPEN*\n\n"
            f"Current time: {now.strftime('%I:%M %p ET')}\n"
            f"Closes at: {event_time.strftime('%I:%M %p ET')}\n"
            f"Time remaining: {hours}h {minutes}m\n\n"
            "_You can buy and sell stocks now!_"
        )
    else:
        time_to_open = event_time - now
        days = time_to_open.days
        hours, remainder = divmod(int(time_to_open.total_seconds()) % 86400, 3600)
        minutes = remainder // 60

        if days > 0:
            time_str = f"{days}d {hours}h {minutes}m"
        else:
            time_str = f"{hours}h {minutes}m"

        status_text = (
            "🔴 *Market is CLOSED*\n\n"
            f"Current time: {now.strftime('%I:%M %p ET')}\n"
            f"Opens: {event_time.strftime('%a %b %d at %I:%M %p ET')}\n"
            f"Time until open: {time_str}\n\n"
            "_Market hours: Mon-Fri 9:30 AM - 4:00 PM ET_"
        )

    await update.message.reply_text(status_text, parse_mode='Markdown')


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run full hammer scan"""
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    await update.message.reply_text("🔍 Scanning... This may take a minute.")

    try:
        results = scan_for_hammers(
            patterns=settings['patterns'],
            lookback_days=settings['lookback_days'],
            tolerance=settings['tolerance']
        )

        message = format_results_for_telegram(results)

        # Add scan info and market status
        market_status = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
        message = (
            f"📊 *Scan Results* | Market: {market_status}\n"
            f"_Tolerance: {settings['tolerance']}% | Lookback: {settings['lookback_days']} days_\n\n"
            + message
        )

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Scan error: {e}")
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")


async def quick_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick scan - today only"""
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    await update.message.reply_text("⚡ Quick scan (today only)...")

    try:
        results = scan_for_hammers(
            patterns=settings['patterns'],
            lookback_days=1,  # Today only
            tolerance=settings['tolerance']
        )

        if not results['blue'] and not results['upper']:
            await update.message.reply_text("📭 No hammers on trendlines today.")
            return

        message = format_results_for_telegram(results)
        market_status = "🟢 OPEN" if is_market_open() else "🔴 CLOSED"
        message = f"⚡ *Quick Scan - Today Only* | Market: {market_status}\n\n" + message

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Quick scan error: {e}")
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show settings menu"""
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    keyboard = [
        [
            InlineKeyboardButton(f"Tolerance: {settings['tolerance']}%", callback_data='settings_tolerance'),
        ],
        [
            InlineKeyboardButton(f"Lookback: {settings['lookback_days']} days", callback_data='settings_lookback'),
        ],
        [
            InlineKeyboardButton("📋 Patterns", callback_data='settings_patterns'),
        ],
        [
            InlineKeyboardButton(
                f"🔔 Scan Alerts: {'ON' if settings['alerts_enabled'] else 'OFF'}",
                callback_data='toggle_alerts'
            ),
        ],
        [
            InlineKeyboardButton(
                f"🕐 Market Alerts: {'ON' if settings.get('market_alerts', True) else 'OFF'}",
                callback_data='toggle_market_alerts'
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚙️ *Settings*\n\nTap to adjust:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle alerts on/off"""
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    settings['alerts_enabled'] = not settings['alerts_enabled']
    status = "enabled ✅" if settings['alerts_enabled'] else "disabled ❌"

    await update.message.reply_text(f"🔔 Scan Alerts {status}")


# Callback Query Handlers

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    settings = get_user_settings(user_id)
    data = query.data

    if data == 'settings_tolerance':
        keyboard = [
            [
                InlineKeyboardButton("1%", callback_data='set_tolerance_1.0'),
                InlineKeyboardButton("1.5%", callback_data='set_tolerance_1.5'),
                InlineKeyboardButton("2%", callback_data='set_tolerance_2.0'),
                InlineKeyboardButton("3%", callback_data='set_tolerance_3.0'),
            ],
            [InlineKeyboardButton("« Back", callback_data='back_to_settings')],
        ]
        await query.edit_message_text(
            f"📏 *Tolerance*\nCurrent: {settings['tolerance']}%\n\nSelect new tolerance:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif data.startswith('set_tolerance_'):
        tolerance = float(data.replace('set_tolerance_', ''))
        settings['tolerance'] = tolerance
        await query.edit_message_text(f"✅ Tolerance set to {tolerance}%")

    elif data == 'settings_lookback':
        keyboard = [
            [
                InlineKeyboardButton("1 day", callback_data='set_lookback_1'),
                InlineKeyboardButton("3 days", callback_data='set_lookback_3'),
                InlineKeyboardButton("5 days", callback_data='set_lookback_5'),
                InlineKeyboardButton("7 days", callback_data='set_lookback_7'),
            ],
            [InlineKeyboardButton("« Back", callback_data='back_to_settings')],
        ]
        await query.edit_message_text(
            f"📅 *Lookback Days*\nCurrent: {settings['lookback_days']} days\n\nSelect new lookback:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif data.startswith('set_lookback_'):
        days = int(data.replace('set_lookback_', ''))
        settings['lookback_days'] = days
        await query.edit_message_text(f"✅ Lookback set to {days} days")

    elif data == 'settings_patterns':
        patterns = settings['patterns']
        all_patterns = ['wedgeup', 'wedgedown', 'channelup', 'channeldown', 'horizontal']

        keyboard = []
        for p in all_patterns:
            status = "✅" if p in patterns else "❌"
            keyboard.append([InlineKeyboardButton(f"{status} {p}", callback_data=f'toggle_pattern_{p}')])
        keyboard.append([InlineKeyboardButton("« Back", callback_data='back_to_settings')])

        await query.edit_message_text(
            "📋 *Patterns*\nTap to toggle:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif data.startswith('toggle_pattern_'):
        pattern = data.replace('toggle_pattern_', '')
        if pattern in settings['patterns']:
            settings['patterns'].remove(pattern)
        else:
            settings['patterns'].append(pattern)

        # Refresh pattern menu
        patterns = settings['patterns']
        all_patterns = ['wedgeup', 'wedgedown', 'channelup', 'channeldown', 'horizontal']

        keyboard = []
        for p in all_patterns:
            status = "✅" if p in patterns else "❌"
            keyboard.append([InlineKeyboardButton(f"{status} {p}", callback_data=f'toggle_pattern_{p}')])
        keyboard.append([InlineKeyboardButton("« Back", callback_data='back_to_settings')])

        await query.edit_message_text(
            "📋 *Patterns*\nTap to toggle:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif data == 'toggle_alerts':
        settings['alerts_enabled'] = not settings['alerts_enabled']
        status = "ON ✅" if settings['alerts_enabled'] else "OFF ❌"
        await query.edit_message_text(f"🔔 Scan Alerts: {status}")

    elif data == 'toggle_market_alerts':
        settings['market_alerts'] = not settings.get('market_alerts', True)
        status = "ON ✅" if settings['market_alerts'] else "OFF ❌"
        await query.edit_message_text(f"🕐 Market Alerts: {status}")

    elif data == 'back_to_settings':
        keyboard = [
            [InlineKeyboardButton(f"Tolerance: {settings['tolerance']}%", callback_data='settings_tolerance')],
            [InlineKeyboardButton(f"Lookback: {settings['lookback_days']} days", callback_data='settings_lookback')],
            [InlineKeyboardButton("📋 Patterns", callback_data='settings_patterns')],
            [InlineKeyboardButton(
                f"🔔 Scan Alerts: {'ON' if settings['alerts_enabled'] else 'OFF'}",
                callback_data='toggle_alerts'
            )],
            [InlineKeyboardButton(
                f"🕐 Market Alerts: {'ON' if settings.get('market_alerts', True) else 'OFF'}",
                callback_data='toggle_market_alerts'
            )],
        ]
        await query.edit_message_text(
            "⚙️ *Settings*\n\nTap to adjust:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


# Scheduled Jobs

async def send_to_users(context: ContextTypes.DEFAULT_TYPE, message: str, check_setting: str = None) -> None:
    """Send message to all registered users"""
    # Send to admin first
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send to admin: {e}")

    # Send to all registered users
    for user_id in registered_users:
        if check_setting:
            settings = get_user_settings(user_id)
            if not settings.get(check_setting, True):
                continue
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")


async def market_open_warning(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send 15-minute warning before market opens"""
    logger.info("Sending market open warning (15 min)...")
    message = (
        "⏰ *15 Minutes Until Market Opens!*\n\n"
        "🟢 Market opens at 9:30 AM ET\n\n"
        "_Get ready to trade! Use /scan to find opportunities._"
    )
    await send_to_users(context, message, 'market_alerts')


async def market_open_notification(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send notification when market opens"""
    logger.info("Sending market open notification...")
    message = (
        "🔔 *Market is NOW OPEN!*\n\n"
        "🟢 Trading hours: 9:30 AM - 4:00 PM ET\n\n"
        "_You can now buy and sell stocks!_\n"
        "_Use /scan to find hammer signals._"
    )
    await send_to_users(context, message, 'market_alerts')


async def market_close_warning(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send 15-minute warning before market closes"""
    logger.info("Sending market close warning (15 min)...")
    message = (
        "⏰ *15 Minutes Until Market Closes!*\n\n"
        "🔴 Market closes at 4:00 PM ET\n\n"
        "_Finish your trades soon!_"
    )
    await send_to_users(context, message, 'market_alerts')


async def market_close_notification(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send notification when market closes"""
    logger.info("Sending market close notification...")
    message = (
        "🔔 *Market is NOW CLOSED!*\n\n"
        "🔴 Trading has ended for today.\n"
        "📅 Next open: Tomorrow at 9:30 AM ET (if weekday)\n\n"
        "_See you tomorrow!_"
    )
    await send_to_users(context, message, 'market_alerts')


async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run scheduled scan and send alerts to users with alerts enabled"""
    # Only run during market hours
    if not is_market_open():
        logger.info("Skipping scheduled scan - market closed")
        return

    logger.info("Running scheduled scan...")

    try:
        results = scan_for_hammers(lookback_days=1, tolerance=2.0)

        if not results['blue'] and not results['upper']:
            logger.info("No signals found in scheduled scan")
            return

        message = "🔔 *Scheduled Alert*\n\n" + format_results_for_telegram(results)
        await send_to_users(context, message, 'alerts_enabled')

    except Exception as e:
        logger.error(f"Scheduled scan error: {e}")


async def daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send daily report at market close"""
    logger.info("Sending daily report...")

    try:
        results = scan_for_hammers(lookback_days=5, tolerance=2.0)

        message = (
            "📊 *Daily Report*\n"
            f"_{datetime.now(ET).strftime('%Y-%m-%d %I:%M %p ET')}_\n\n"
            + format_results_for_telegram(results)
        )
        await send_to_users(context, message, 'alerts_enabled')

    except Exception as e:
        logger.error(f"Daily report error: {e}")


def main() -> None:
    """Start the bot"""
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in environment")
        print("1. Create a bot with @BotFather on Telegram")
        print("2. Copy the token")
        print("3. Create .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
        return

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("quick", quick_scan))
    application.add_handler(CommandHandler("market", market_status))
    application.add_handler(CommandHandler("settings", settings_cmd))
    application.add_handler(CommandHandler("alerts", alerts))

    # Add callback query handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Set up scheduled jobs
    job_queue = application.job_queue

    # Market open alerts (9:15 AM and 9:30 AM ET = 14:15 and 14:30 UTC)
    # Note: These times are in UTC
    job_queue.run_daily(market_open_warning, time=time(hour=14, minute=15))  # 9:15 AM ET
    job_queue.run_daily(market_open_notification, time=time(hour=14, minute=30))  # 9:30 AM ET

    # Market close alerts (3:45 PM and 4:00 PM ET = 20:45 and 21:00 UTC)
    job_queue.run_daily(market_close_warning, time=time(hour=20, minute=45))  # 3:45 PM ET
    job_queue.run_daily(market_close_notification, time=time(hour=21, minute=0))  # 4:00 PM ET

    # Hourly scan during market hours
    job_queue.run_repeating(scheduled_scan, interval=3600, first=60)  # Every hour

    # Daily report at 4:30 PM ET (21:30 UTC)
    job_queue.run_daily(daily_report, time=time(hour=21, minute=30))

    print("🤖 Bot starting...")
    print("Commands: /start, /scan, /quick, /market, /settings, /alerts, /help")
    print("Market Alerts:")
    print("  - 15 min before open (9:15 AM ET)")
    print("  - Market open (9:30 AM ET)")
    print("  - 15 min before close (3:45 PM ET)")
    print("  - Market close (4:00 PM ET)")
    print("Scheduled: Hourly scans + Daily report at 4:30 PM ET")

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
