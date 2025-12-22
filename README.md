# BTC Futures Trading Bot

A risk-focused Bitcoin futures trading bot using EMA cross signals with MACD and volume confirmation, designed for Gate.io exchange.

## Features

- **EMA Cross Strategy**: Uses fast and slow EMA crossover as primary signal
- **MACD Confirmation**: Validates signals with MACD indicator
- **Volume Confirmation**: Ensures volume increase before entering trades
- **Risk Management**: 
  - Configurable leverage (default 3x)
  - Target profit per trade ($150-200)
  - Hard stop loss protection for sudden price dumps (10-15K movements)
  - Position sizing based on profit targets
- **Simulation Mode**: Test the bot without placing real orders
- **Gate.io Integration**: Full futures trading API support

## Project Structure

```
.
├── main.py                          # Main bot runner
├── config.py                        # Configuration management
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
├── exchange/
│   └── gateio_client.py            # Gate.io API client
├── indicators/
│   └── technical_indicators.py     # Technical indicator calculations
├── strategy/
│   └── ema_macd_volume_strategy.py # Trading strategy implementation
├── risk/
│   └── risk_manager.py             # Risk management and position sizing
└── utils/
    └── logger.py                   # Logging utilities
```

## Installation

1. **Clone or navigate to the project directory**

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**:
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your configuration
# For simulation mode, API keys are optional
# For live trading, you MUST provide valid Gate.io API keys
```

## Configuration

Edit the `.env` file with your settings:

```env
# Gate.io API Credentials (required for live trading)
GATE_API_KEY=your_api_key_here
GATE_API_SECRET=your_api_secret_here
GATE_SANDBOX=true  # Use testnet for testing

# Trading Configuration
INITIAL_BALANCE=10000        # Starting balance in USDT
LEVERAGE=3                   # Trading leverage (1-125)
SYMBOL=BTC_USDT             # Trading pair
PROFIT_TARGET_USD=150       # Target profit per trade in USD

# Risk Management
HARD_STOP_LOSS_USD=10000    # Hard stop loss for emergency exits
ENABLE_SIMULATION=true      # Set to false for live trading

# Technical Indicators
EMA_FAST=12                 # Fast EMA period
EMA_SLOW=26                 # Slow EMA period
MACD_FAST=12                # MACD fast period
MACD_SLOW=26                # MACD slow period
MACD_SIGNAL=9               # MACD signal period
```

## Risk Management Philosophy

This bot prioritizes risk safety:

1. **No Aggressive Stop Losses**: The bot avoids tight stop losses that get hit by normal market fluctuations
2. **Target-Based Profit Taking**: Takes profit when target is reached
3. **Hard Stop Protection**: Emergency exit only for extreme movements (10-15K USD moves)
4. **Conservative Leverage**: Default 3x leverage can be adjusted lower for more safety
5. **Position Sizing**: Automatically calculates position size to achieve profit targets

### Adjusting Profit Targets

If $150-200 per trade is unrealistic for your account size or market conditions, you can:

1. Lower `PROFIT_TARGET_USD` in `.env` (e.g., 50, 75, 100)
2. Reduce `LEVERAGE` (e.g., 2x instead of 3x)
3. The bot will automatically adjust position sizes accordingly

## Usage

### Simulation Mode (Recommended for Testing)

```bash
# Make sure ENABLE_SIMULATION=true in .env
python main.py
```

The bot will:
- Fetch real market data
- Analyze signals using real price data
- Simulate trades without placing real orders
- Track simulated P&L and positions

### Live Trading Mode

**WARNING**: Live trading involves real money. Test thoroughly in simulation mode first!

1. Set `ENABLE_SIMULATION=false` in `.env`
2. Provide valid Gate.io API keys
3. Start with small amounts
4. Monitor closely

```bash
python main.py
```

## How It Works

1. **Data Collection**: Fetches 1-hour candles for analysis (last 200 candles)

2. **Signal Detection**:
   - Detects EMA crossover (fast EMA crosses slow EMA)
   - Confirms with MACD (histogram and signal line alignment)
   - Confirms with volume (current volume > 20% above volume SMA)

3. **Trade Execution**:
   - Calculates position size to achieve profit target
   - Places market order
   - Sets take profit and hard stop loss levels

4. **Position Management**:
   - Monitors open positions
   - Closes when take profit is reached
   - Closes on hard stop loss trigger
   - Closes on reverse signal detection

5. **Risk Checks**:
   - Continuously monitors positions
   - Checks for hard stop loss conditions
   - Updates account balance

## Gate.io API Setup

1. Log in to Gate.io
2. Go to API Management
3. Create a new API key with futures trading permissions
4. For testing, use Gate.io testnet (set `GATE_SANDBOX=true`)
5. Copy API key and secret to `.env`

**Security Notes**:
- Never commit `.env` file to git
- Use read-only permissions if testing
- Enable IP whitelist if possible
- Start with small amounts

## Logs

Logs are saved to `logs/trading_bot_YYYYMMDD.log` for detailed debugging and analysis.

## Trading Strategy Details

### Entry Signals

**Long (Buy)**:
- Fast EMA crosses above slow EMA (bullish cross)
- MACD histogram is positive and increasing
- MACD line is above signal line
- Volume is at least 20% above volume SMA

**Short (Sell)**:
- Fast EMA crosses below slow EMA (bearish cross)
- MACD histogram is negative and decreasing
- MACD line is below signal line
- Volume is at least 20% above volume SMA

### Exit Signals

- **Take Profit**: Price reaches calculated target (based on profit goal)
- **Hard Stop Loss**: Extreme price movement against position (10-15K USD)
- **Reverse Signal**: Opposite signal appears (new EMA cross in opposite direction)

## Troubleshooting

### "Insufficient data" warnings
- The bot needs at least 50 candles for proper indicator calculation
- Wait for more data or check your internet connection

### API errors
- Verify API keys are correct
- Check API permissions (futures trading enabled)
- Ensure you're using the correct sandbox/mainnet endpoint

### Simulation mode not working
- The bot still needs internet connection to fetch market data
- Check your firewall/network settings

## Disclaimer

This trading bot is for educational purposes. Cryptocurrency trading involves significant risk. Always:

- Test thoroughly in simulation mode
- Start with small amounts
- Never trade more than you can afford to lose
- Understand the risks of leverage trading
- Monitor your positions regularly
- Use proper risk management

The authors are not responsible for any financial losses incurred from using this bot.

## License

MIT License - See LICENSE file for details

