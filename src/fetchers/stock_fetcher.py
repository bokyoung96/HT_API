import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from base import KISAuth, KISConfig
from fetchers.base_fetcher import PriceFetcher
from models.dataclasses import CandleData
from models.enums import MarketType


class StockPriceFetcher(PriceFetcher):
    def __init__(
        self,
        queue: asyncio.Queue,
        config: KISConfig,
        auth: KISAuth,
        client: httpx.AsyncClient,
        symbol: str,
        timeframe: int,
    ):
        super().__init__(
            queue, config, auth, client, symbol, timeframe, MarketType.STOCK
        )

    def _select_completed_candle(
        self, candles: List[Dict], current_time: str
    ) -> Optional[Dict]:
        if len(candles) < 1:
            return None
        if current_time.startswith("1530"):
            return candles[0]
        return candles[1] if len(candles) > 1 else candles[0]

    async def fetch_data(self) -> Dict[str, Any]:
        if not self.is_trading_hours():
            logging.debug(f"Outside trading hours for stock {self.symbol}")
            return {}

        url = f"{self.config.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        headers = await self.get_headers()
        headers["tr_id"] = self.config.stock_minute_tr_id

        query_time = datetime.now().strftime("%H%M%S")

        params = {
            "fid_etc_cls_code": "",
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": self.symbol,
            "fid_input_hour_1": query_time,
            "fid_pw_data_incu_yn": "Y",
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

        log_format = "🕐 [{symbol}] {timeframe}m: OHLCV {open:.0f}/{high:.0f}/{low:.0f}/{close:.0f} Vol: {volume:,}"
        return await self._handle_candle_data(current_time, completed_candle, log_format)

    def _process_candle_data(self, candle: Dict) -> Optional[CandleData]:
        if not candle:
            return None

        base_timestamp = datetime.now().replace(second=0, microsecond=0)
        
        current_time = base_timestamp.strftime("%H%M")
        if current_time != "1530":
            base_timestamp += timedelta(minutes=1)

        return CandleData(
            symbol=self.symbol,
            timestamp=base_timestamp,
            timeframe=self.timeframe,
            open=int(candle.get("stck_oprc", 0)),
            high=int(candle.get("stck_hgpr", 0)),
            low=int(candle.get("stck_lwpr", 0)),
            close=int(candle.get("stck_prpr", 0)),
            volume=int(candle.get("cntg_vol", 0)),
            data_type="s",
        ) 