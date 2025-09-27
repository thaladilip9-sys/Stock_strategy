#!/usr/bin/env python3
"""
3-Day High Breakout Trading Bot

A Python trading bot that monitors Indian stocks (NSE) for 3-day high breakouts
and sends real-time notifications via email and Telegram.

Author: Trading Bot Team
License: MIT
"""

import os
import sys
import time
import logging
import schedule
import smtplib
import threading
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import yfinance as yf
    import pandas as pd
    import pytz
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log') if os.getenv('LOG_TO_FILE') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)


class StockBreakoutBot:
    """
    3-Day High Breakout Trading Bot

    Monitors specified stocks for breakouts above their 3-day high
    and sends notifications when breakouts are detected.
    """

    def __init__(self):
        """Initialize the trading bot with configuration"""
        logger.info("Initializing 3-Day High Breakout Bot...")

        # Email configuration
        self.email_config = self._setup_email_config()

        # Telegram configuration  
        self.telegram_config = self._setup_telegram_config()

        # Trading configuration
        self.scan_interval = int(os.getenv('SCAN_INTERVAL_MINUTES', 15))
        self.breakout_threshold = float(os.getenv('BREAKOUT_THRESHOLD_PERCENT', 0.1))
        self.min_volume_ratio = float(os.getenv('MIN_VOLUME_RATIO', 1.2))
        self.enable_volume_check = os.getenv('ENABLE_VOLUME_CHECK', 'true').lower() == 'true'

        # Market timezone
        self.market_timezone = pytz.timezone(os.getenv('MARKET_TIMEZONE', 'Asia/Kolkata'))

        # Default Indian stocks to monitor (high liquidity NSE stocks)
        self.stocks_to_monitor = [
            'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
            'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
            'LT.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'TITAN.NS', 'NESTLEIND.NS'
        ]

        # Notification tracking (prevent duplicates)
        self.notifications_sent = set()

        # Performance tracking
        self.scan_count = 0
        self.breakouts_found = 0
        self.start_time = datetime.now()

        logger.info(f"Bot initialized successfully")
        logger.info(f"Monitoring {len(self.stocks_to_monitor)} stocks")
        logger.info(f"Scan interval: {self.scan_interval} minutes")
        logger.info(f"Breakout threshold: {self.breakout_threshold}%")

    def _setup_email_config(self):
        """Setup email configuration from environment variables"""
        if not os.getenv('SENDER_EMAIL'):
            logger.info("Email notifications disabled (SENDER_EMAIL not set)")
            return None

        return {
            'sender_email': os.getenv('SENDER_EMAIL'),
            'receiver_email': os.getenv('RECEIVER_EMAIL', os.getenv('SENDER_EMAIL')),
            'password': os.getenv('EMAIL_PASSWORD'),
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', 587))
        }

    def _setup_telegram_config(self):
        """Setup Telegram configuration from environment variables"""
        if not os.getenv('TELEGRAM_BOT_TOKEN'):
            logger.info("Telegram notifications disabled (TELEGRAM_BOT_TOKEN not set)")
            return None

        return {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
            'parse_mode': 'Markdown'
        }

    def get_stock_data(self, symbol, period='5d'):
        """
        Fetch stock data using yfinance

        Args:
            symbol (str): Stock symbol (e.g., 'RELIANCE.NS')
            period (str): Data period ('5d' for 5 days)

        Returns:
            pandas.DataFrame: Stock data or None if error
        """
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period=period)

            if data.empty:
                logger.warning(f"No data available for {symbol}")
                return None

            return data

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def check_3day_high_breakout(self, symbol):
        """
        Check if stock has broken its 3-day high

        Args:
            symbol (str): Stock symbol to check

        Returns:
            dict: Breakout information if detected, None otherwise
        """
        try:
            # Get stock data
            data = self.get_stock_data(symbol)

            if data is None or len(data) < 4:
                logger.debug(f"Insufficient data for {symbol}")
                return None

            # Get recent data (last 4 days including today)
            recent_data = data.tail(4)

            # Calculate 3-day high (excluding today)
            three_day_data = recent_data.iloc[:-1]  # Exclude last row (today)
            three_day_high = three_day_data['High'].max()

            # Today's data
            today_data = recent_data.iloc[-1]
            current_price = today_data['Close']
            today_high = today_data['High']
            today_volume = today_data['Volume']

            # Check if today's high broke the 3-day high
            if today_high <= three_day_high:
                logger.debug(f"{symbol}: No breakout - High: ₹{today_high:.2f}, 3D High: ₹{three_day_high:.2f}")
                return None

            # Calculate breakout percentage
            breakout_percentage = ((today_high - three_day_high) / three_day_high) * 100

            # Check if breakout meets minimum threshold
            if breakout_percentage < self.breakout_threshold:
                logger.debug(f"{symbol}: Breakout too small - {breakout_percentage:.2f}%")
                return None

            # Volume analysis (optional)
            volume_ratio = 1.0
            if self.enable_volume_check and len(three_day_data) > 0:
                avg_volume = three_day_data['Volume'].mean()
                volume_ratio = today_volume / avg_volume if avg_volume > 0 else 1.0

                if volume_ratio < self.min_volume_ratio:
                    logger.debug(f"{symbol}: Volume too low - {volume_ratio:.2f}x")
                    return None

            # Breakout detected!
            breakout_info = {
                'symbol': symbol,
                'current_price': float(current_price),
                'today_high': float(today_high),
                'three_day_high': float(three_day_high),
                'breakout_percentage': float(breakout_percentage),
                'volume_ratio': float(volume_ratio),
                'timestamp': datetime.now(self.market_timezone),
                'market_cap_category': self._get_market_cap_category(symbol)
            }

            logger.info(f"🚀 BREAKOUT DETECTED: {symbol} +{breakout_percentage:.2f}%")
            return breakout_info

        except Exception as e:
            logger.error(f"Error checking breakout for {symbol}: {e}")
            return None

    def _get_market_cap_category(self, symbol):
        """Categorize stock by market cap (rough estimation based on symbol)"""
        large_cap = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS']
        if symbol in large_cap:
            return 'Large Cap'
        return 'Mid/Small Cap'

    def send_email_notification(self, breakout_info):
        """Send email notification for breakout"""
        if not self.email_config or not self.email_config['password']:
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = self.email_config['receiver_email']
            msg['Subject'] = f"🚀 BREAKOUT ALERT: {breakout_info['symbol']}"

            # Create email body
            body = f"""
📈 STOCK BREAKOUT DETECTED!

🏢 Stock: {breakout_info['symbol']}
💰 Current Price: ₹{breakout_info['current_price']:.2f}
🎯 Today's High: ₹{breakout_info['today_high']:.2f}
📊 3-Day High: ₹{breakout_info['three_day_high']:.2f}
🚀 Breakout: +{breakout_info['breakout_percentage']:.2f}%
📊 Volume: {breakout_info['volume_ratio']:.2f}x average
🕐 Time: {breakout_info['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z')}
🏷️ Category: {breakout_info['market_cap_category']}

This stock has broken its 3-day high resistance level with {
'strong' if breakout_info['volume_ratio'] > 2 else 'moderate'
} volume support.

⚠️ This is for informational purposes only. Always do your own research 
before making any trading decisions.

Happy Trading! 📈
            """

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['sender_email'], self.email_config['password'])
            server.send_message(msg)
            server.quit()

            logger.info(f"✅ Email notification sent for {breakout_info['symbol']}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email for {breakout_info['symbol']}: {e}")
            return False

    def send_telegram_notification(self, breakout_info):
        """Send Telegram notification for breakout"""
        if not self.telegram_config or not self.telegram_config['chat_id']:
            return False

        try:
            # Create Telegram message
            message = f"""🚀 *BREAKOUT ALERT*

📊 *{breakout_info['symbol']}*
💰 ₹{breakout_info['current_price']:.2f}
📈 +{breakout_info['breakout_percentage']:.2f}%
📊 Vol: {breakout_info['volume_ratio']:.1f}x
🏷️ {breakout_info['market_cap_category']}
⏰ {breakout_info['timestamp'].strftime('%H:%M')}

_3-day resistance broken with {'strong' if breakout_info['volume_ratio'] > 2 else 'moderate'} volume_"""

            url = f"https://api.telegram.org/bot{self.telegram_config['bot_token']}/sendMessage"
            payload = {
                'chat_id': self.telegram_config['chat_id'],
                'text': message,
                'parse_mode': self.telegram_config['parse_mode']
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ Telegram notification sent for {breakout_info['symbol']}")
                return True
            else:
                logger.error(f"❌ Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to send Telegram for {breakout_info['symbol']}: {e}")
            return False

    def send_notifications(self, breakout_info):
        """Send all configured notifications"""
        notifications_sent = 0

        if self.send_email_notification(breakout_info):
            notifications_sent += 1

        if self.send_telegram_notification(breakout_info):
            notifications_sent += 1

        if notifications_sent == 0:
            logger.warning(f"No notifications configured or all failed for {breakout_info['symbol']}")

        return notifications_sent > 0

    def is_market_open(self):
        """Check if Indian stock market is currently open"""
        try:
            now = datetime.now(self.market_timezone)

            # Check if it's a weekday (Monday=0, Friday=4)
            if now.weekday() >= 5:  # Saturday=5, Sunday=6
                return False

            # Market hours: 9:15 AM to 3:30 PM IST
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

            return market_open <= now <= market_close

        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False  # Fail safe

    def run_scan(self):
        """Run a single breakout scan cycle"""
        if not self.is_market_open():
            logger.info("💤 Market closed - skipping scan")
            return []

        logger.info("🔍 Starting breakout scan...")
        scan_start_time = datetime.now()
        breakouts_in_scan = []
        errors_in_scan = 0

        for i, symbol in enumerate(self.stocks_to_monitor, 1):
            try:
                logger.debug(f"Scanning {symbol} ({i}/{len(self.stocks_to_monitor)})")

                breakout = self.check_3day_high_breakout(symbol)

                if breakout:
                    # Check if we've already notified about this stock today
                    notification_key = f"{symbol}_{datetime.now().strftime('%Y-%m-%d')}"

                    if notification_key not in self.notifications_sent:
                        logger.info(f"🚀 NEW BREAKOUT: {symbol} +{breakout['breakout_percentage']:.2f}%")

                        # Send notifications
                        if self.send_notifications(breakout):
                            self.notifications_sent.add(notification_key)
                            breakouts_in_scan.append(breakout)
                            self.breakouts_found += 1

                    else:
                        logger.debug(f"📝 {symbol}: Already notified today")

                # Small delay between stocks to be respectful to APIs
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Error scanning {symbol}: {e}")
                errors_in_scan += 1

        # Scan summary
        scan_duration = (datetime.now() - scan_start_time).total_seconds()
        self.scan_count += 1

        logger.info(f"✅ Scan complete: {len(breakouts_in_scan)} new breakouts, "
                   f"{errors_in_scan} errors, {scan_duration:.1f}s duration")

        if not breakouts_in_scan:
            logger.info("📊 No new breakouts found in this scan")

        return breakouts_in_scan

    def get_bot_stats(self):
        """Get bot performance statistics"""
        uptime = datetime.now() - self.start_time
        return {
            'uptime': str(uptime).split('.')[0],  # Remove microseconds
            'scans_completed': self.scan_count,
            'breakouts_found': self.breakouts_found,
            'notifications_sent': len(self.notifications_sent),
            'stocks_monitored': len(self.stocks_to_monitor),
            'market_open': self.is_market_open()
        }

    def run_scheduler(self):
        """Run the bot with scheduler for continuous operation"""
        logger.info("🤖 Starting Stock Breakout Bot scheduler")
        logger.info(f"📊 Monitoring {len(self.stocks_to_monitor)} stocks")
        logger.info(f"⏰ Scan interval: {self.scan_interval} minutes")

        # Schedule scans
        schedule.every(self.scan_interval).minutes.do(self.run_scan)

        # Schedule daily cleanup at market close
        schedule.every().day.at("16:00").do(self._daily_cleanup)

        # Run initial scan if market is open
        if self.is_market_open():
            logger.info("🚀 Running initial scan...")
            self.run_scan()

        # Main scheduler loop
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                logger.info("🛑 Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

    def _daily_cleanup(self):
        """Daily cleanup tasks"""
        logger.info("🧹 Running daily cleanup...")

        # Clear notification cache for new day
        self.notifications_sent.clear()

        # Log daily statistics
        stats = self.get_bot_stats()
        logger.info(f"📊 Daily Stats: {stats['scans_completed']} scans, "
                   f"{stats['breakouts_found']} breakouts found")


class KeepAliveServer:
    """Simple HTTP server to keep cloud platforms happy"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.port = int(os.environ.get('PORT', 10000))

    class RequestHandler(BaseHTTPRequestHandler):
        def __init__(self, bot_instance, *args, **kwargs):
            self.bot = bot_instance
            super().__init__(*args, **kwargs)

        def do_GET(self):
            """Handle GET requests"""
            try:
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()

                    stats = self.bot.get_bot_stats()
                    html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>3-Day Breakout Bot Status</title>
                        <meta http-equiv="refresh" content="60">
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                            .container {{ max-width: 600px; margin: 0 auto; background: white; 
                                        padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                            .status {{ color: {'green' if stats['market_open'] else 'orange'}; font-weight: bold; }}
                            .stat {{ margin: 10px 0; padding: 8px; background: #f8f9fa; border-radius: 4px; }}
                            .header {{ color: #333; text-align: center; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1 class="header">🤖 3-Day Breakout Bot</h1>
                            <h2 class="header status">{'🟢 ACTIVE' if stats['market_open'] else '🟡 STANDBY'}</h2>

                            <div class="stat"><strong>Uptime:</strong> {stats['uptime']}</div>
                            <div class="stat"><strong>Scans Completed:</strong> {stats['scans_completed']}</div>
                            <div class="stat"><strong>Breakouts Found:</strong> {stats['breakouts_found']}</div>
                            <div class="stat"><strong>Notifications Sent:</strong> {stats['notifications_sent']}</div>
                            <div class="stat"><strong>Stocks Monitored:</strong> {stats['stocks_monitored']}</div>
                            <div class="stat"><strong>Market Status:</strong> 
                                {'🟢 OPEN' if stats['market_open'] else '🔴 CLOSED'}
                            </div>
                            <div class="stat"><strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>

                            <p style="text-align: center; margin-top: 30px; color: #666; font-size: 14px;">
                                Auto-refreshes every 60 seconds<br>
                                Market Hours: 9:15 AM - 3:30 PM IST (Mon-Fri)
                            </p>
                        </div>
                    </body>
                    </html>
                    """

                    self.wfile.write(html.encode())

                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()

                    health_data = {
                        'status': 'healthy',
                        'timestamp': datetime.now().isoformat(),
                        **self.bot.get_bot_stats()
                    }

                    import json
                    self.wfile.write(json.dumps(health_data).encode())

                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'404 Not Found')

            except Exception as e:
                logger.error(f"HTTP server error: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'Internal Server Error')

        def log_message(self, format, *args):
            """Suppress HTTP access logs"""
            pass

    def start(self):
        """Start the HTTP server in background thread"""
        try:
            # Create server with bot instance bound to handler
            handler = lambda *args, **kwargs: self.RequestHandler(self.bot, *args, **kwargs)
            server = HTTPServer(('0.0.0.0', self.port), handler)

            logger.info(f"🌐 HTTP server started on port {self.port}")
            logger.info(f"📊 Status page: http://localhost:{self.port}")

            server.serve_forever()

        except Exception as e:
            logger.error(f"❌ Failed to start HTTP server: {e}")


def main():
    """Main entry point"""
    try:
        logger.info("🚀 Starting 3-Day High Breakout Trading Bot")

        # Initialize bot
        bot = StockBreakoutBot()

        # Start HTTP server in background (for cloud platforms)
        if os.environ.get('PORT'):  # Running on cloud platform
            server = KeepAliveServer(bot)
            server_thread = threading.Thread(target=server.start, daemon=True)
            server_thread.start()

        # Start the bot scheduler
        bot.run_scheduler()

    except KeyboardInterrupt:
        logger.info("🛑 Bot shutdown requested")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Bot shutdown complete")


if __name__ == "__main__":
    main()
