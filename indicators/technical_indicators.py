"""Technical indicators implementation."""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average.
    
    Args:
        prices: Series of prices
        period: EMA period
        
    Returns:
        Series of EMA values
    """
    return prices.ewm(span=period, adjust=False).mean()


def calculate_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Dict[str, pd.Series]:
    """Calculate MACD indicator.
    
    Args:
        prices: Series of prices
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line EMA period
        
    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' series
    """
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def calculate_volume_sma(volumes: pd.Series, period: int = 20) -> pd.Series:
    """Calculate Simple Moving Average of volume.
    
    Args:
        volumes: Series of volumes
        period: SMA period
        
    Returns:
        Series of volume SMA values
    """
    return volumes.rolling(window=period).mean()


def prepare_data(candles: List[Dict]) -> pd.DataFrame:
    """Convert candle data to pandas DataFrame.
    
    Args:
        candles: List of candle dictionaries
        
    Returns:
        DataFrame with OHLCV data
    """
    if not candles:
        return pd.DataFrame()
    
    df = pd.DataFrame(candles)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    
    return df


def calculate_indicators(
    df: pd.DataFrame,
    ema_fast: int = 12,
    ema_slow: int = 26,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    volume_sma_period: int = 20,
) -> pd.DataFrame:
    """Calculate all technical indicators.
    
    Args:
        df: DataFrame with OHLCV data
        ema_fast: Fast EMA period
        ema_slow: Slow EMA period
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period
        volume_sma_period: Volume SMA period
        
    Returns:
        DataFrame with added indicator columns
    """
    if df.empty:
        return df
    
    # Calculate EMAs
    df["ema_fast"] = calculate_ema(df["close"], ema_fast)
    df["ema_slow"] = calculate_ema(df["close"], ema_slow)
    
    # Calculate MACD
    macd_data = calculate_macd(
        df["close"],
        fast_period=macd_fast,
        slow_period=macd_slow,
        signal_period=macd_signal,
    )
    df["macd"] = macd_data["macd"]
    df["macd_signal"] = macd_data["signal"]
    df["macd_histogram"] = macd_data["histogram"]
    
    # Calculate volume SMA
    df["volume_sma"] = calculate_volume_sma(df["volume"], volume_sma_period)
    
    return df


def detect_ema_cross(df: pd.DataFrame) -> Optional[str]:
    """Detect EMA crossover signal.
    
    Args:
        df: DataFrame with EMA columns
        
    Returns:
        "bullish" if fast EMA crosses above slow EMA,
        "bearish" if fast EMA crosses below slow EMA,
        None otherwise
    """
    if len(df) < 2:
        return None
    
    current = df.iloc[-1]
    previous = df.iloc[-2]
    
    # Bullish cross: fast EMA crosses above slow EMA
    if (
        previous["ema_fast"] <= previous["ema_slow"]
        and current["ema_fast"] > current["ema_slow"]
    ):
        return "bullish"
    
    # Bearish cross: fast EMA crosses below slow EMA
    if (
        previous["ema_fast"] >= previous["ema_slow"]
        and current["ema_fast"] < current["ema_slow"]
    ):
        return "bearish"
    
    return None


def confirm_with_macd(df: pd.DataFrame, signal_type: str) -> bool:
    """Confirm signal with MACD.
    
    Args:
        df: DataFrame with MACD columns
        signal_type: "bullish" or "bearish"
        
    Returns:
        True if MACD confirms the signal
    """
    if len(df) < 2:
        return False
    
    current = df.iloc[-1]
    previous = df.iloc[-2]
    
    if signal_type == "bullish":
        # MACD confirms bullish: histogram is positive and increasing
        return (
            current["macd_histogram"] > 0
            and current["macd_histogram"] > previous["macd_histogram"]
            and current["macd"] > current["macd_signal"]
        )
    
    elif signal_type == "bearish":
        # MACD confirms bearish: histogram is negative and decreasing
        return (
            current["macd_histogram"] < 0
            and current["macd_histogram"] < previous["macd_histogram"]
            and current["macd"] < current["macd_signal"]
        )
    
    return False


def confirm_with_volume(df: pd.DataFrame, volume_threshold: float = 1.2) -> bool:
    """Confirm signal with volume.
    
    Args:
        df: DataFrame with volume columns
        volume_threshold: Minimum volume increase ratio (default 1.2 = 20% increase)
        
    Returns:
        True if volume is above threshold
    """
    if len(df) == 0:
        return False
    
    current = df.iloc[-1]
    
    if "volume_sma" not in df.columns or pd.isna(current["volume_sma"]):
        return False
    
    # Volume should be above SMA (indicating increased interest)
    return current["volume"] >= current["volume_sma"] * volume_threshold

