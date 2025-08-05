import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from base import KISAuth, KISConfig
from fetchers.base_fetcher import PriceFetcher
from models.dataclasses import CandleData
from models.enums import MarketType


class DerivPriceFetcher(PriceFetcher):
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
            queue, config, auth, client, symbol, timeframe, MarketType.DERIVATIVES
        )

    def _select_completed_candle(
        self, candles: List[Dict], current_time: str
    ) -> Optional[Dict]:
        if len(candles) < 1:
            return None
        if current_time.startswith("1545"):
            return candles[0]
        return candles[1] if len(candles) > 1 else candles[0]

    async def fetch_data(self) -> Dict[str, Any]:
        if not self.is_trading_hours():
            logging.debug(f"Outside trading hours for derivatives {self.symbol}")
            return {}

        url = f"{self.config.base_url}/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
        headers = await self.get_headers()
        headers["tr_id"] = self.config.deriv_minute_tr_id

        query_time = datetime.now().strftime("%H%M%S")

        params = {
            "fid_cond_mrkt_div_code": "F",
            "fid_input_iscd": self.symbol,
            "fid_hour_cls_code": "60",
            "fid_pw_data_incu_yn": "Y",
            "fid_fake_tick_incu_yn": "N",
            "fid_input_date_1": "",
            "fid_input_hour_1": query_time,
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

        completed_time = completed_candle.get("stck_cntg_hour")

        log_format = "🕐 [{symbol}] {timeframe}m: OHLCV {open:.2f}/{high:.2f}/{low:.2f}/{close:.2f} Vol: {volume:,}"
        return await self._handle_candle_data(completed_time, completed_candle, log_format)

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
            data_type="d",
        ) 