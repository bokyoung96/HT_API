import json
import logging
import asyncio
import websockets
import httpx
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Type

from base import KISConfig, KISAuth
from tools import is_market_open, get_market_status


class DataType(Enum):
    S_QUOTE = "s_quote"      # Stock bid/ask prices and quantities
    S_PRICE = "s_price"      # Stock transaction prices
    F_QUOTE = "f_quote"      # Futures bid/ask prices and quantities  
    F_PRICE = "f_price"      # Futures transaction prices


@dataclass
class SubscriptionConfig:
    data_type: DataType
    symbol: str
    display_name: Optional[str] = None


class ISubscriptionManager(ABC):
    @abstractmethod
    def add_subscription(self, config: SubscriptionConfig) -> None: pass
    
    @abstractmethod
    def get_subscriptions(self) -> List[SubscriptionConfig]: pass
    
    @abstractmethod
    def clear_subscriptions(self) -> None: pass


class IHandlerFactory(ABC):
    @abstractmethod
    def create_handler(self, queue: asyncio.Queue, config: KISConfig, sub_config: SubscriptionConfig) -> 'Handler': pass


class IDataFeed(ABC):
    @abstractmethod
    async def start_feed(self) -> None: pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool: pass
    
    @property
    @abstractmethod
    def message_count(self) -> int: pass


class IDataProcessor(ABC):
    @abstractmethod
    async def process_data(self) -> None: pass
    
    @property
    @abstractmethod
    def processed_count(self) -> int: pass


class SubscriptionManager(ISubscriptionManager):
    def __init__(self):
        self._subscriptions: List[SubscriptionConfig] = []
    
    def add_subscription(self, config: SubscriptionConfig) -> None:
        self._subscriptions.append(config)
    
    def get_subscriptions(self) -> List[SubscriptionConfig]:
        return self._subscriptions.copy()
    
    def clear_subscriptions(self) -> None:
        self._subscriptions.clear()


class HandlerRegistry:
    def __init__(self):
        self._handlers: Dict[DataType, Callable] = {}
    
    def register(self, data_type: DataType, handler_class: Type['Handler']) -> None:
        self._handlers[data_type] = handler_class
    
    def create_handler(self, queue: asyncio.Queue, config: KISConfig, sub_config: SubscriptionConfig) -> 'Handler':
        handler_class = self._handlers.get(sub_config.data_type)
        if not handler_class:
            raise ValueError(f"No handler registered for {sub_config.data_type}")     
        return handler_class(queue, config, sub_config.symbol)


class HandlerFactory(IHandlerFactory):
    def __init__(self):
        self._registry = HandlerRegistry()
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        self._registry.register(DataType.S_QUOTE, StockQuoteHandler)
        self._registry.register(DataType.S_PRICE, StockPriceHandler)
        self._registry.register(DataType.F_QUOTE, FuturesQuoteHandler)
        self._registry.register(DataType.F_PRICE, FuturesPriceHandler)
    
    def create_handler(self, queue: asyncio.Queue, config: KISConfig, sub_config: SubscriptionConfig) -> 'Handler':
        return self._registry.create_handler(queue, config, sub_config)
    
    def register_handler(self, data_type: DataType, handler_class: Type['Handler']) -> None:
        self._registry.register(data_type, handler_class)


class TaskManager:
    def __init__(self):
        self._tasks: List[asyncio.Task] = []
    
    def add_task(self, coro, name: str) -> None:
        task = asyncio.create_task(coro, name=name)
        self._tasks.append(task)
    
    async def run_all(self) -> None:
        try:
            await asyncio.gather(*self._tasks)
        except KeyboardInterrupt:
            logging.info("🛑 Shutdown requested by user")
        except Exception as e:
            logging.error(f"❌ Application error: {e}")
        finally:
            await self._cleanup()
    
    async def _cleanup(self) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


class Handler(ABC):
    def __init__(self, queue: asyncio.Queue): 
        self.queue = queue

    @abstractmethod
    def get_request(self, approval_key: str) -> Dict[str, Any]: pass
    @abstractmethod
    async def handle_message(self, message: str): pass


class StockPriceHandler(Handler):
    def __init__(self, queue: asyncio.Queue, config: KISConfig, stock_code: str):
        super().__init__(queue)
        self.config = config
        self.stock_code = stock_code
        self.tr_id = config.price_tr_id

    def get_request(self, key: str) -> Dict[str, Any]:
        return {"header": {"approval_key": key, 
                           "custtype": "P", 
                           "tr_type": "1"},
                "body": {"input": {"tr_id": self.tr_id, 
                                   "tr_key": self.stock_code}}}

    async def handle_message(self, msg: str):
        if msg.startswith('{'):
            return
            
        if msg.startswith('0') and self.tr_id in msg:
            parts = msg.split('^')
            prefix_parts = parts[0].split('|')
            stock_code = prefix_parts[-1] if len(prefix_parts) >= 4 else "UNKNOWN"
            
            data = {"type": "s_price", 
                    "code": stock_code, 
                    "price": int(parts[2]) if len(parts) > 2 and parts[2] else 0}
            logging.info(f"💰 Price update [{stock_code}]: {data['price']:,}")
            await self.queue.put(data)


