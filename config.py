"""Configuration management for the trading bot."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # Gate.io API
    GATE_API_KEY = os.getenv("GATE_API_KEY", "")
    GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
    GATE_SANDBOX = os.getenv("GATE_SANDBOX", "true").lower() == "true"
    
    # Trading Configuration
    INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "10000"))
    LEVERAGE = int(os.getenv("LEVERAGE", "3"))
    SYMBOL = os.getenv("SYMBOL", "BTC_USDT")
    PROFIT_TARGET_USD = float(os.getenv("PROFIT_TARGET_USD", "150"))
    
    # Risk Management
    HARD_STOP_LOSS_USD = float(os.getenv("HARD_STOP_LOSS_USD", "10000"))
    ENABLE_SIMULATION = os.getenv("ENABLE_SIMULATION", "true").lower() == "true"
    
    # Technical Indicators
    EMA_FAST = int(os.getenv("EMA_FAST", "12"))
    EMA_SLOW = int(os.getenv("EMA_SLOW", "26"))
    MACD_FAST = int(os.getenv("MACD_FAST", "12"))
    MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
    MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))
    
    # Volume confirmation (minimum volume increase percentage)
    VOLUME_THRESHOLD = 1.2  # 20% increase in volume
    
    @classmethod
    def validate(cls):
        """Validate configuration."""
        if not cls.ENABLE_SIMULATION and (not cls.GATE_API_KEY or not cls.GATE_API_SECRET):
            raise ValueError("API keys are required when simulation is disabled")
        
        if cls.LEVERAGE < 1 or cls.LEVERAGE > 125:
            raise ValueError("Leverage must be between 1 and 125")
        
        if cls.INITIAL_BALANCE <= 0:
            raise ValueError("Initial balance must be positive")
        
        return True

