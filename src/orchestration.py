from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Type

from base import KISAuth, KISConfig
from core.feed import KISDataFeed
from core.subscription import SubscriptionManager
from fetchers.factory import FetcherFactory
from models.dataclasses import SubscriptionConfig
from models.enums import DataType
from processing.processors import DataProcessor
from protocols import DataFeed, DataProcessor as DataProcessorProtocol, FetcherFactory as FetcherFactoryProtocol, SubscriptionManager as SubscriptionManagerProtocol

if TYPE_CHECKING:
    import httpx
    from fetchers.base_fetcher import PriceFetcher


class DataFeedOrchestrator:
    def __init__(
        self,
        subscription_manager: SubscriptionManagerProtocol,
        fetcher_factory: FetcherFactoryProtocol,
        config: KISConfig,
        auth: KISAuth,
        client: httpx.AsyncClient,
    ):
        self._subscription_manager = subscription_manager
        self._fetcher_factory = fetcher_factory
        self._config = config
        self._auth = auth
        self._client = client
        self._data_feed: Optional[DataFeed] = None
        self._data_processor: Optional[DataProcessorProtocol] = None
        self._data_writer = None
        
    def set_data_writer(self, data_writer):
        self._data_writer = data_writer

    async def start(self) -> None:
        subscriptions = self._subscription_manager.get_subscriptions()
        if not subscriptions:
            logging.warning("No subscriptions configured")
            return

        shared_queue = asyncio.Queue()
        fetchers = []

        for sub_config in subscriptions:
            try:
                fetcher = self._fetcher_factory.create_fetcher(
                    self._config, self._auth, self._client, shared_queue, sub_config
                )
                fetchers.append(fetcher)
                asset_type = (
                    "stock"
                    if sub_config.data_type == DataType.S_CANDLE
                    else "derivatives"
                )
                logging.info(
                    f"✅ Created fetcher for {asset_type}: {sub_config.symbol} ({sub_config.timeframe}m)"
                )
            except Exception as e:
                logging.error(
                    f"❌ Failed to create fetcher for {sub_config.symbol}: {e}"
                )

        if not fetchers:
            logging.error("No fetchers created successfully")
            return

        self._data_feed = KISDataFeed(self._config, self._auth, fetchers)
        self._data_processor = DataProcessor(shared_queue, self._data_writer)

        tasks = [
            asyncio.create_task(self._data_feed.start_feed()),
            asyncio.create_task(self._data_processor.process_data())
        ]
        
        if self._data_writer:
            tasks.append(asyncio.create_task(self._data_writer.start_batch_writer()))
            logging.info("✅ Database writer started")

        await asyncio.gather(*tasks)


class DataFeedBuilder:
    def __init__(
        self, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient
    ):
        self._config = config
        self._auth = auth
        self._client = client
        self._subscription_manager = SubscriptionManager()
        self._fetcher_factory = FetcherFactory()

    def add_stock(
        self, symbol: str, timeframe: int = 1, name: Optional[str] = None
    ) -> DataFeedBuilder:
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.S_CANDLE, symbol, timeframe, name)
        )
        return self

    def add_deriv(
        self, symbol: str, timeframe: int = 1, name: Optional[str] = None
    ) -> DataFeedBuilder:
        self._subscription_manager.add_subscription(
            SubscriptionConfig(DataType.D_CANDLE, symbol, timeframe, name)
        )
        return self

    def add_option_chain(
        self,
        maturity: str,
        underlying_asset_type: str = "",
        name: Optional[str] = None,
    ) -> DataFeedBuilder:
        self._subscription_manager.add_subscription(
            SubscriptionConfig(
                DataType.O_CHAIN, "", 1, name, maturity, underlying_asset_type
            )
        )
        return self

    def clear_subscriptions(self) -> DataFeedBuilder:
        self._subscription_manager.clear_subscriptions()
        return self

    def show_subscriptions(self) -> DataFeedBuilder:
        subscriptions = self._subscription_manager.get_subscriptions()
        if not subscriptions:
            print("No subscriptions configured")
        else:
            print("Current subscriptions:")
            for i, sub in enumerate(subscriptions, 1):
                name = sub.display_name or sub.symbol
                if sub.data_type == DataType.S_CANDLE:
                    asset_type = "Stock"
                    details = f"{name} ({sub.timeframe}m)"
                elif sub.data_type == DataType.D_CANDLE:
                    asset_type = "Derivatives"
                    details = f"{name} ({sub.timeframe}m)"
                elif sub.data_type == DataType.O_CHAIN:
                    asset_type = "Option Chain"
                    details = f"{name} (Maturity: {sub.maturity})"
                else:
                    asset_type = "Unknown"
                    details = f"{name}"

                print(f"  {i}. {asset_type}: {details}")

        return self

    def register_custom_fetcher(
        self, data_type: DataType, fetcher_class: Type[PriceFetcher]
    ) -> DataFeedBuilder:
        self._fetcher_factory.register_fetcher(data_type, fetcher_class)
        return self

    def build(self) -> DataFeedOrchestrator:
        return DataFeedOrchestrator(
            self._subscription_manager,
            self._fetcher_factory,
            self._config,
            self._auth,
            self._client,
        ) 