class StockQuoteHandler(Handler):
    def __init__(self, queue: asyncio.Queue, config: KISConfig, stock_code: str):
        super().__init__(queue)
        self.config = config
        self.stock_code = stock_code
        self.tr_id = config.quote_tr_id

    def get_request(self, key: str) -> Dict[str, Any]:
        return {"header": {"approval_key": key, 
                           "custtype": "P", 
                           "tr_type": "1"},
                "body": {"input": {"tr_id": self.tr_id, 
                                   "tr_key": self.stock_code}}}

    async def handle_message(self, msg: str):
        if msg.startswith('{'):
            return
            
        if msg.startswith('0') and self.tr_id in msg:
            parts = msg.split('^')
            if len(parts) >= 15:
                prefix_parts = parts[0].split('|')
                stock_code = prefix_parts[-1] if len(prefix_parts) >= 4 else "UNKNOWN"
                
                data = {
                    "type": "s_quote",
                    "code": stock_code,
                    "ask_price_1": int(parts[3]) if parts[3] else 0,
                    "bid_price_1": int(parts[4]) if parts[4] else 0,
                    "ask_qty_1": int(parts[5]) if parts[5] else 0,
                    "bid_qty_1": int(parts[6]) if parts[6] else 0,
                    "ask_price_2": int(parts[7]) if parts[7] else 0,
                    "bid_price_2": int(parts[8]) if parts[8] else 0,
                    "current_price": int(parts[12]) if parts[12] else 0,
                    "change": int(parts[13]) if parts[13] else 0,
                    "volume": int(parts[14]) if parts[14] else 0
                }
                logging.info(f"📊 Quote update [{stock_code}]: Ask {data['ask_price_1']:,} Bid {data['bid_price_1']:,} Current {data['current_price']:,}")
                await self.queue.put(data)


class FuturesQuoteHandler(Handler):
    def __init__(self, queue: asyncio.Queue, config: KISConfig, futures_code: str):
        super().__init__(queue)
        self.config = config
        self.futures_code = futures_code
        self.tr_id = config.futures_quote_tr_id

    def get_request(self, key: str) -> Dict[str, Any]:
        return {"header": {"approval_key": key, 
                           "custtype": "P", 
                           "tr_type": "1"},
                "body": {"input": {"tr_id": self.tr_id, 
                                   "tr_key": self.futures_code}}}

    async def handle_message(self, msg: str):
        if msg.startswith('{'):
            return
            
        if msg.startswith('0') and self.tr_id in msg:
            parts = msg.split('^')
            if len(parts) >= 22:
                prefix_parts = parts[0].split('|')
                futures_code = prefix_parts[-1] if len(prefix_parts) >= 4 else "UNKNOWN"
                
                data = {
                    "type": "f_quote", 
                    "code": futures_code,
                    "time": parts[1],
                    "ask_price_1": float(parts[2]) if parts[2] else 0.0,
                    "ask_price_2": float(parts[3]) if parts[3] else 0.0, 
                    "ask_price_3": float(parts[4]) if parts[4] else 0.0,
                    "bid_price_1": float(parts[7]) if parts[7] else 0.0,
                    "bid_price_2": float(parts[8]) if parts[8] else 0.0,
                    "bid_price_3": float(parts[9]) if parts[9] else 0.0,
                    "ask_qty_1": int(parts[12]) if parts[12] else 0,
                    "ask_qty_2": int(parts[13]) if parts[13] else 0,
                    "bid_qty_1": int(parts[17]) if parts[17] else 0,
                    "bid_qty_2": int(parts[18]) if parts[18] else 0,
                    "current_price": float(parts[2]) if parts[2] else 0.0
                }
                
                logging.info(f"📊 Futures [{futures_code}] Quote - Ask1: {data['ask_price_1']:.2f}({data['ask_qty_1']}) Bid1: {data['bid_price_1']:.2f}({data['bid_qty_1']})")
                await self.queue.put(data)


