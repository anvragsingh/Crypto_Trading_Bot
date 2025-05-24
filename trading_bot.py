
# Binance Futures Trading Bot for Testnet


import logging
import json
import sys
from datetime import datetime
from typing import Optional, Dict, List
from decimal import Decimal, ROUND_DOWN
import time

try:
    from binance import Client
    from binance.exceptions import BinanceAPIException, BinanceOrderException
    import colorama
    from colorama import Fore, Style
    colorama.init()
except ImportError as e:
    print(f"Missing required packages. Please install with:")
    print("pip install python-binance colorama")
    sys.exit(1)


class TradingBotLogger:
    """Custom logger for trading bot operations"""
    
    def __init__(self, log_file: str = "trading_bot.log", level: int = logging.INFO):
        self.logger = logging.getLogger("TradingBot")
        self.logger.setLevel(level)
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def critical(self, message: str):
        self.logger.critical(message)


class BasicBot:
    """Simplified Trading Bot for Binance Futures Testnet"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Initialize the trading bot
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet (default: True)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client = None
        self.logger = TradingBotLogger()
        
        # Initialize client
        self._initialize_client()
        
        # Cache for symbol info
        self.symbol_info_cache = {}
        self.account_info = None
    
    def _initialize_client(self):
        """Initialize Binance client with proper configuration"""
        try:
            self.client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            
            # Set testnet URL for futures
            if self.testnet:
                self.client.API_URL = 'https://testnet.binancefuture.com'
                self.client.FUTURES_URL = 'https://testnet.binancefuture.com'
            
            # Test connection
            server_time = self.client.get_server_time()
            self.logger.info(f"Connected to Binance {'Testnet' if self.testnet else 'Mainnet'}")
            self.logger.info(f"Server time: {datetime.fromtimestamp(server_time['serverTime']/1000)}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize client: {str(e)}")
            raise
    
    def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            self.account_info = self.client.futures_account()
            self.logger.info("Account information retrieved successfully")
            return self.account_info
        except BinanceAPIException as e:
            self.logger.error(f"API Error getting account info: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            raise
    
    def get_balance(self, asset: str = "USDT") -> float:
        """Get balance for specific asset"""
        try:
            if not self.account_info:
                self.get_account_info()
            
            for balance in self.account_info['assets']:
                if balance['asset'] == asset:
                    return float(balance['walletBalance'])
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return 0.0
    
    def get_symbol_info(self, symbol: str) -> Dict:
        """Get symbol information with caching"""
        if symbol in self.symbol_info_cache:
            return self.symbol_info_cache[symbol]
        
        try:
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    self.symbol_info_cache[symbol] = s
                    return s
            raise ValueError(f"Symbol {symbol} not found")
        except Exception as e:
            self.logger.error(f"Error getting symbol info: {e}")
            raise
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            self.logger.error(f"Error getting price for {symbol}: {e}")
            raise
    
    def validate_order_params(self, symbol: str, side: str, order_type: str, 
                            quantity: float, price: Optional[float] = None) -> bool:
        """Validate order parameters"""
        try:
            # Get symbol info
            symbol_info = self.get_symbol_info(symbol)
            
            # Check if symbol is active
            if symbol_info['status'] != 'TRADING':
                raise ValueError(f"Symbol {symbol} is not actively trading")
            
            # Validate side
            if side.upper() not in ['BUY', 'SELL']:
                raise ValueError("Side must be 'BUY' or 'SELL'")
            
            # Validate order type
            if order_type.upper() not in ['MARKET', 'LIMIT']:
                raise ValueError("Order type must be 'MARKET' or 'LIMIT'")
            
            # Validate quantity
            lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
            min_qty = float(lot_size_filter['minQty'])
            max_qty = float(lot_size_filter['maxQty'])
            step_size = float(lot_size_filter['stepSize'])
            
            if quantity < min_qty or quantity > max_qty:
                raise ValueError(f"Quantity must be between {min_qty} and {max_qty}")
            
            # Check step size
            precision = len(str(step_size).split('.')[-1]) if '.' in str(step_size) else 0
            rounded_qty = round(quantity, precision)
            if abs(quantity - rounded_qty) > 1e-10:
                self.logger.warning(f"Quantity adjusted from {quantity} to {rounded_qty}")
            
            # Validate price for limit orders
            if order_type.upper() == 'LIMIT' and price:
                price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
                min_price = float(price_filter['minPrice'])
                max_price = float(price_filter['maxPrice'])
                tick_size = float(price_filter['tickSize'])
                
                if price < min_price or price > max_price:
                    raise ValueError(f"Price must be between {min_price} and {max_price}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Order validation failed: {e}")
            raise
    
    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Place a market order"""
        try:
            self.validate_order_params(symbol, side, 'MARKET', quantity)
            
            self.logger.info(f"Placing MARKET {side} order: {quantity} {symbol}")
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side.upper(),
                type='MARKET',
                quantity=quantity
            )
            
            self.logger.info(f"Market order placed successfully: {order['orderId']}")
            return order
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API Error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error placing market order: {e}")
            raise
    
    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> Dict:
        """Place a limit order"""
        try:
            self.validate_order_params(symbol, side, 'LIMIT', quantity, price)
            
            self.logger.info(f"Placing LIMIT {side} order: {quantity} {symbol} at {price}")
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side.upper(),
                type='LIMIT',
                timeInForce='GTC',
                quantity=quantity,
                price=price
            )
            
            self.logger.info(f"Limit order placed successfully: {order['orderId']}")
            return order
            
        except BinanceAPIException as e:
            self.logger.error(f"Binance API Error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error placing limit order: {e}")
            raise
    
    def get_order_status(self, symbol: str, order_id: int) -> Dict:
        """Get order status"""
        try:
            return self.client.futures_get_order(symbol=symbol, orderId=order_id)
        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            raise
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an order"""
        try:
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            self.logger.info(f"Order {order_id} cancelled successfully")
            return result
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            raise
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open orders"""
        try:
            return self.client.futures_get_open_orders(symbol=symbol)
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            raise


