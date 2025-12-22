"""Main trading bot runner."""
import time
import sys
from typing import Optional
from utils.logger import setup_logger
from config import Config
from exchange.gateio_client import GateIOClient
from strategy.ema_macd_volume_strategy import EMAMACDVolumeStrategy
from risk.risk_manager import RiskManager

logger = setup_logger(__name__)


class TradingBot:
    """Main trading bot."""
    
    def __init__(self):
        """Initialize trading bot."""
        # Validate configuration
        try:
            Config.validate()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)
        
        # Initialize components
        self.client = GateIOClient(simulation_mode=Config.ENABLE_SIMULATION)
        self.risk_manager = RiskManager(
            initial_balance=Config.INITIAL_BALANCE,
            leverage=Config.LEVERAGE,
            profit_target_usd=Config.PROFIT_TARGET_USD,
            hard_stop_loss_usd=Config.HARD_STOP_LOSS_USD,
        )
        self.strategy = EMAMACDVolumeStrategy(
            exchange_client=self.client,
            risk_manager=self.risk_manager,
            symbol=Config.SYMBOL,
        )
        
        logger.info("=" * 60)
        logger.info("Trading Bot Initialized")
        logger.info("=" * 60)
        logger.info(f"Mode: {'SIMULATION' if Config.ENABLE_SIMULATION else 'LIVE'}")
        logger.info(f"Symbol: {Config.SYMBOL}")
        logger.info(f"Initial Balance: ${Config.INITIAL_BALANCE:,.2f}")
        logger.info(f"Leverage: {Config.LEVERAGE}x")
        logger.info(f"Profit Target: ${Config.PROFIT_TARGET_USD:.2f} per trade")
        logger.info(f"Hard Stop Loss: ${Config.HARD_STOP_LOSS_USD:.2f}")
        logger.info("=" * 60)
    
    def get_current_price(self) -> Optional[float]:
        """Get current market price."""
        ticker = self.client.get_ticker(Config.SYMBOL)
        if ticker:
            return ticker.get("last") or ticker.get("mark_price")
        
        # Fallback: get from latest candle
        candles = self.client.get_candles(Config.SYMBOL, interval="1h", limit=1)
        if candles:
            return candles[-1]["close"]
        
        return None
    
    def run(self, check_interval: int = 300):
        """Run the trading bot.
        
        Args:
            check_interval: Time in seconds between market checks
        """
        logger.info("Starting trading bot...")
        
        try:
            while True:
                try:
                    # Update account balance
                    account = self.client.get_account()
                    current_balance = account.get("total", Config.INITIAL_BALANCE)
                    self.risk_manager.update_balance(current_balance)
                    
                    # Get current positions
                    positions = self.client.get_positions(Config.SYMBOL)
                    
                    # Get current price
                    current_price = self.get_current_price()
                    if not current_price:
                        logger.warning("Could not get current price, will try to get from candles")
                        # Try to get price from latest candle as fallback
                        if candles and len(candles) > 0:
                            current_price = candles[-1].get("close")
                            if current_price:
                                logger.info(f"Using price from latest candle: ${current_price:,.2f}")
                        if not current_price:
                            logger.warning("No price available, skipping this cycle")
                            time.sleep(check_interval)
                            continue
                    
                    # Get historical candles for analysis
                    candles = self.client.get_candles(
                        Config.SYMBOL,
                        interval="1h",  # 1 hour candles
                        limit=200,
                    )
                    
                    if not candles:
                        logger.warning("Could not get candle data, skipping this cycle")
                        time.sleep(check_interval)
                        continue
                    
                    # Check if we have an open position
                    if positions and len(positions) > 0:
                        position = positions[0]
                        self.strategy.current_position = position
                        
                        # Check if position should be closed
                        close_signal = self.strategy.should_close_position(
                            position, current_price, candles
                        )
                        
                        if close_signal:
                            logger.info(f"Closing position: {close_signal['reason']}")
                            self.strategy.close_position(close_signal)
                    else:
                        # No position, look for entry signals
                        signal = self.strategy.analyze(candles)
                        
                        if signal:
                            logger.info(
                                f"Trading signal detected: {signal['action'].upper()} @ {signal['price']:.2f}"
                            )
                            
                            # Execute trade
                            result = self.strategy.execute_trade(signal)
                            
                            if result:
                                logger.info("Trade executed successfully")
                            else:
                                logger.warning("Trade execution failed")
                        else:
                            logger.debug("No trading signal at this time")
                    
                    # Log current status
                    logger.info(
                        f"Balance: ${current_balance:,.2f} | "
                        f"Price: ${current_price:,.2f} | "
                        f"Positions: {len(positions)}"
                    )
                    
                except KeyboardInterrupt:
                    logger.info("Bot stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Error in trading loop: {e}", exc_info=True)
                
                # Wait before next check
                logger.info(f"Waiting {check_interval} seconds before next check...")
                time.sleep(check_interval)
        
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    bot = TradingBot()
    bot.run(check_interval=300)  # Check every 5 minutes


if __name__ == "__main__":
    main()

