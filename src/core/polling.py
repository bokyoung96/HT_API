import asyncio
import logging
from datetime import datetime
from services.time_service import TimeService
from typing import List, Any

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
            now = TimeService.now_kst_naive()
            wait_seconds = (
                60.0 - now.second - (now.microsecond / 1_000_000)
            ) + self._interval
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            try:
                results = await self._execute_fetch_cycle(self._fetchers)

                failed_fetchers = [
                    fetcher
                    for fetcher, result in zip(self._fetchers, results)
                    if not result or isinstance(result, Exception)
                ]

                if failed_fetchers:
                    for i in range(10):
                        sleep_time = 2.0 + (i * 0.3) if i < 5 else 4.0
                        logging.warning(
                            f"🔄 Retrying after {sleep_time:.1f}s for {len(failed_fetchers)} failed symbols... (Attempt {i+1}/10)"
                        )
                        await asyncio.sleep(sleep_time)
                        results = await self._execute_fetch_cycle(failed_fetchers)
                        
                        failed_fetchers = [
                            fetcher
                            for fetcher, result in zip(failed_fetchers, results)
                            if not result or isinstance(result, Exception)
                        ]

                        if not failed_fetchers:
                            logging.info(f"✅ All fetchers recovered after {i+1} attempts")
                            break
                    
                    if failed_fetchers:
                        failed_symbols = [f.symbol for f in failed_fetchers]
                        logging.error(f"❌ {len(failed_fetchers)} fetchers still failing after 10 attempts: {failed_symbols}")

            except Exception as e:
                logging.error(
                    f"An unexpected error occurred in the polling loop: {e}"
                )

    async def _execute_fetch_cycle(
        self, fetchers_to_process: List[PriceFetcher]
    ) -> List[Any]:
        results = []
        if not fetchers_to_process:
            return results

        for fetcher in fetchers_to_process:
            try:
                result = await fetcher.fetch_data()
                results.append(result)
            except Exception as e:
                logging.error(
                    f"Failed to fetch data for symbol '{fetcher.symbol}': {e}"
                )
                results.append(e)
            finally:
                await asyncio.sleep(0.5)

        self._fetch_count += len(fetchers_to_process)
        if self._fetch_count > 0 and self._fetch_count % 20 == 0:
            logging.debug(f"Completed {self._fetch_count} total fetches.")

        return results

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def fetch_count(self) -> int:
        return self._fetch_count
