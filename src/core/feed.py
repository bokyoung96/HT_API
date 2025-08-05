import asyncio
import logging
from typing import List

from base import KISAuth, KISConfig
from core.polling import PollingManager
from fetchers.base_fetcher import PriceFetcher
from protocols import DataFeed


class KISDataFeed(DataFeed):
    def __init__(
        self, config: KISConfig, auth: KISAuth, fetchers: List[PriceFetcher]
    ):
        self._config = config
        self._auth = auth
        self._fetchers = fetchers
        self._queue = asyncio.Queue()
        self._polling_manager = PollingManager(config.polling_interval, fetchers)

    async def start_feed(self) -> None:
        if self._polling_manager.is_running:
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
        return self._polling_manager.is_running

    @property
    def fetch_count(self) -> int:
        return self._polling_manager.fetch_count 