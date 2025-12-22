"""Risk management for trading."""
from typing import Optional, Dict
from utils.logger import setup_logger
from config import Config

logger = setup_logger(__name__)


class RiskManager:
    """Manages trading risk and position sizing."""
    
    def __init__(
        self,
        initial_balance: float,
        leverage: int,
        profit_target_usd: float,
        hard_stop_loss_usd: float,
    ):
        """Initialize risk manager.
        
        Args:
            initial_balance: Initial account balance
            leverage: Trading leverage
            profit_target_usd: Target profit per trade in USD
            hard_stop_loss_usd: Hard stop loss in USD for emergency exits
        """
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.profit_target_usd = profit_target_usd
        self.hard_stop_loss_usd = hard_stop_loss_usd
        self.current_balance = initial_balance
        
    def calculate_position_size(
        self,
        entry_price: float,
        current_balance: Optional[float] = None,
    ) -> float:
        """Calculate position size based on profit target.
        
        The position size is calculated to achieve the profit target
        with the given leverage.
        
        Args:
            entry_price: Entry price for the trade
            current_balance: Current account balance (defaults to initial)
            
        Returns:
            Position size in BTC
        """
        if current_balance is None:
            current_balance = self.current_balance
        
        # Calculate the price movement needed to achieve profit target
        # With leverage: profit = price_change * position_size * leverage
        # We want: profit_target = price_change_pct * entry_price * position_size * leverage
        # For a 1% price movement: profit = 0.01 * entry_price * position_size * leverage
        # So: position_size = profit_target / (0.01 * entry_price * leverage)
        
        # Targeting around 1-2% price movement for profit
        # This gives us: position_size = profit_target / (price_movement_pct * entry_price * leverage)
        target_price_movement_pct = 0.015  # 1.5% target movement
        
        # Calculate position size to achieve profit target
        position_size = self.profit_target_usd / (
            target_price_movement_pct * entry_price * self.leverage
        )
        
        # Ensure we don't use more than 80% of available balance
        max_position_value = current_balance * 0.8 * self.leverage
        max_position_size = max_position_value / entry_price
        
        position_size = min(position_size, max_position_size)
        
        logger.debug(
            f"Calculated position size: {position_size:.6f} BTC "
            f"(target profit: ${self.profit_target_usd:.2f})"
        )
        
        return position_size
    
    def calculate_take_profit_price(
        self,
        entry_price: float,
        side: str,
        position_size: float,
    ) -> float:
        """Calculate take profit price to achieve target profit.
        
        Args:
            entry_price: Entry price
            side: "buy" or "sell"
            position_size: Position size in BTC
            
        Returns:
            Take profit price
        """
        if position_size == 0:
            return entry_price
        
        # Calculate required price movement
        required_profit_per_btc = self.profit_target_usd / position_size / self.leverage
        
        if side == "buy":
            # For long: profit when price goes up
            tp_price = entry_price + required_profit_per_btc
        else:
            # For short: profit when price goes down
            tp_price = entry_price - required_profit_per_btc
        
        return tp_price
    
    def calculate_hard_stop_loss_price(
        self,
        entry_price: float,
        side: str,
        position_size: float,
    ) -> float:
        """Calculate hard stop loss price for emergency exit.
        
        Args:
            entry_price: Entry price
            side: "buy" or "sell"
            position_size: Position size in BTC
            
        Returns:
            Hard stop loss price
        """
        if position_size == 0:
            return entry_price
        
        # Calculate price movement that would cause hard stop loss loss
        loss_per_btc = self.hard_stop_loss_usd / position_size / self.leverage
        
        if side == "buy":
            # For long: loss when price goes down
            sl_price = entry_price - loss_per_btc
        else:
            # For short: loss when price goes up
            sl_price = entry_price + loss_per_btc
        
        return sl_price
    
    def check_hard_stop_loss(
        self,
        entry_price: float,
        current_price: float,
        side: str,
        position_size: float,
    ) -> bool:
        """Check if hard stop loss should be triggered.
        
        Args:
            entry_price: Entry price
            current_price: Current market price
            side: "buy" or "sell"
            position_size: Position size in BTC
            
        Returns:
            True if hard stop loss should be triggered
        """
        sl_price = self.calculate_hard_stop_loss_price(entry_price, side, position_size)
        
        if side == "buy":
            # Long position: trigger if price drops below SL
            triggered = current_price <= sl_price
        else:
            # Short position: trigger if price rises above SL
            triggered = current_price >= sl_price
        
        if triggered:
            logger.warning(
                f"Hard stop loss triggered! Entry: {entry_price}, Current: {current_price}, "
                f"SL Price: {sl_price:.2f}"
            )
        
        return triggered
    
    def update_balance(self, new_balance: float):
        """Update current balance."""
        self.current_balance = new_balance
    
    def get_risk_metrics(
        self,
        entry_price: float,
        current_price: float,
        side: str,
        position_size: float,
    ) -> Dict:
        """Get current risk metrics for a position.
        
        Args:
            entry_price: Entry price
            current_price: Current market price
            side: "buy" or "sell"
            position_size: Position size in BTC
            
        Returns:
            Dictionary with risk metrics
        """
        tp_price = self.calculate_take_profit_price(entry_price, side, position_size)
        sl_price = self.calculate_hard_stop_loss_price(entry_price, side, position_size)
        
        # Calculate current P&L
        price_diff = (current_price - entry_price) if side == "buy" else (entry_price - current_price)
        unrealized_pnl = price_diff * position_size * self.leverage
        
        # Calculate P&L percentages
        position_value = entry_price * position_size
        pnl_pct = (unrealized_pnl / position_value) * 100 if position_value > 0 else 0
        
        return {
            "entry_price": entry_price,
            "current_price": current_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "unrealized_pnl": unrealized_pnl,
            "pnl_pct": pnl_pct,
            "price_to_tp": abs(current_price - tp_price),
            "price_to_sl": abs(current_price - sl_price),
        }

