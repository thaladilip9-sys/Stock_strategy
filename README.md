# 🚀 3-Day High Breakout Trading Bot

A Python trading bot that monitors Indian stocks (NSE) for 3-day high breakouts and sends real-time notifications via email and Telegram. Designed for 24x7 operation on cloud platforms like Render.

## ✨ Features

- 📊 **3-Day High Breakout Detection** - Identifies stocks breaking 3-day resistance levels
- 🔔 **Real-time Notifications** - Email and Telegram alerts for breakouts
- 🕘 **Market Hours Aware** - Operates only during NSE trading hours (9:15 AM - 3:30 PM IST)
- 🛡️ **Error Recovery** - Robust error handling and automatic recovery
- 📈 **Volume Analysis** - Considers volume ratio for breakout validation
- ⚡ **Cloud Ready** - Optimized for Render, AWS, and other cloud platforms
- 🔒 **Secure** - Environment-based configuration for sensitive data

## 📊 Monitored Stocks

The bot monitors these high-liquidity Indian stocks by default:
- RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, ICICIBANK.NS
- HINDUNILVR.NS, ITC.NS, SBIN.NS, BHARTIARTL.NS, KOTAKBANK.NS
- LT.NS, ASIANPAINT.NS, MARUTI.NS, TITAN.NS, NESTLEIND.NS

## 🚀 Quick Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Option 1: One-Click Deploy
1. Click the "Deploy to Render" button above
2. Connect your GitHub account
3. Set environment variables (see Configuration section)
4. Deploy!

### Option 2: Manual Deploy
1. Fork this repository
2. Create a new Web Service on [Render](https://render.com)
3. Connect your forked repository
4. Use these settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Plan:** Starter ($7/month for 24x7 operation)

## ⚙️ Configuration

Set these environment variables in your Render dashboard:

### Required
```bash
# No required variables - bot works with default notifications to console
```

### Optional (for notifications)
```bash
# Email Notifications (recommended)
SENDER_EMAIL=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Custom Settings (optional)
SCAN_INTERVAL_MINUTES=15
BREAKOUT_THRESHOLD_PERCENT=0.1
```

## 📧 Email Setup (Gmail)

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password:**
   - Go to Google Account → Security → 2-Step Verification → App passwords
   - Select "Mail" and generate password
   - Use this password in `EMAIL_PASSWORD` environment variable

## 📱 Telegram Setup (Optional)

1. **Create Bot:**
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. **Get Chat ID:**
   - Start a chat with your bot
   - Send any message
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Copy your chat ID from the response

## 💻 Local Development

### Prerequisites
- Python 3.8+
- pip

### Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/3day-breakout-bot.git
   cd 3day-breakout-bot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables:**
   ```bash
   export SENDER_EMAIL=your_email@gmail.com
   export EMAIL_PASSWORD=your_app_password
   ```

4. **Run the bot:**
   ```bash
   python bot.py
   ```

## 📁 Project Structure

```
3day-breakout-bot/
│
├── bot.py                 # Main trading bot application
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment configuration
├── Dockerfile            # Docker deployment option
├── README.md             # This file
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore rules
└── docs/
    ├── DEPLOYMENT.md     # Detailed deployment guide
    ├── API_INTEGRATION.md # Broker API integration guide
    └── STRATEGY.md       # Trading strategy explanation
```

## 🔧 Advanced Configuration

### Custom Stock List
Edit the `stocks_to_monitor` list in `bot.py`:
```python
self.stocks_to_monitor = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS',
    # Add your stocks here
]
```

### Scan Frequency
Set `SCAN_INTERVAL_MINUTES` environment variable (default: 15 minutes):
```bash
SCAN_INTERVAL_MINUTES=30  # Scan every 30 minutes
```

### Breakout Threshold
Set minimum breakout percentage:
```bash
BREAKOUT_THRESHOLD_PERCENT=0.5  # Require 0.5% minimum breakout
```

## 📊 Broker API Integration

For better data quality and real-time prices, integrate with Indian broker APIs:

### Supported Free APIs
- **Upstox API** (Free) - Recommended
- **Angel One API** (Free)
- **Fyers API** (Free)

See [API_INTEGRATION.md](docs/API_INTEGRATION.md) for detailed setup instructions.

## 💰 Hosting Costs

| Platform | Monthly Cost | 24x7 Uptime | Ease of Use | Best For |
|----------|--------------|-------------|-------------|----------|
| **Render (Paid)** | $7 | ✅ | ⭐⭐⭐⭐⭐ | **Recommended** |
| Railway | $5 + usage | ✅ | ⭐⭐⭐⭐ | Developers |
| AWS EC2 | $7.49 | ✅ | ⭐⭐ | Scalable apps |
| VPS (Cloudzy) | $3.48 | ✅ | ⭐⭐⭐ | Budget option |

## 📈 Trading Strategy

### 3-Day High Breakout Logic
1. **Calculate 3-day high** from historical data (excluding current day)
2. **Monitor current price** for breakthrough
3. **Validate with volume** - ensure above-average trading volume
4. **Send notification** when breakout confirmed
5. **Prevent duplicates** - one notification per stock per day

### Performance Expectations
- **Win Rate:** 45-55% (market dependent)
- **Best Markets:** Trending markets with momentum
- **Risk Management:** Always use stop-losses and position sizing

## 🛡️ Security & Best Practices

### Security
- ✅ All sensitive data in environment variables
- ✅ No credentials committed to repository
- ✅ Secure API key handling
- ✅ HTTPS-only communications

### Trading Safety
- ✅ Start with paper trading
- ✅ Use small position sizes initially
- ✅ Implement stop-losses
- ✅ Monitor performance regularly

## 🐛 Troubleshooting

### Common Issues

**Bot not running 24x7?**
- Ensure you're using Render's paid plan ($7/month)
- Check logs for runtime errors
- Verify all environment variables are set

**No notifications received?**
- Test email credentials locally first
- Check spam/junk folders
- Verify Telegram bot token and chat ID
- Ensure bot runs during market hours

**False breakouts?**
- Increase `BREAKOUT_THRESHOLD_PERCENT`
- Add volume confirmation requirements
- Consider multiple timeframe analysis

### Getting Help
1. Check the [Issues](https://github.com/yourusername/3day-breakout-bot/issues) page
2. Review logs in your hosting platform dashboard
3. Test configurations locally before deploying

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results. Always:

- Do your own research
- Start with paper trading
- Use proper risk management
- Comply with local regulations
- Never invest more than you can afford to lose

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## ⭐ Show Your Support

If this project helped you, please give it a ⭐ star!

---

**Happy Trading! 📈**

For detailed setup instructions, see [DEPLOYMENT.md](docs/DEPLOYMENT.md)