class FuturesPriceHandler(Handler):
    def __init__(self, queue: asyncio.Queue, config: KISConfig, futures_code: str):
        super().__init__(queue)
        self.config = config
        self.futures_code = futures_code
        self.tr_id = config.futures_price_tr_id

    def get_request(self, key: str) -> Dict[str, Any]:
        return {"header": {"approval_key": key, 
                           "custtype": "P", 
                           "tr_type": "1"},
                "body": {"input": {"tr_id": self.tr_id, 
                                   "tr_key": self.futures_code}}}

    async def handle_message(self, msg: str):
        if msg.startswith('{'):
            return
            
        if msg.startswith('0') and self.tr_id in msg:
            parts = msg.split('^')
            if len(parts) >= 6:
                prefix_parts = parts[0].split('|')
                futures_code = prefix_parts[-1] if len(prefix_parts) >= 4 else "UNKNOWN"

                data = {
                    "type": "f_price", 
                    "code": futures_code,
                    "time": parts[1],
                    "current_price": float(parts[5]) if len(parts) > 5 and parts[5] else 0.0,
                    "change": float(parts[2]) if len(parts) > 2 and parts[2] else 0.0,
                    "change_rate": float(parts[4]) if len(parts) > 4 and parts[4] else 0.0,
                    "volume": int(parts[3]) if len(parts) > 3 and parts[3] else 0
                }
                
                change_symbol = "📈" if data['change'] >= 0 else "📉"
                logging.info(f"{change_symbol} Futures [{futures_code}] Price: {data['current_price']:.2f} (Change: {data['change']:+.2f}, {data['change_rate']:+.2f}%) Vol: {data['volume']:,}")
                await self.queue.put(data)


class KISDataFeed(IDataFeed):
    def __init__(self, config: KISConfig, auth: KISAuth, handlers: List[Handler]):
        self._config = config
        self._auth = auth
        self._handlers = handlers
        self._connected = False
        self._message_count = 0

    async def _send_subscriptions(self, ws: Any, key: str) -> None:
        for handler in self._handlers:
            try:
                req = handler.get_request(key)
                await ws.send(json.dumps(req))
                logging.info(f"📜 Subscription sent: {req['body']['input']}")
            except Exception as e:
                logging.error(f"Failed to send subscription for {handler.__class__.__name__}: {e}")

    async def _process_messages(self, ws: Any) -> None:
        first_message = True
        
        async for message in ws:
            try:
                self._message_count += 1
                
                if first_message:
                    logging.info("📊 First message received - data feed active")
                    first_message = False
                
                await asyncio.gather(*[
                    handler.handle_message(message) 
                    for handler in self._handlers
                ], return_exceptions=True)
                
                if self._message_count % 100 == 0:
                    logging.debug(f"Processed {self._message_count} messages")
                    
            except Exception as e:
                logging.error(f"Error processing message: {e}")

    async def start_feed(self) -> None:
        try:
            key = await self._auth.get_approval_key()
            
            async with websockets.connect(
                self._config.ws_url, 
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ) as ws:
                self._connected = True
                logging.info("✅ WebSocket connection established")
                
                if is_market_open():
                    logging.info("📈 Market is open - real-time data available")
                else:
                    logging.warning("⏰ Market closed - limited data expected")
                
                await self._send_subscriptions(ws, key)
                logging.info("🔍 Waiting for data...")
                await self._process_messages(ws)
                
        except websockets.exceptions.ConnectionClosed as e:
            self._connected = False
            logging.error(f"❌ WebSocket connection closed: {e}")
            
        except websockets.exceptions.InvalidURI as e:
            logging.error(f"❌ Invalid WebSocket URI: {e}")
            
        except asyncio.TimeoutError:
            logging.error("❌ WebSocket connection timeout")
            
        except Exception as e:
            self._connected = False
            logging.error(f"❌ Unexpected error: {e}", exc_info=True)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def message_count(self) -> int:
        return self._message_count


class DataProcessor(IDataProcessor):
    def __init__(self, queue: asyncio.Queue, batch_size: int = 10):
        self.queue = queue
        self.batch_size = batch_size
        self._processed_count = 0

    async def process_data(self) -> None:
        while True:
            try:
                data = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                await self._format_and_display(data)
                
                self.queue.task_done()
                self._processed_count += 1
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Data processing error: {e}")

    async def _format_and_display(self, data: Dict[str, Any]) -> None:
        formatters = {
            "s_quote": self._format_stock_quote,
            "s_price": self._format_stock_price,
            "f_quote": self._format_futures_quote,
            "f_price": self._format_futures_price
        }
        
        formatter = formatters.get(data["type"])
        if formatter:
            print(formatter(data))
        else:
            logging.warning(f"Unknown data type: {data['type']}")

    def _format_stock_quote(self, data: Dict[str, Any]) -> str:
        return (f"📊 [{data['code']}] Stock Quote - "
                f"Ask1: {data['ask_price_1']:,}({data['ask_qty_1']:,}) "
                f"Bid1: {data['bid_price_1']:,}({data['bid_qty_1']:,}) "
                f"Current: {data['current_price']:,}")

    def _format_stock_price(self, data: Dict[str, Any]) -> str:
        return f"💰 [{data['code']}] Stock Price: {data['price']:,}"

    def _format_futures_quote(self, data: Dict[str, Any]) -> str:
        return (f"📊 [{data['code']}] Futures Quote - "
                f"Ask1: {data['ask_price_1']:.2f}({data['ask_qty_1']}) "
                f"Bid1: {data['bid_price_1']:.2f}({data['bid_qty_1']}) "
                f"Ask2: {data['ask_price_2']:.2f}({data['ask_qty_2']}) "
                f"Bid2: {data['bid_price_2']:.2f}({data['bid_qty_2']})")
    
    def _format_futures_price(self, data: Dict[str, Any]) -> str:
        change_symbol = "📈" if data['change'] >= 0 else "📉"
        return f"{change_symbol} [{data['code']}] Futures Price: {data['current_price']:.2f} (Change: {data['change']:+.2f}, {data['change_rate']:+.2f}%) Vol: {data['volume']:,}"

    @property
    def processed_count(self) -> int:
        return self._processed_count


