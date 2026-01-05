"""EMA-MACD-Volume trading strategy."""
from typing import Optional, Dict, List
import pandas as pd
from utils.logger import setup_logger
from config import Config
from indicators.technical_indicators import (
    prepare_data,
    calculate_indicators,
    detect_ema_cross,
    confirm_with_macd,
    confirm_with_volume,
)
from risk.risk_manager import RiskManager
from exchange.gateio_client import GateIOClient

logger = setup_logger(__name__)


class EMAMACDVolumeStrategy:
    """Trading strategy using EMA cross, MACD, and volume confirmation."""
    
    def __init__(
        self,
        exchange_client: GateIOClient,
        risk_manager: RiskManager,
        symbol: str = "BTC_USDT",
    ):
        """Initialize strategy.
        
        Args:
            exchange_client: Exchange client instance
            risk_manager: Risk manager instance
            symbol: Trading pair symbol
        """
        self.client = exchange_client
        self.risk_manager = risk_manager
        self.symbol = symbol
        self.current_position = None
        
    def analyze(self, candles: List[Dict]) -> Optional[Dict]:
        """Analyze market and generate trading signal.
        
        Args:
            candles: List of candle dictionaries
            
        Returns:
            Signal dictionary with 'action', 'side', 'confidence', or None
        """
        if len(candles) < 50:  # Need enough data for indicators
            logger.warning(f"Insufficient data: {len(candles)} candles")
            return None
        
        # Prepare and calculate indicators
        df = prepare_data(candles)
        df = calculate_indicators(
            df,
            ema_fast=Config.EMA_FAST,
            ema_slow=Config.EMA_SLOW,
            macd_fast=Config.MACD_FAST,
            macd_slow=Config.MACD_SLOW,
            macd_signal=Config.MACD_SIGNAL,
        )
        
        if df.empty or len(df) < 2:
            return None
        
        # Get current and previous values for logging
        current = df.iloc[-1]
        previous = df.iloc[-2] if len(df) >= 2 else current
        
        # Extract indicator values
        current_price = float(current["close"])
        ema_fast_current = float(current["ema_fast"]) if pd.notna(current["ema_fast"]) else None
        ema_slow_current = float(current["ema_slow"]) if pd.notna(current["ema_slow"]) else None
        ema_fast_previous = float(previous["ema_fast"]) if pd.notna(previous["ema_fast"]) else None
        ema_slow_previous = float(previous["ema_slow"]) if pd.notna(previous["ema_slow"]) else None
        
        macd_current = float(current["macd"]) if pd.notna(current["macd"]) else None
        macd_signal_current = float(current["macd_signal"]) if pd.notna(current["macd_signal"]) else None
        macd_histogram_current = float(current["macd_histogram"]) if pd.notna(current["macd_histogram"]) else None
        macd_histogram_previous = float(previous["macd_histogram"]) if pd.notna(previous["macd_histogram"]) else None
        
        volume_current = float(current["volume"]) if pd.notna(current["volume"]) else None
        volume_sma_current = float(current["volume_sma"]) if pd.notna(current["volume_sma"]) else None
        
        # Log indicator values
        logger.info("=" * 80)
        logger.info("MARKET ANALYSIS")
        logger.info("=" * 80)
        logger.info(f"Price: ${current_price:,.2f}")
        logger.info(f"Candles analyzed: {len(df)}")
        logger.info("")
        logger.info("EMA Indicators:")
        logger.info(f"  EMA Fast ({Config.EMA_FAST}): ${ema_fast_current:,.2f}" if ema_fast_current else "  EMA Fast: N/A")
        logger.info(f"  EMA Slow ({Config.EMA_SLOW}): ${ema_slow_current:,.2f}" if ema_slow_current else "  EMA Slow: N/A")
        if ema_fast_current and ema_slow_current:
            ema_diff = ema_fast_current - ema_slow_current
            ema_status = "Fast ABOVE Slow" if ema_diff > 0 else "Fast BELOW Slow"
            logger.info(f"  EMA Status: {ema_status} (diff: ${abs(ema_diff):,.2f})")
        logger.info("")
        logger.info("MACD Indicators:")
        logger.info(f"  MACD Line: {macd_current:,.2f}" if macd_current is not None else "  MACD Line: N/A")
        logger.info(f"  Signal Line: {macd_signal_current:,.2f}" if macd_signal_current is not None else "  Signal Line: N/A")
        logger.info(f"  Histogram (Current): {macd_histogram_current:,.2f}" if macd_histogram_current is not None else "  Histogram: N/A")
        logger.info(f"  Histogram (Previous): {macd_histogram_previous:,.2f}" if macd_histogram_previous is not None else "  Histogram Previous: N/A")
        if macd_current is not None and macd_signal_current is not None:
            macd_status = "MACD ABOVE Signal" if macd_current > macd_signal_current else "MACD BELOW Signal"
            logger.info(f"  MACD Status: {macd_status}")
        if macd_histogram_current is not None and macd_histogram_previous is not None:
            histogram_trend = "INCREASING" if macd_histogram_current > macd_histogram_previous else "DECREASING"
            logger.info(f"  Histogram Trend: {histogram_trend}")
        logger.info("")
        logger.info("Volume Indicators:")
        logger.info(f"  Current Volume: {volume_current:,.2f}" if volume_current else "  Current Volume: N/A")
        logger.info(f"  Volume SMA (20): {volume_sma_current:,.2f}" if volume_sma_current else "  Volume SMA: N/A")
        if volume_current and volume_sma_current:
            volume_ratio = volume_current / volume_sma_current if volume_sma_current > 0 else 0
            volume_threshold_met = volume_ratio >= Config.VOLUME_THRESHOLD
            logger.info(f"  Volume Ratio: {volume_ratio:.2f}x (threshold: {Config.VOLUME_THRESHOLD}x)")
            logger.info(f"  Volume Status: {'ABOVE threshold' if volume_threshold_met else 'BELOW threshold'}")
        logger.info("")
        
        # Detect EMA cross
        ema_signal = detect_ema_cross(df)
        
        if ema_signal is None:
            logger.info("Signal Check: ❌ NO EMA CROSS detected")
            logger.info("=" * 80)
            return None
        
        logger.info(f"Signal Check: ✅ EMA CROSS detected ({ema_signal.upper()})")
        
        # Confirm with MACD
        macd_confirmed = confirm_with_macd(df, ema_signal)
        if not macd_confirmed:
            logger.info("Signal Check: ❌ MACD does NOT confirm signal")
            # Explain why MACD failed
            if ema_signal == "bullish":
                required_conditions = []
                if macd_histogram_current is not None and macd_histogram_current <= 0:
                    required_conditions.append(f"Histogram must be > 0 (currently: {macd_histogram_current:,.2f})")
                if macd_histogram_current is not None and macd_histogram_previous is not None and macd_histogram_current <= macd_histogram_previous:
                    required_conditions.append(f"Histogram must be increasing (current: {macd_histogram_current:,.2f}, previous: {macd_histogram_previous:,.2f})")
                if macd_current is not None and macd_signal_current is not None and macd_current <= macd_signal_current:
                    required_conditions.append(f"MACD must be > Signal (MACD: {macd_current:,.2f}, Signal: {macd_signal_current:,.2f})")
                if required_conditions:
                    logger.info(f"  Reasons: {'; '.join(required_conditions)}")
            else:  # bearish
                required_conditions = []
                if macd_histogram_current is not None and macd_histogram_current >= 0:
                    required_conditions.append(f"Histogram must be < 0 (currently: {macd_histogram_current:,.2f})")
                if macd_histogram_current is not None and macd_histogram_previous is not None and macd_histogram_current >= macd_histogram_previous:
                    required_conditions.append(f"Histogram must be decreasing (current: {macd_histogram_current:,.2f}, previous: {macd_histogram_previous:,.2f})")
                if macd_current is not None and macd_signal_current is not None and macd_current >= macd_signal_current:
                    required_conditions.append(f"MACD must be < Signal (MACD: {macd_current:,.2f}, Signal: {macd_signal_current:,.2f})")
                if required_conditions:
                    logger.info(f"  Reasons: {'; '.join(required_conditions)}")
            logger.info("=" * 80)
            return None
        
        logger.info("Signal Check: ✅ MACD confirms signal")
        
        # Confirm with volume
        volume_confirmed = confirm_with_volume(df, Config.VOLUME_THRESHOLD)
        if not volume_confirmed:
            logger.info("Signal Check: ❌ Volume does NOT confirm signal")
            if volume_current and volume_sma_current:
                volume_ratio = volume_current / volume_sma_current if volume_sma_current > 0 else 0
                logger.info(
                    f"  Reason: Volume ratio ({volume_ratio:.2f}x) is below threshold ({Config.VOLUME_THRESHOLD}x)"
                )
                logger.info(
                    f"  Current volume: {volume_current:,.2f}, Required: {volume_sma_current * Config.VOLUME_THRESHOLD:,.2f}"
                )
            logger.info("=" * 80)
            return None
        
        logger.info("Signal Check: ✅ Volume confirms signal")
        logger.info("=" * 80)
        
        # Generate signal (current_price already extracted above)
        signal = {
            "action": "buy" if ema_signal == "bullish" else "sell",
            "side": "buy" if ema_signal == "bullish" else "sell",
            "price": current_price,
            "confidence": "high" if macd_confirmed and volume_confirmed else "medium",
            "timestamp": df.index[-1],
        }
        
        logger.info(
            f"Signal generated: {signal['action'].upper()} @ {current_price:.2f} "
            f"(EMA: {ema_signal}, MACD: confirmed, Volume: confirmed)"
        )
        
        return signal
    
    def should_close_position(
        self,
        position: Dict,
        current_price: float,
        candles: List[Dict],
    ) -> Optional[Dict]:
        """Check if position should be closed.
        
        Args:
            position: Current position dictionary
            current_price: Current market price
            candles: List of candle dictionaries
            
        Returns:
            Close signal dictionary or None
        """
        entry_price = position.get("entry_price", 0)
        position_size = abs(position.get("size", 0))
        side = "buy" if position.get("size", 0) > 0 else "sell"
        
        if position_size == 0:
            return None
        
        # Get risk metrics
        metrics = self.risk_manager.get_risk_metrics(
            entry_price, current_price, side, position_size
        )
        
        # Check hard stop loss
        if self.risk_manager.check_hard_stop_loss(
            entry_price, current_price, side, position_size
        ):
            return {
                "action": "close",
                "reason": "hard_stop_loss",
                "current_price": current_price,
                "metrics": metrics,
            }
        
        # Check take profit
        tp_price = metrics["tp_price"]
        if side == "buy" and current_price >= tp_price:
            return {
                "action": "close",
                "reason": "take_profit",
                "current_price": current_price,
                "metrics": metrics,
            }
        elif side == "sell" and current_price <= tp_price:
            return {
                "action": "close",
                "reason": "take_profit",
                "current_price": current_price,
                "metrics": metrics,
            }
        
        # Check for reverse signal (exit if opposite signal appears)
        signal = self.analyze(candles)
        if signal and signal["side"] != side:
            # Strong reverse signal - consider closing
            logger.info(f"Reverse signal detected, considering closing position")
            return {
                "action": "close",
                "reason": "reverse_signal",
                "current_price": current_price,
                "metrics": metrics,
            }
        
        return None
    
    def execute_trade(self, signal: Dict) -> Optional[Dict]:
        """Execute a trade based on signal.
        
        Args:
            signal: Trading signal dictionary
            
        Returns:
            Order result dictionary or None
        """
        action = signal["action"]
        price = signal["price"]
        
        # Calculate position size
        account = self.client.get_account()
        current_balance = account.get("available", Config.INITIAL_BALANCE)
        self.risk_manager.update_balance(current_balance)
        
        position_size = self.risk_manager.calculate_position_size(price, current_balance)
        
        if position_size <= 0:
            logger.warning("Position size is zero, cannot execute trade")
            return None
        
        # Place order
        try:
            order = self.client.place_order(
                symbol=self.symbol,
                side=action,
                size=position_size,
                price=None,  # Market order
                order_type="market",
            )
            
            if order:
                logger.info(
                    f"Order executed: {action.upper()} {position_size:.6f} {self.symbol} @ {price:.2f}"
                )
                
                # Store position info
                self.current_position = {
                    "entry_price": price,
                    "size": position_size if action == "buy" else -position_size,
                    "side": action,
                    "order_id": order.get("id"),
                    "tp_price": self.risk_manager.calculate_take_profit_price(
                        price, action, position_size
                    ),
                    "sl_price": self.risk_manager.calculate_hard_stop_loss_price(
                        price, action, position_size
                    ),
                }
            
            return order
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return None
    
    def close_position(self, close_signal: Dict) -> Optional[Dict]:
        """Close current position.
        
        Args:
            close_signal: Close signal dictionary
            
        Returns:
            Order result dictionary or None
        """
        if not self.current_position:
            return None
        
        position = self.current_position
        # Determine side from position size (positive = long/buy, negative = short/sell)
        position_size = abs(position.get("size", 0))
        side = "buy" if position.get("size", 0) > 0 else "sell"
        
        # Close with opposite side
        close_side = "sell" if side == "buy" else "buy"
        
        try:
            order = self.client.place_order(
                symbol=self.symbol,
                side=close_side,
                size=position_size,
                price=None,
                order_type="market",
            )
            
            if order:
                entry_price = position["entry_price"]
                exit_price = close_signal["current_price"]
                pnl = (exit_price - entry_price) * position_size * Config.LEVERAGE
                if side == "sell":
                    pnl = -pnl
                
                logger.info(
                    f"Position closed: {close_signal['reason']} | "
                    f"Entry: {entry_price:.2f}, Exit: {exit_price:.2f}, P&L: ${pnl:.2f}"
                )
                
                self.current_position = None
            
            return order
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None

