import json
import logging
import asyncio
import httpx
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Type
from datetime import datetime, time

from base import KISConfig, KISAuth
from tools import Tools


class DataType(Enum):
    S_CANDLE = "s_candle"      # Stock candle data
    D_CANDLE = "d_candle"      # Derivatives candle data


class MarketType(Enum):
    STOCK = "stock"
    DERIVATIVES = "derivatives"


def is_market_open(market_type: MarketType) -> bool:
    now = datetime.now().time()
    
    if market_type == MarketType.STOCK:
        return time(9, 0) <= now <= time(15, 30)
    elif market_type == MarketType.DERIVATIVES:
        return time(8, 45) <= now <= time(15, 45)
    
    return False


@dataclass
class CandleData:
    symbol: str
    timestamp: datetime
    timeframe: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    data_type: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "timeframe": f"{self.timeframe}m",
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "type": f"{self.data_type}_candle"
        }


@dataclass
class SubscriptionConfig:
    data_type: DataType
    symbol: str
    timeframe: int = 1
    display_name: Optional[str] = None


class ISubscriptionManager(ABC):
    @abstractmethod
    def add_subscription(self, config: SubscriptionConfig) -> None: pass
    
    @abstractmethod
    def get_subscriptions(self) -> List[SubscriptionConfig]: pass
    
    @abstractmethod
    def clear_subscriptions(self) -> None: pass


class IFetcherFactory(ABC):
    @abstractmethod
    def create_fetcher(self, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient, queue: asyncio.Queue, sub_config: SubscriptionConfig) -> 'PriceFetcher': pass


class IDataFeed(ABC):
    @abstractmethod
    async def start_feed(self) -> None: pass
    
    @property
    @abstractmethod
    def is_running(self) -> bool: pass
    
    @property
    @abstractmethod
    def fetch_count(self) -> int: pass


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


class CandleProcessor:
    def __init__(self, symbol: str, timeframe: int, queue: asyncio.Queue):
        self.symbol = symbol
        self.timeframe = timeframe
        self.queue = queue
        self._last_processed_time: Optional[str] = None

    async def process_candle_data(self, current_time: Optional[str], completed_candle: Optional[Dict], 
                                 log_format: str, process_func: Callable[[Dict], Optional[CandleData]]) -> Dict[str, Any]:
        if not current_time or not completed_candle:
            return {}

        if self._last_processed_time is None:
            wait_msg = f"⏳ [{self.symbol}] First run - waiting for next fresh candle..."
            logging.debug(wait_msg)
            print(wait_msg)
            self._last_processed_time = current_time
            return {}

        if self._last_processed_time == current_time:
            return {}

        self._last_processed_time = current_time
        
        processed_candle = process_func(completed_candle)
        if not processed_candle:
            return {}

        candle_data = processed_candle.to_dict()
        logging.info(log_format.format(
            symbol=self.symbol,
            timeframe=self.timeframe,
            open=processed_candle.open,
            high=processed_candle.high,
            low=processed_candle.low,
            close=processed_candle.close,
            volume=processed_candle.volume
        ))
        await self.queue.put(candle_data)
        return candle_data


class PriceFetcher(ABC):
    def __init__(self, queue: asyncio.Queue, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient, 
                 symbol: str, timeframe: int, market_type: MarketType):
        self.queue = queue
        self.config = config
        self.auth = auth
        self.client = client
        self.symbol = symbol
        self.timeframe = timeframe
        self.market_type = market_type
        self._candle_processor = CandleProcessor(symbol, timeframe, queue)
    
    @abstractmethod
    async def fetch_data(self) -> Dict[str, Any]: pass
    
    async def get_headers(self) -> Dict[str, str]:
        token = await self.auth.get_access_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "appKey": self.config.app_key,
            "appSecret": self.config.app_secret
        }
    
    def is_trading_hours(self) -> bool:
        return is_market_open(self.market_type)

    async def _handle_candle_data(self, current_time: Optional[str], completed_candle: Optional[Dict], log_format: str) -> Dict[str, Any]:
        return await self._candle_processor.process_candle_data(
            current_time, completed_candle, log_format, self._process_candle_data
        )

    @abstractmethod
    def _process_candle_data(self, candle: Dict) -> Optional[CandleData]: pass


