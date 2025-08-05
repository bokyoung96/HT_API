import asyncio
import logging
from typing import List

from fetchers.base_fetcher import PriceFetcher


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
    def is_running(self) -> bool:
        return self._running

    @property
    def fetch_count(self) -> int:
        return self._fetch_count 