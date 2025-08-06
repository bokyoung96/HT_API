from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional
import logging

from processing.processors import CandleProcessor
from utils import is_market_open

if TYPE_CHECKING:
    import httpx
    from base import KISAuth, KISConfig
    from models.dataclasses import CandleData
    from models.enums import MarketType


class PriceFetcher(ABC):
    def __init__(
        self,
        queue: asyncio.Queue,
        config: KISConfig,
        auth: KISAuth,
        client: httpx.AsyncClient,
        symbol: str,
        timeframe: int,
        market_type: MarketType,
    ):
        self.queue = queue
        self.config = config
        self.auth = auth
        self.client = client
        self.symbol = symbol
        self.timeframe = timeframe
        self.market_type = market_type
        self._candle_processor = CandleProcessor(symbol, timeframe, queue)

    @abstractmethod
    async def fetch_data(self) -> Dict[str, Any]:
        pass

    async def get_headers(self) -> Dict[str, str]:
        token = await self.auth.get_access_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "appKey": self.config.app_key,
            "appSecret": self.config.app_secret,
        }

    def is_trading_hours(self) -> bool:
        return is_market_open(self.market_type)

    async def _handle_candle_data(
        self,
        current_time: Optional[str],
        completed_candle: Optional[Dict],
        log_format: str,
    ) -> Dict[str, Any]:
        
        processed_candle_data = await self._candle_processor.process_candle_data(
            current_time, completed_candle, log_format, self._process_candle_data
        )

        return processed_candle_data

    @abstractmethod
    def _process_candle_data(self, candle: Dict) -> Optional[CandleData]:
        pass 