class StockPriceFetcher(PriceFetcher):
    def __init__(self, queue: asyncio.Queue, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient, 
                 symbol: str, timeframe: int):
        super().__init__(queue, config, auth, client, symbol, timeframe, MarketType.STOCK)

    def _select_completed_candle(self, candles: List[Dict], current_time: str) -> Optional[Dict]:
        if len(candles) < 1:
            return None
        if current_time.startswith("1530"):
            return candles[0]
        return candles[1] if len(candles) > 1 else None

    async def fetch_data(self) -> Dict[str, Any]:
        if not self.is_trading_hours():
            logging.debug(f"Outside trading hours for stock {self.symbol}")
            return {}
            
        url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        headers = await self.get_headers()
        headers["tr_id"] = self.config.stock_minute_tr_id
        
        query_time = datetime.now().strftime('%H%M%S')
        
        params = {
            "fid_etc_cls_code": "",
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": self.symbol,
            "fid_input_hour_1": query_time,
            "fid_pw_data_incu_yn": "Y"
        }
        
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("rt_cd") != "0" or not data.get("output2"):
            return {}

        candles = data["output2"]
        current_time = candles[0].get("stck_cntg_hour")
        
        # 적절한 완성 봉 선택
        completed_candle = self._select_completed_candle(candles, current_time)
        if not completed_candle:
            return {}
        
        log_format = "🕐 [{symbol}] {timeframe}m: OHLCV {open:.0f}/{high:.0f}/{low:.0f}/{close:.0f} Vol: {volume:,}"
        return await self._handle_candle_data(current_time, completed_candle, log_format)
    
    def _process_candle_data(self, candle: Dict) -> Optional[CandleData]:
        if not candle:
            return None
            
        return CandleData(
            symbol=self.symbol,
            timestamp=datetime.now().replace(second=0, microsecond=0),
            timeframe=self.timeframe,
            open=int(candle.get("stck_oprc", 0)),
            high=int(candle.get("stck_hgpr", 0)),
            low=int(candle.get("stck_lwpr", 0)),
            close=int(candle.get("stck_prpr", 0)),
            volume=int(candle.get("cntg_vol", 0)),
            data_type="s"
        )


class DerivPriceFetcher(PriceFetcher):
    def __init__(self, queue: asyncio.Queue, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient, 
                 symbol: str, timeframe: int):
        super().__init__(queue, config, auth, client, symbol, timeframe, MarketType.DERIVATIVES)

    def _select_completed_candle(self, candles: List[Dict], current_time: str) -> Optional[Dict]:
        if len(candles) < 1:
            return None
        if current_time.startswith("1545"):
            return candles[0]
        return candles[1] if len(candles) > 1 else None

    async def fetch_data(self) -> Dict[str, Any]:
        if not self.is_trading_hours():
            logging.debug(f"Outside trading hours for derivatives {self.symbol}")
            return {}
            
        url = f"{self.config.base_url}/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
        headers = await self.get_headers()
        headers["tr_id"] = self.config.deriv_minute_tr_id
        
        query_time = datetime.now().strftime('%H%M%S')
        
        params = {
            "fid_cond_mrkt_div_code": "F",
            "fid_input_iscd": self.symbol,
            "fid_hour_cls_code": "60",
            "fid_pw_data_incu_yn": "Y",
            "fid_fake_tick_incu_yn": "N",
            "fid_input_date_1": "",
            "fid_input_hour_1": query_time
        }
        
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("rt_cd") != "0" or not data.get("output2"):
            return {}

        candles = data["output2"]
        current_time = candles[0].get("stck_cntg_hour")
        
        completed_candle = self._select_completed_candle(candles, current_time)
        if not completed_candle:
            return {}
        
        log_format = "🕐 [{symbol}] {timeframe}m: OHLCV {open:.2f}/{high:.2f}/{low:.2f}/{close:.2f} Vol: {volume:,}"
        return await self._handle_candle_data(current_time, completed_candle, log_format)
    
    def _process_candle_data(self, candle: Dict) -> Optional[CandleData]:
        if not candle:
            return None
            
        return CandleData(
            symbol=self.symbol,
            timestamp=datetime.now().replace(second=0, microsecond=0),
            timeframe=self.timeframe,
            open=float(candle.get("futs_oprc", 0)),
            high=float(candle.get("futs_hgpr", 0)),
            low=float(candle.get("futs_lwpr", 0)),
            close=float(candle.get("futs_prpr", 0)),
            volume=int(candle.get("cntg_vol", 0)),
            data_type="d"
        )


