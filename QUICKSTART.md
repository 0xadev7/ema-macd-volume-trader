# Quick Start Guide

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Set Up Environment

```bash
python setup_env.py
```

This creates a `.env` file with default values. Edit it to customize:

```env
ENABLE_SIMULATION=true  # Start with simulation mode!
PROFIT_TARGET_USD=150   # Adjust if $150 is too high
LEVERAGE=3              # Lower to 2 for more safety
```

## Step 3: Run in Simulation Mode

```bash
python main.py
```

The bot will:
- Fetch real BTC price data
- Analyze for trading signals
- Simulate trades (no real orders)
- Log all activity to console and `logs/` directory

## Step 4: Monitor and Adjust

Watch the logs to see:
- When signals are detected
- Position entries and exits
- P&L tracking
- Risk metrics

Adjust `PROFIT_TARGET_USD` if needed:
- If positions are too large → Lower the target
- If profits are too small → Raise the target (carefully!)

## Step 5: Test Thoroughly

Run in simulation for at least a few days/weeks to:
- Verify signal quality
- Check risk management
- Understand bot behavior
- Adjust parameters

## Step 6: Go Live (Optional)

**Only after thorough testing!**

1. Set `ENABLE_SIMULATION=false` in `.env`
2. Add real Gate.io API keys
3. Start with small `INITIAL_BALANCE` for testing
4. Monitor closely!

## Key Settings to Understand

- `PROFIT_TARGET_USD`: How much profit you want per trade
  - Lower = smaller positions, lower risk
  - Higher = larger positions, higher risk
  
- `LEVERAGE`: Trading leverage multiplier
  - Lower = safer, smaller profits
  - Higher = riskier, larger profits
  
- `HARD_STOP_LOSS_USD`: Emergency exit threshold
  - Only triggers on extreme moves (10K+ USD)
  - Protects against sudden crashes

## Troubleshooting

**Bot says "Insufficient data"**
- Normal at first, wait a few minutes
- Need at least 50 candles (50 hours of 1h data)

**No signals appearing**
- Normal! The bot is selective
- Requires EMA cross + MACD + Volume confirmation
- This reduces false signals

**Simulation not working**
- Need internet connection for price data
- Check firewall/network settings

## Need Help?

- Check the main README.md for detailed documentation
- Review logs in `logs/` directory
- Start with lower profit targets and leverage

