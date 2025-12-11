#!/usr/bin/env python3
"""
Telegram Bot for Hammer Scanner
Sends alerts when hammers on blue trendline are detected
"""
import os
import logging
from datetime import datetime, time
from typing import Dict, Any
from dotenv import load_dotenv

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

# User settings storage (in production, use a database)
user_settings: Dict[int, Dict[str, Any]] = {}

def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Get user settings with defaults"""
    if user_id not in user_settings:
        user_settings[user_id] = {
            'tolerance': 2.0,
            'patterns': ['wedgeup', 'wedgedown', 'channelup', 'channeldown'],
            'alerts_enabled': True,
            'lookback_days': 5
        }
    return user_settings[user_id]


# Command Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when /start is issued"""
    welcome_text = (
        "🔨 *Hammer Scanner Bot*\n\n"
        "I scan stocks for hammer candlesticks touching trendlines using real Finviz data.\n\n"
        "*Commands:*\n"
        "/scan - Run a full scan now\n"
        "/quick - Quick scan (today only)\n"
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

        # Add scan info
        message = (
            f"📊 *Scan Results*\n"
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
        message = f"⚡ *Quick Scan - Today Only*\n\n" + message

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Quick scan error: {e}")
        await update.message.reply_text(f"❌ Scan failed: {str(e)}")


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
                f"🔔 Alerts: {'ON' if settings['alerts_enabled'] else 'OFF'}",
                callback_data='toggle_alerts'
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

    await update.message.reply_text(f"🔔 Alerts {status}")


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
        await query.edit_message_text(f"🔔 Alerts: {status}")

    elif data == 'back_to_settings':
        keyboard = [
            [InlineKeyboardButton(f"Tolerance: {settings['tolerance']}%", callback_data='settings_tolerance')],
            [InlineKeyboardButton(f"Lookback: {settings['lookback_days']} days", callback_data='settings_lookback')],
            [InlineKeyboardButton("📋 Patterns", callback_data='settings_patterns')],
            [InlineKeyboardButton(
                f"🔔 Alerts: {'ON' if settings['alerts_enabled'] else 'OFF'}",
                callback_data='toggle_alerts'
            )],
        ]
        await query.edit_message_text(
            "⚙️ *Settings*\n\nTap to adjust:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )


# Scheduled Jobs

async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run scheduled scan and send alerts to users with alerts enabled"""
    logger.info("Running scheduled scan...")

    try:
        results = scan_for_hammers(lookback_days=1, tolerance=2.0)

        if not results['blue'] and not results['upper']:
            logger.info("No signals found in scheduled scan")
            return

        message = "🔔 *Scheduled Alert*\n\n" + format_results_for_telegram(results)

        # Send to admin
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )

        # Send to all users with alerts enabled
        for user_id, settings in user_settings.items():
            if settings.get('alerts_enabled', False):
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert to {user_id}: {e}")

    except Exception as e:
        logger.error(f"Scheduled scan error: {e}")


async def daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send daily report at market close"""
    logger.info("Sending daily report...")

    try:
        results = scan_for_hammers(lookback_days=5, tolerance=2.0)

        message = (
            "📊 *Daily Report*\n"
            f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
            + format_results_for_telegram(results)
        )

        # Send to admin
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )

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
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("alerts", alerts))

    # Add callback query handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    # Set up scheduled jobs
    job_queue = application.job_queue

    # Hourly scan (every hour during market hours: 9:30 AM - 4:00 PM ET)
    # For simplicity, run every hour
    job_queue.run_repeating(scheduled_scan, interval=3600, first=60)  # Every hour, start after 1 min

    # Daily report at 4:30 PM ET (21:30 UTC)
    job_queue.run_daily(daily_report, time=time(hour=21, minute=30))

    print("🤖 Bot starting...")
    print("Commands: /start, /scan, /quick, /settings, /alerts, /help")
    print("Scheduled: Hourly scans + Daily report at 4:30 PM ET")

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