class FetcherRegistry:
    def __init__(self):
        self._fetchers: Dict[DataType, Callable] = {}
    
    def register(self, data_type: DataType, fetcher_class: Type[PriceFetcher]) -> None:
        self._fetchers[data_type] = fetcher_class
    
    def create_fetcher(self, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient, queue: asyncio.Queue, sub_config: SubscriptionConfig) -> PriceFetcher:
        fetcher_class = self._fetchers.get(sub_config.data_type)
        if not fetcher_class:
            raise ValueError(f"No fetcher registered for {sub_config.data_type}")     
        return fetcher_class(queue, config, auth, client, sub_config.symbol, sub_config.timeframe)


class FetcherFactory(IFetcherFactory):
    def __init__(self):
        self._registry = FetcherRegistry()
        self._register_default_fetchers()
    
    def _register_default_fetchers(self):
        self._registry.register(DataType.S_CANDLE, StockPriceFetcher)
        self._registry.register(DataType.D_CANDLE, DerivPriceFetcher)
    
    def create_fetcher(self, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient, queue: asyncio.Queue, sub_config: SubscriptionConfig) -> PriceFetcher:
        return self._registry.create_fetcher(config, auth, client, queue, sub_config)
    
    def register_fetcher(self, data_type: DataType, fetcher_class: Type[PriceFetcher]) -> None:
        self._registry.register(data_type, fetcher_class)


class PollingManager:
    def __init__(self, interval: int, fetchers: List[PriceFetcher]):
        self._interval = interval
        self._fetchers = fetchers
        self._running = False
        self._fetch_count = 0

    async def start_polling(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._execute_fetch_cycle()
                await asyncio.sleep(self._interval)
            except Exception as e:
                logging.error(f"Error during polling: {e}")
                await asyncio.sleep(self._interval)

    async def _execute_fetch_cycle(self) -> None:
        fetch_tasks = [fetcher.fetch_data() for fetcher in self._fetchers]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict) and result:
                pass
        
        self._fetch_count += len(self._fetchers)
        
        if self._fetch_count % 20 == 0:
            logging.debug(f"Completed {self._fetch_count} fetches")

    def stop(self) -> None:
        self._running = False

    @property
    def fetch_count(self) -> int:
        return self._fetch_count


class KISDataFeed(IDataFeed):
    def __init__(self, config: KISConfig, auth: KISAuth, fetchers: List[PriceFetcher]):
        self._config = config
        self._auth = auth
        self._fetchers = fetchers
        self._queue = asyncio.Queue()
        self._polling_manager = PollingManager(config.polling_interval, fetchers)

    async def start_feed(self) -> None:
        if self._polling_manager._running:
            logging.warning("Data feed is already running")
            return
            
        timeframes = list(set(f.timeframe for f in self._fetchers))
        logging.info(f"🚀 Starting candle feed with {len(self._fetchers)} fetchers")
        logging.info(f"⏱️  Polling interval: {self._config.polling_interval} seconds")
        logging.info(f"📊 Timeframes: {timeframes}m")
        
        try:
            await self._polling_manager.start_polling()
        except KeyboardInterrupt:
            logging.info("🛑 Data feed stopped by user")
        finally:
            self._polling_manager.stop()

    @property
    def is_running(self) -> bool:
        return self._polling_manager._running
    
    @property
    def fetch_count(self) -> int:
        return self._polling_manager.fetch_count


