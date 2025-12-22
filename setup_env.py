"""Helper script to create .env file from template."""
import os
import shutil

def setup_env():
    """Create .env file from example if it doesn't exist."""
    if os.path.exists(".env"):
        print(".env file already exists. Skipping setup.")
        return
    
    if os.path.exists(".env.example"):
        shutil.copy(".env.example", ".env")
        print(".env file created from .env.example")
        print("Please edit .env with your configuration before running the bot.")
    else:
        # Create basic .env file
        env_content = """# Gate.io API Credentials (required for live trading, optional for simulation)
GATE_API_KEY=your_api_key_here
GATE_API_SECRET=your_api_secret_here
GATE_SANDBOX=true

# Trading Configuration
INITIAL_BALANCE=10000
LEVERAGE=3
SYMBOL=BTC_USDT
PROFIT_TARGET_USD=150

# Risk Management
HARD_STOP_LOSS_USD=10000
ENABLE_SIMULATION=true

# Technical Indicators
EMA_FAST=12
EMA_SLOW=26
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
"""
        with open(".env", "w") as f:
            f.write(env_content)
        print(".env file created with default values.")
        print("Please edit .env with your configuration before running the bot.")

if __name__ == "__main__":
    setup_env()

