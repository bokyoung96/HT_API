from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Callable, Dict, Type

from fetchers.base_fetcher import PriceFetcher
from fetchers.deriv_fetcher import DerivPriceFetcher
from fetchers.option_chain_fetcher import OptionChainFetcher
from fetchers.stock_fetcher import StockPriceFetcher
from models.dataclasses import SubscriptionConfig
from models.enums import DataType
from protocols import FetcherFactory as FetcherFactoryProtocol

if TYPE_CHECKING:
    import httpx
    from base import KISAuth, KISConfig


class FetcherRegistry:
    def __init__(self):
        self._fetchers: Dict[DataType, Type[PriceFetcher]] = {}

    def register(
        self, data_type: DataType, fetcher_class: Type[PriceFetcher]
    ) -> None:
        self._fetchers[data_type] = fetcher_class

    def create_fetcher(
        self,
        config: KISConfig,
        auth: KISAuth,
        client: httpx.AsyncClient,
        queue: asyncio.Queue,
        sub_config: SubscriptionConfig,
    ) -> PriceFetcher:
        fetcher_class = self._fetchers.get(sub_config.data_type)
        if not fetcher_class:
            raise ValueError(f"No fetcher registered for {sub_config.data_type}")

        if sub_config.data_type == DataType.O_CHAIN:
            return fetcher_class(
                queue,
                config,
                auth,
                client,
                sub_config.symbol,
                sub_config.timeframe,
                sub_config.maturity,
                sub_config.underlying_asset_type,
                sub_config.display_name,
            )
        return fetcher_class(
            queue, config, auth, client, sub_config.symbol, sub_config.timeframe
        )


class FetcherFactory(FetcherFactoryProtocol):
    def __init__(self):
        self._registry = FetcherRegistry()
        self._register_default_fetchers()

    def _register_default_fetchers(self):
        self._registry.register(DataType.S_CANDLE, StockPriceFetcher)
        self._registry.register(DataType.D_CANDLE, DerivPriceFetcher)
        self._registry.register(DataType.O_CHAIN, OptionChainFetcher)

    def create_fetcher(
        self,
        config: KISConfig,
        auth: KISAuth,
        client: httpx.AsyncClient,
        queue: asyncio.Queue,
        sub_config: SubscriptionConfig,
    ) -> PriceFetcher:
        return self._registry.create_fetcher(config, auth, client, queue, sub_config)

    def register_fetcher(
        self, data_type: DataType, fetcher_class: Type[PriceFetcher]
    ) -> None:
        self._registry.register(data_type, fetcher_class) 