class DataProcessor(IDataProcessor):
    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._processed_count = 0

    async def process_data(self) -> None:
        while True:
            try:
                data = await self._queue.get()
                await self._process_single_data(data)
                self._processed_count += 1
                self._queue.task_done()
            except Exception as e:
                logging.error(f"Error processing data: {e}")

    async def _process_single_data(self, data: Dict[str, Any]) -> None:
        data_type = data.get("type", "unknown")
        symbol = data.get("symbol", "unknown")
        timestamp = data.get("timestamp", "")
        
        logging.debug(f"📦 Processing {data_type} data for {symbol} at {timestamp}")

    @property
    def processed_count(self) -> int:
        return self._processed_count


class DataFeedOrchestrator:
    def __init__(self, subscription_manager: ISubscriptionManager, 
                 fetcher_factory: IFetcherFactory, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient):
        self._subscription_manager = subscription_manager
        self._fetcher_factory = fetcher_factory
        self._config = config
        self._auth = auth
        self._client = client
        self._data_feed: Optional[IDataFeed] = None
        self._data_processor: Optional[IDataProcessor] = None

    async def start(self) -> None:
        subscriptions = self._subscription_manager.get_subscriptions()
        if not subscriptions:
            logging.warning("No subscriptions configured")
            return

        shared_queue = asyncio.Queue()
        fetchers = []
        
        for sub_config in subscriptions:
            try:
                fetcher = self._fetcher_factory.create_fetcher(self._config, self._auth, self._client, shared_queue, sub_config)
                fetchers.append(fetcher)
                asset_type = "stock" if sub_config.data_type == DataType.S_CANDLE else "derivatives"
                logging.info(f"✅ Created fetcher for {asset_type}: {sub_config.symbol} ({sub_config.timeframe}m)")
            except Exception as e:
                logging.error(f"❌ Failed to create fetcher for {sub_config.symbol}: {e}")

        if not fetchers:
            logging.error("No fetchers created successfully")
            return

        self._data_feed = KISDataFeed(self._config, self._auth, fetchers)
        
        await self._data_feed.start_feed()


class DataFeedBuilder:
    def __init__(self, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient):
        self._config = config
        self._auth = auth
        self._client = client
        self._subscription_manager = SubscriptionManager()
        self._fetcher_factory = FetcherFactory()

    def add_stock(self, symbol: str, timeframe: int = 1, name: Optional[str] = None):
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.S_CANDLE, symbol, timeframe, name))
        return self
        
    def add_deriv(self, symbol: str, timeframe: int = 1, name: Optional[str] = None):
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.D_CANDLE, symbol, timeframe, name))
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
                asset_type = "Stock" if sub.data_type == DataType.S_CANDLE else "Derivatives"
                print(f"  {i}. {asset_type}: {name} ({sub.timeframe}m)")
                
        return self
    
    def register_custom_fetcher(self, data_type: DataType, fetcher_class: Type[PriceFetcher]):
        self._fetcher_factory.register_fetcher(data_type, fetcher_class)
        return self
        
    def build(self) -> DataFeedOrchestrator:
        return DataFeedOrchestrator(
            self._subscription_manager,
            self._fetcher_factory,
            self._config,
            self._auth,
            self._client
        )


async def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = KISConfig("config.json")
    
    print(f"🕐 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️  Polling interval: {config.polling_interval} seconds")
    print(f"🏢 Stock market hours: 09:00 ~ 15:30")
    print(f"📈 Derivatives market hours: 08:45 ~ 15:45")
    print("━" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        auth = KISAuth(config, client)
        
        builder = (DataFeedBuilder(config, auth, client)
                  .add_stock("005930", timeframe=1, name="Samsung Electronics")
                  .add_deriv("101W09", timeframe=1, name="KOSPI200 Futures"))
        
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