from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, List, Protocol

if TYPE_CHECKING:
    import httpx
    from base import KISConfig, KISAuth
    from models.dataclasses import SubscriptionConfig
    from fetchers.base_fetcher import PriceFetcher


class SubscriptionManager(Protocol):
    def add_subscription(self, config: SubscriptionConfig) -> None: ...
    def get_subscriptions(self) -> List[SubscriptionConfig]: ...
    def clear_subscriptions(self) -> None: ...


class FetcherFactory(Protocol):
    def create_fetcher(
        self,
        config: KISConfig,
        auth: KISAuth,
        client: httpx.AsyncClient,
        queue: asyncio.Queue,
        sub_config: SubscriptionConfig,
    ) -> "PriceFetcher": ...


class DataFeed(Protocol):
    async def start_feed(self) -> None: ...

    @property
    def is_running(self) -> bool: ...

    @property
    def fetch_count(self) -> int: ...


class DataProcessor(Protocol):
    async def process_data(self) -> None: ...

    @property
    def processed_count(self) -> int: ... 