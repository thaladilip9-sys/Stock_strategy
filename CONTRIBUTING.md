# Contributing to 3-Day Breakout Trading Bot

Thank you for your interest in contributing to this project! 🎉

## 🤝 How to Contribute

### Reporting Issues
- Use the GitHub Issues tab to report bugs
- Provide detailed information about the issue
- Include steps to reproduce if possible

### Submitting Changes
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📋 Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/3day-breakout-bot.git
   cd 3day-breakout-bot
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run tests:**
   ```bash
   python -c "from bot import StockBreakoutBot; bot = StockBreakoutBot(); print('✅ Setup successful')"
   ```

## 🔧 Code Guidelines

### Python Style
- Follow PEP 8 style guide
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and small

### Trading Logic
- Always validate trading logic thoroughly
- Add appropriate error handling
- Consider edge cases (market holidays, data unavailability)
- Test with paper trading before live implementation

### Documentation
- Update README.md if you add new features
- Document any new environment variables
- Add inline comments for complex logic

## 🧪 Testing

Before submitting a PR:

1. **Test bot initialization:**
   ```bash
   python -c "from bot import StockBreakoutBot; StockBreakoutBot()"
   ```

2. **Test with sample data:**
   ```bash
   python bot.py  # Should start without errors
   ```

3. **Check for common issues:**
   - Ensure all imports work
   - Validate environment variable handling
   - Test notification systems (if configured)

## 📊 Trading Strategy Improvements

When contributing trading logic:

1. **Backtest thoroughly** - Validate with historical data
2. **Consider risk management** - Add appropriate safeguards
3. **Document the strategy** - Explain the logic clearly
4. **Start conservative** - Prefer false negatives over false positives

## 🚨 Security

- Never commit API keys or credentials
- Use environment variables for sensitive data
- Review code for security vulnerabilities
- Test with minimal permissions first

## 📝 Pull Request Template

When submitting a PR, please include:

- **Description** of changes made
- **Motivation** for the changes
- **Testing** performed
- **Breaking changes** (if any)
- **Screenshots** (if UI changes)

## 🤖 Bot Behavior Guidelines

### Notifications
- Avoid spam - limit notification frequency
- Provide useful information in alerts
- Handle notification failures gracefully

### Market Data
- Respect API rate limits
- Handle data unavailability
- Cache data when appropriate

### Error Handling
- Log errors appropriately
- Recover from temporary failures
- Fail gracefully on permanent issues

## 🎯 Areas for Contribution

We welcome contributions in these areas:

### Features
- Additional breakout patterns
- More notification channels (Slack, Discord, etc.)
- Advanced filtering options
- Portfolio management features
- Risk management tools

### Improvements
- Better error handling
- Performance optimizations
- Code refactoring
- Documentation improvements
- Test coverage

### Integrations
- More broker APIs
- Alternative data sources
- Cloud platform support
- Monitoring and alerting

## 📞 Getting Help

- Check existing issues first
- Join discussions in issue comments
- Be respectful and constructive
- Provide context and examples

## ⚠️ Trading Disclaimer

When contributing trading-related code:

- This is educational software
- Trading involves financial risk
- Always encourage paper trading first
- Include appropriate risk warnings
- Follow applicable regulations

Thank you for contributing to make this project better! 🚀
