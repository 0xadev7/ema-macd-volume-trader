"""Gate.io API client for futures trading."""
from typing import Optional, Dict, List
import time
import csv
import os
from datetime import datetime
import requests
from gate_api import ApiClient, Configuration, FuturesApi, FuturesOrder, FuturesAccount
from gate_api.rest import ApiException
from utils.logger import setup_logger
from config import Config

logger = setup_logger(__name__)


class GateIOClient:
    """Gate.io futures trading client."""
    
    def __init__(self, simulation_mode: bool = True):
        """Initialize Gate.io client.
        
        Args:
            simulation_mode: If True, simulates trades without real API calls
        """
        self.simulation_mode = simulation_mode
        self.config = None
        self.api = None
        
        if not simulation_mode:
            # Initialize real API client
            self.config = Configuration(
                key=Config.GATE_API_KEY,
                secret=Config.GATE_API_SECRET,
                host="https://api.gateio.ws/api/v4" if not Config.GATE_SANDBOX else "https://fx-api-testnet.gateio.ws/api/v4"
            )
            self.api = FuturesApi(ApiClient(self.config))
        
        # Simulation state
        self._sim_balance = Config.INITIAL_BALANCE
        self._sim_positions = {}
        self._sim_trades = []
        self._sim_realized_pnl = 0.0
        self._last_price_cache = {}  # Cache last known prices for fallback
        
        # CSV logging for simulation mode
        if self.simulation_mode:
            self._csv_file_path = self._init_csv_log()
    
    def _init_csv_log(self) -> str:
        """Initialize CSV log file for simulation orders.
        
        Returns:
            Path to the CSV log file
        """
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Create CSV file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file_path = f"data/simulation_orders_{timestamp}.csv"
        
        # Write header
        headers = [
            "timestamp",
            "order_id",
            "symbol",
            "side",
            "size",
            "price",
            "order_type",
            "position_size_before",
            "position_size_after",
            "entry_price",
            "exit_price",
            "realized_pnl",
            "balance_before",
            "balance_after",
            "leverage",
            "trade_type",  # "open", "close", "partial"
            "notes"
        ]
        
        with open(csv_file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        
        logger.info(f"CSV log initialized: {csv_file_path}")
        return csv_file_path
    
    def _log_order_to_csv(
        self,
        order_id: str,
        symbol: str,
        side: str,
        size: float,
        price: float,
        order_type: str,
        position_size_before: float,
        position_size_after: float,
        entry_price: float = 0.0,
        exit_price: float = 0.0,
        realized_pnl: float = 0.0,
        balance_before: float = 0.0,
        balance_after: float = 0.0,
        trade_type: str = "open",
        notes: str = "",
    ):
        """Log order to CSV file.
        
        Args:
            order_id: Order ID
            symbol: Trading pair symbol
            side: "buy" or "sell"
            size: Order size
            price: Execution price
            order_type: Order type (market/limit)
            position_size_before: Position size before this order
            position_size_after: Position size after this order
            entry_price: Entry price for the position
            exit_price: Exit price (if closing)
            realized_pnl: Realized P&L (if closing)
            balance_before: Account balance before order
            balance_after: Account balance after order
            trade_type: Type of trade ("open", "close", "partial")
            notes: Additional notes
        """
        if not self.simulation_mode:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        row = [
            timestamp,
            order_id,
            symbol,
            side.upper(),
            f"{size:.8f}",
            f"{price:.2f}",
            order_type,
            f"{position_size_before:.8f}",
            f"{position_size_after:.8f}",
            f"{entry_price:.2f}" if entry_price > 0 else "",
            f"{exit_price:.2f}" if exit_price > 0 else "",
            f"{realized_pnl:.2f}" if realized_pnl != 0 else "",
            f"{balance_before:.2f}",
            f"{balance_after:.2f}",
            str(Config.LEVERAGE),
            trade_type,
            notes,
        ]
        
        try:
            with open(self._csv_file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            logger.error(f"Error writing to CSV log: {e}")
        
    def get_account(self) -> Dict:
        """Get futures account balance.
        
        Returns:
            Account information dictionary
        """
        if self.simulation_mode:
            # Calculate unrealized P&L from open positions
            unrealized_pnl = 0.0
            for symbol, pos in self._sim_positions.items():
                if pos["size"] != 0:
                    entry_price = pos["entry_price"]
                    current_price = pos["mark_price"]
                    position_size = abs(pos["size"])
                    pnl = (current_price - entry_price) * position_size * Config.LEVERAGE
                    if pos["size"] < 0:  # Short position
                        pnl = -pnl
                    unrealized_pnl += pnl
            
            return {
                "total": self._sim_balance + unrealized_pnl,
                "available": self._sim_balance,
                "unrealised_pnl": unrealized_pnl,
                "position_margin": 0.0,
                "order_margin": 0.0,
            }
        
        try:
            account = self.api.list_futures_accounts()
            if account:
                return {
                    "total": float(account.total),
                    "available": float(account.available),
                    "unrealised_pnl": float(account.unrealised_pnl or 0),
                    "position_margin": float(account.position_margin or 0),
                    "order_margin": float(account.order_margin or 0),
                }
        except ApiException as e:
            logger.error(f"Error getting account: {e}")
            raise
        
        return {}
    
    def get_positions(self, symbol: str = None) -> List[Dict]:
        """Get open positions.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC_USDT). If None, returns all positions.
            
        Returns:
            List of position dictionaries
        """
        if self.simulation_mode:
            positions = []
            # Update mark prices for simulation positions
            if symbol and symbol in self._sim_positions:
                pos = self._sim_positions[symbol]
                ticker = self.get_ticker(symbol)
                if ticker:
                    pos["mark_price"] = ticker.get("last") or ticker.get("mark_price", pos.get("mark_price", 0))
                    # Calculate unrealized P&L
                    if pos["size"] != 0:
                        entry_price = pos["entry_price"]
                        current_price = pos["mark_price"]
                        position_size = abs(pos["size"])
                        pnl = (current_price - entry_price) * position_size * Config.LEVERAGE
                        if pos["size"] < 0:  # Short position
                            pnl = -pnl
                        pos["unrealised_pnl"] = pnl
                positions.append(pos.copy())
            elif not symbol:
                for sym, pos in self._sim_positions.items():
                    ticker = self.get_ticker(sym)
                    if ticker:
                        pos["mark_price"] = ticker.get("last") or ticker.get("mark_price", pos.get("mark_price", 0))
                        if pos["size"] != 0:
                            entry_price = pos["entry_price"]
                            current_price = pos["mark_price"]
                            position_size = abs(pos["size"])
                            pnl = (current_price - entry_price) * position_size * Config.LEVERAGE
                            if pos["size"] < 0:
                                pnl = -pnl
                            pos["unrealised_pnl"] = pnl
                    positions.append(pos.copy())
            return positions
        
        try:
            positions = self.api.list_futures_positions(settle="usdt")
            result = []
            for pos in positions:
                pos_dict = {
                    "contract": pos.contract,
                    "size": float(pos.size),
                    "leverage": pos.leverage,
                    "entry_price": float(pos.entry_price) if pos.entry_price else 0,
                    "mark_price": float(pos.mark_price) if pos.mark_price else 0,
                    "unrealised_pnl": float(pos.unrealised_pnl or 0),
                    "value": float(pos.value or 0),
                }
                if symbol is None or pos_dict["contract"] == symbol:
                    result.append(pos_dict)
            return result
        except ApiException as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker price for symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC_USDT)
            
        Returns:
            Ticker dictionary with price information
        """
        # Even in simulation mode, fetch real price data
        if self.simulation_mode:
            try:
                base_url = "https://api.gateio.ws/api/v4"
                url = f"{base_url}/futures/usdt/tickers"
                params = {"contract": symbol}
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data:
                    t = data[0]
                    ticker_data = {
                        "contract": symbol,
                        "last": float(t.get("last", 0)),
                        "mark_price": float(t.get("mark_price", 0)),
                        "index_price": float(t.get("index_price", 0)),
                        "volume_24h": float(t.get("total_volume", 0)),
                    }
                    # Cache the price for fallback
                    self._last_price_cache[symbol] = ticker_data.get("last") or ticker_data.get("mark_price", 0)
                    return ticker_data
            except requests.exceptions.RequestException as e:
                # Network errors - use cached price if available
                cached_price = self._last_price_cache.get(symbol)
                if cached_price and cached_price > 0:
                    logger.warning(
                        f"Network error fetching ticker for {symbol}: {e}. "
                        f"Using cached price: ${cached_price:,.2f}"
                    )
                    return {
                        "contract": symbol,
                        "last": cached_price,
                        "mark_price": cached_price,
                        "index_price": cached_price,
                        "volume_24h": 0,
                    }
                else:
                    logger.warning(f"Network error fetching ticker for {symbol}: {e}. No cached price available.")
                    return None
            except Exception as e:
                logger.warning(f"Error getting ticker in simulation: {e}")
                # Try to use cached price
                cached_price = self._last_price_cache.get(symbol)
                if cached_price and cached_price > 0:
                    return {
                        "contract": symbol,
                        "last": cached_price,
                        "mark_price": cached_price,
                        "index_price": cached_price,
                        "volume_24h": 0,
                    }
                return None
        
        try:
            ticker = self.api.list_futures_tickers(settle="usdt", contract=symbol)
            if ticker:
                t = ticker[0]
                return {
                    "contract": t.contract,
                    "last": float(t.last),
                    "mark_price": float(t.mark_price),
                    "index_price": float(t.index_price),
                    "volume_24h": float(t.total_volume),
                }
        except ApiException as e:
            logger.error(f"Error getting ticker: {e}")
            return None
    
    def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> Optional[Dict]:
        """Place a futures order.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC_USDT)
            side: "buy" or "sell"
            size: Order size (positive number)
            price: Limit price (required for limit orders)
            order_type: "market" or "limit"
            
        Returns:
            Order information dictionary
        """
        if self.simulation_mode:
            return self._simulate_order(symbol, side, size, price, order_type)
        
        try:
            order = FuturesOrder(
                contract=symbol,
                size=size if side == "buy" else -size,
                price=str(price) if price else None,
                tif="ioc" if order_type == "market" else "gtc",
            )
            
            result = self.api.create_futures_order(settle="usdt", futures_order=order)
            return {
                "id": result.id,
                "contract": result.contract,
                "size": float(result.size),
                "price": float(result.price) if result.price else None,
                "status": result.status,
            }
        except ApiException as e:
            logger.error(f"Error placing order: {e}")
            raise
    
    def _simulate_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: Optional[float],
        order_type: str,
    ) -> Dict:
        """Simulate order execution."""
        # Get current price from ticker or cache
        if price:
            current_price = price
        else:
            ticker = self.get_ticker(symbol)
            if ticker:
                current_price = ticker.get("last") or ticker.get("mark_price", 0)
            else:
                # Try cached price
                cached_price = self._last_price_cache.get(symbol)
                if cached_price and cached_price > 0:
                    current_price = cached_price
                    logger.info(f"Using cached price for order simulation: ${current_price:,.2f}")
                else:
                    # Last resort fallback - this shouldn't happen in normal operation
                    current_price = 50000
                    logger.warning(f"No price available for {symbol}, using fallback price: ${current_price:,.2f}")
        
        order_result = {
            "id": f"sim_{int(time.time() * 1000)}",
            "contract": symbol,
            "size": size if side == "buy" else -size,
            "price": current_price,
            "status": "finished",
        }
        
        # Update simulation position
        position_size_before = 0.0
        if symbol not in self._sim_positions:
            self._sim_positions[symbol] = {
                "contract": symbol,
                "size": 0,
                "entry_price": 0,
                "mark_price": current_price,
            }
        else:
            position_size_before = self._sim_positions[symbol]["size"]
        
        pos = self._sim_positions[symbol]
        balance_before = self._sim_balance
        
        total_value = abs(pos["size"]) * pos["entry_price"] if pos["size"] != 0 else 0
        new_size = pos["size"] + order_result["size"]
        
        if new_size == 0:
            # Position closed - calculate realized P&L
            entry_price = pos["entry_price"]
            original_size = pos["size"]
            pnl = (current_price - entry_price) * abs(original_size) * Config.LEVERAGE
            if original_size < 0:  # Short position
                pnl = -pnl
            self._sim_realized_pnl += pnl
            self._sim_balance += pnl
            
            # Log to CSV
            self._log_order_to_csv(
                order_id=order_result["id"],
                symbol=symbol,
                side=side,
                size=size,
                price=current_price,
                order_type=order_type,
                position_size_before=position_size_before,
                position_size_after=0.0,
                entry_price=entry_price,
                exit_price=current_price,
                realized_pnl=pnl,
                balance_before=balance_before,
                balance_after=self._sim_balance,
                trade_type="close",
                notes="Position closed",
            )
            
            logger.info(f"[SIM] Position closed. P&L: ${pnl:.2f}, New Balance: ${self._sim_balance:.2f}")
            del self._sim_positions[symbol]
        else:
            # Update position
            is_opening = pos["size"] == 0
            is_adding = (pos["size"] > 0 and side == "buy") or (pos["size"] < 0 and side == "sell")
            
            if is_opening or is_adding:
                # Average entry price
                new_entry = (total_value + abs(order_result["size"]) * current_price) / abs(new_size)
                pos["entry_price"] = new_entry
            pos["size"] = new_size
            pos["mark_price"] = current_price
            
            # Determine trade type
            trade_type = "open" if is_opening else "partial"
            
            # Log to CSV
            self._log_order_to_csv(
                order_id=order_result["id"],
                symbol=symbol,
                side=side,
                size=size,
                price=current_price,
                order_type=order_type,
                position_size_before=position_size_before,
                position_size_after=new_size,
                entry_price=pos["entry_price"],
                exit_price=0.0,
                realized_pnl=0.0,
                balance_before=balance_before,
                balance_after=self._sim_balance,
                trade_type=trade_type,
                notes="Position opened" if is_opening else "Position added to",
            )
        
        self._sim_trades.append({
            "time": time.time(),
            "symbol": symbol,
            "side": side,
            "size": size,
            "price": current_price,
        })
        
        logger.info(f"[SIM] {side.upper()} {size} {symbol} @ {current_price}")
        return order_result
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        if self.simulation_mode:
            logger.info(f"[SIM] Cancel order {order_id}")
            return True
        
        try:
            self.api.cancel_futures_order(settle="usdt", order_id=order_id)
            return True
        except ApiException as e:
            logger.error(f"Error canceling order: {e}")
            return False
    
    def get_candles(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 200,
    ) -> List[Dict]:
        """Get historical candle data.
        
        Args:
            symbol: Trading pair symbol
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d)
            limit: Number of candles to retrieve
            
        Returns:
            List of candle dictionaries
        """
        # Even in simulation mode, we need real market data for analysis
        # Create a temporary API client for data fetching only
        if self.simulation_mode:
            try:
                # Use public API endpoint (no auth needed for candles)
                base_url = "https://api.gateio.ws/api/v4"
                url = f"{base_url}/futures/usdt/candlesticks"
                params = {
                    "contract": symbol,
                    "interval": interval,
                    "limit": limit,
                }
                response = requests.get(url, params=params, timeout=10)
                
                # Check response status before parsing
                if response.status_code != 200:
                    logger.warning(
                        f"Gate.io API returned status {response.status_code} for {symbol}. "
                        f"Response: {response.text[:200]}"
                    )
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                # Validate response
                if data is None:
                    logger.warning(f"API returned None for {symbol}")
                    return []
                
                if not isinstance(data, list):
                    logger.warning(
                        f"Invalid candle data format for {symbol}: expected list, got {type(data)}. "
                        f"Data: {str(data)[:200]}"
                    )
                    return []
                
                if len(data) == 0:
                    logger.warning(f"Empty candle data list for {symbol}")
                    return []
                
                result = []
                for candle in data:
                    try:
                        candle_data = {
                            "timestamp": int(float(candle.get("t"))),  # timestamp (seconds)
                            "volume": float(candle.get("v")),           # volume
                            "close": float(candle.get("c")),            # close price
                            "high": float(candle.get("h")),             # high price
                            "low": float(candle.get("l")),              # low price
                            "open": float(candle.get("o")),             # open price
                        }
                        
                        # Validate data is reasonable
                        if candle_data["close"] <= 0 or candle_data["timestamp"] <= 0:
                            logger.debug(f"Skipping candle with invalid values: {candle_data}")
                            continue
                        
                        result.append(candle_data)
                        # Update price cache with latest close price
                        self._last_price_cache[symbol] = candle_data["close"]
                    except (IndexError, ValueError, TypeError) as e:
                        logger.warning(f"Error parsing candle data: {candle}, error: {e}")
                        continue
                
                if not result:
                    logger.warning(f"No valid candles retrieved for {symbol}")
                else:
                    logger.debug(f"Retrieved {len(result)} candles for {symbol}")
                
                return result
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error getting candles for {symbol}: {e}")
                return []
            except Exception as e:
                logger.warning(f"Error getting candles in simulation for {symbol}: {type(e).__name__}: {e}")
                return []
        
        try:
            candles = self.api.list_futures_candlesticks(
                settle="usdt",
                contract=symbol,
                interval=interval,
                limit=limit,
            )
            result = []
            for candle in candles:
                result.append({
                    "timestamp": candle.t,
                    "open": float(candle.o),
                    "high": float(candle.h),
                    "low": float(candle.l),
                    "close": float(candle.c),
                    "volume": float(candle.v),
                })
            return result
        except ApiException as e:
            logger.error(f"Error getting candles: {e}")
            return []