class DataFeedOrchestrator:
    def __init__(self, 
                 subscription_manager: ISubscriptionManager,
                 handler_factory: IHandlerFactory,
                 config: KISConfig,
                 auth: KISAuth):
        self._subscription_manager = subscription_manager
        self._handler_factory = handler_factory
        self._config = config
        self._auth = auth
        self._queue = asyncio.Queue(maxsize=1000)
    
    async def start(self) -> None:
        subscriptions = self._subscription_manager.get_subscriptions()
        if not subscriptions:
            logging.warning("No subscriptions configured!")
            return
        
        handlers = []
        for sub_config in subscriptions:
            try:
                handler = self._handler_factory.create_handler(self._queue, self._config, sub_config)
                handlers.append(handler)
                display_name = sub_config.display_name or sub_config.symbol
                logging.info(f"📡 Added {sub_config.data_type.value} subscription: {display_name}")
            except Exception as e:
                logging.error(f"Failed to create handler for {sub_config}: {e}")
        
        if not handlers:
            logging.error("No valid handlers created!")
            return
        
        feed = KISDataFeed(self._config, self._auth, handlers)
        processor = DataProcessor(self._queue)
        
        task_manager = TaskManager()
        task_manager.add_task(processor.process_data(), "processor")
        task_manager.add_task(feed.start_feed(), "feed")
        
        await task_manager.run_all()
        
        if feed.message_count > 0:
            logging.info(f"📊 Total messages: {feed.message_count}")
            logging.info(f"📈 Processed data: {processor.processed_count}")


class DataFeedBuilder:
    def __init__(self, config: KISConfig, auth: KISAuth):
        self._subscription_manager = SubscriptionManager()
        self._handler_factory = HandlerFactory()
        self._config = config
        self._auth = auth
    
    def add_quote(self, symbol: str, name: Optional[str] = None):
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.S_QUOTE, symbol, name))
        return self
        
    def add_price(self, symbol: str, name: Optional[str] = None):
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.S_PRICE, symbol, name))
        return self
        
    def add_futures_quote(self, symbol: str, name: Optional[str] = None):
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.F_QUOTE, symbol, name))
        return self
        
    def add_futures_price(self, symbol: str, name: Optional[str] = None):
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.F_PRICE, symbol, name))
        return self
        
    def clear_subscriptions(self):
        self._subscription_manager.clear_subscriptions()
        return self
        
    def show_subscriptions(self):
        subscriptions = self._subscription_manager.get_subscriptions()
        if not subscriptions:
            print("No subscriptions configured")
        else:
            print("Current subscriptions:")
            for i, sub in enumerate(subscriptions, 1):
                name = sub.display_name or sub.symbol
                print(f"  {i}. {sub.data_type.value.upper()}: {name}")
                
        return self
    
    def register_custom_handler(self, data_type: DataType, handler_class: Type['Handler']):
        self._handler_factory.register_handler(data_type, handler_class)
        return self
        
    def build(self) -> 'DataFeedOrchestrator':
        return DataFeedOrchestrator(
            self._subscription_manager,
            self._handler_factory,
            self._config,
            self._auth
        )


async def main():
    config = KISConfig("config.json")
    
    status, time_str = get_market_status()
    print(f"🕐 Current time: {time_str}")
    print(f"📈 Market status: {status}")
    print("━" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        auth = KISAuth(config, client)
        
        # Configure data feed
        builder = (DataFeedBuilder(config, auth)
                  .add_futures_price("101W09", "KOSPI200 Futures Price")    
                  .add_futures_quote("101W09", "KOSPI200 Futures Quote"))
        
        # Alternative configurations:
        # builder.add_quote("005930", "Samsung Electronics")     # Stock quote
        # builder.add_price("000660", "SK Hynix")                # Stock price
        
        builder.show_subscriptions()
        print("━" * 50)
        
        orchestrator = builder.build()
        await orchestrator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Program terminated by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("👋 Goodbye!") 