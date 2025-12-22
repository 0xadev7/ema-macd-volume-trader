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
        
        # Detect EMA cross
        ema_signal = detect_ema_cross(df)
        
        if ema_signal is None:
            return None
        
        # Confirm with MACD
        macd_confirmed = confirm_with_macd(df, ema_signal)
        if not macd_confirmed:
            logger.debug("MACD does not confirm signal")
            return None
        
        # Confirm with volume
        volume_confirmed = confirm_with_volume(df, Config.VOLUME_THRESHOLD)
        if not volume_confirmed:
            logger.debug("Volume does not confirm signal")
            return None
        
        # Get current price
        current_price = float(df.iloc[-1]["close"])
        
        # Generate signal
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
        side = position["side"]
        position_size = abs(position["size"])
        
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