class TradingBotCLI:
    """Command Line Interface for Trading Bot"""
    
    def __init__(self):
        self.bot = None
        self.running = True
    
    def print_header(self):
        """Print CLI header"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}    BINANCE FUTURES TRADING BOT - TESTNET")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    def print_menu(self):
        """Print main menu"""
        print(f"\n{Fore.YELLOW}Available Commands:{Style.RESET_ALL}")
        print("1. Check Account Balance")
        print("2. Get Current Price")
        print("3. Place Market Order")
        print("4. Place Limit Order")
        print("5. Check Order Status")
        print("6. View Open Orders")
        print("7. Cancel Order")
        print("8. Exit")
        print("-" * 30)
    
    def setup_credentials(self):
        """Setup API credentials"""
        print(f"{Fore.GREEN}Setup Binance Testnet Credentials{Style.RESET_ALL}")
        print("\nGet your testnet credentials from: https://testnet.binancefuture.com")
        
        api_key = input("\nEnter API Key: ").strip()
        api_secret = input("Enter API Secret: ").strip()
        
        if not api_key or not api_secret:
            print(f"{Fore.RED}API credentials cannot be empty!{Style.RESET_ALL}")
            return False
        
        try:
            self.bot = BasicBot(api_key, api_secret, testnet=True)
            print(f"{Fore.GREEN}✓ Connected successfully to Binance Testnet{Style.RESET_ALL}")
            return True
        except Exception as e:
            print(f"{Fore.RED}✗ Connection failed: {str(e)}{Style.RESET_ALL}")
            return False
    
    def handle_balance_check(self):
        """Handle balance check"""
        try:
            balance = self.bot.get_balance("USDT")
            print(f"\n{Fore.GREEN}Account Balance: {balance:.4f} USDT{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def handle_price_check(self):
        """Handle price check"""
        symbol = input("Enter symbol (e.g., BTCUSDT): ").strip().upper()
        if not symbol:
            print(f"{Fore.RED}Symbol cannot be empty!{Style.RESET_ALL}")
            return
        
        try:
            price = self.bot.get_current_price(symbol)
            print(f"\n{Fore.GREEN}Current price of {symbol}: {price:.4f}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def handle_market_order(self):
        """Handle market order placement"""
        try:
            symbol = input("Enter symbol (e.g., BTCUSDT): ").strip().upper()
            side = input("Enter side (BUY/SELL): ").strip().upper()
            quantity = float(input("Enter quantity: ").strip())
            
            # Confirm order
            current_price = self.bot.get_current_price(symbol)
            print(f"\n{Fore.YELLOW}Order Summary:{Style.RESET_ALL}")
            print(f"Symbol: {symbol}")
            print(f"Side: {side}")
            print(f"Type: MARKET")
            print(f"Quantity: {quantity}")
            print(f"Est. Price: {current_price:.4f}")
            
            confirm = input(f"\nConfirm order? (y/N): ").strip().lower()
            if confirm == 'y':
                order = self.bot.place_market_order(symbol, side, quantity)
                print(f"\n{Fore.GREEN}✓ Market order placed successfully!{Style.RESET_ALL}")
                print(f"Order ID: {order['orderId']}")
            else:
                print("Order cancelled.")
                
        except ValueError as e:
            print(f"{Fore.RED}Invalid input: {str(e)}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def handle_limit_order(self):
        """Handle limit order placement"""
        try:
            symbol = input("Enter symbol (e.g., BTCUSDT): ").strip().upper()
            side = input("Enter side (BUY/SELL): ").strip().upper()
            quantity = float(input("Enter quantity: ").strip())
            price = float(input("Enter price: ").strip())
            
            # Show current market price for reference
            current_price = self.bot.get_current_price(symbol)
            print(f"\nCurrent market price: {current_price:.4f}")
            
            print(f"\n{Fore.YELLOW}Order Summary:{Style.RESET_ALL}")
            print(f"Symbol: {symbol}")
            print(f"Side: {side}")
            print(f"Type: LIMIT")
            print(f"Quantity: {quantity}")
            print(f"Price: {price:.4f}")
            
            confirm = input(f"\nConfirm order? (y/N): ").strip().lower()
            if confirm == 'y':
                order = self.bot.place_limit_order(symbol, side, quantity, price)
                print(f"\n{Fore.GREEN}✓ Limit order placed successfully!{Style.RESET_ALL}")
                print(f"Order ID: {order['orderId']}")
            else:
                print("Order cancelled.")
                
        except ValueError as e:
            print(f"{Fore.RED}Invalid input: {str(e)}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def handle_order_status(self):
        """Handle order status check"""
        try:
            symbol = input("Enter symbol: ").strip().upper()
            order_id = int(input("Enter order ID: ").strip())
            
            order = self.bot.get_order_status(symbol, order_id)
            
            print(f"\n{Fore.GREEN}Order Status:{Style.RESET_ALL}")
            print(f"Order ID: {order['orderId']}")
            print(f"Symbol: {order['symbol']}")
            print(f"Status: {order['status']}")
            print(f"Side: {order['side']}")
            print(f"Type: {order['type']}")
            print(f"Quantity: {order['origQty']}")
            print(f"Filled: {order['executedQty']}")
            if order['type'] == 'LIMIT':
                print(f"Price: {order['price']}")
            
        except ValueError as e:
            print(f"{Fore.RED}Invalid input: {str(e)}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def handle_open_orders(self):
        """Handle open orders display"""
        try:
            symbol = input("Enter symbol (optional, press Enter for all): ").strip().upper()
            symbol = symbol if symbol else None
            
            orders = self.bot.get_open_orders(symbol)
            
            if not orders:
                print(f"\n{Fore.YELLOW}No open orders found.{Style.RESET_ALL}")
                return
            
            print(f"\n{Fore.GREEN}Open Orders:{Style.RESET_ALL}")
            print("-" * 80)
            for order in orders:
                print(f"ID: {order['orderId']} | {order['symbol']} | {order['side']} | "
                      f"{order['type']} | Qty: {order['origQty']} | Status: {order['status']}")
            
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def handle_cancel_order(self):
        """Handle order cancellation"""
        try:
            symbol = input("Enter symbol: ").strip().upper()
            order_id = int(input("Enter order ID to cancel: ").strip())
            
            confirm = input(f"Cancel order {order_id} for {symbol}? (y/N): ").strip().lower()
            if confirm == 'y':
                result = self.bot.cancel_order(symbol, order_id)
                print(f"\n{Fore.GREEN}✓ Order cancelled successfully!{Style.RESET_ALL}")
            else:
                print("Cancellation aborted.")
                
        except ValueError as e:
            print(f"{Fore.RED}Invalid input: {str(e)}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    
    def run(self):
        """Run the CLI interface"""
        self.print_header()
        
        # Setup credentials
        if not self.setup_credentials():
            return
        
        # Main loop
        while self.running:
            try:
                self.print_menu()
                choice = input(f"{Fore.CYAN}Enter your choice (1-8): {Style.RESET_ALL}").strip()
                
                if choice == '1':
                    self.handle_balance_check()
                elif choice == '2':
                    self.handle_price_check()
                elif choice == '3':
                    self.handle_market_order()
                elif choice == '4':
                    self.handle_limit_order()
                elif choice == '5':
                    self.handle_order_status()
                elif choice == '6':
                    self.handle_open_orders()
                elif choice == '7':
                    self.handle_cancel_order()
                elif choice == '8':
                    print(f"\n{Fore.GREEN}Thank you for using the Trading Bot!{Style.RESET_ALL}")
                    self.running = False
                else:
                    print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")
                
                if self.running:
                    input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
                    
            except KeyboardInterrupt:
                print(f"\n\n{Fore.YELLOW}Exiting...{Style.RESET_ALL}")
                self.running = False
            except Exception as e:
                print(f"{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")


def main():
    """Main function"""
    try:
        cli = TradingBotCLI()
        cli.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()