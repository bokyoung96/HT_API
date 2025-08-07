import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import httpx
from base import KISAuth, KISConfig
from fetchers.base_fetcher import PriceFetcher
from models.dataclasses import CandleData, OptionChainData, OptionData
from models.enums import MarketType


class OptionChainFetcher(PriceFetcher):
    def __init__(
        self,
        queue: asyncio.Queue,
        config: KISConfig,
        auth: KISAuth,
        client: httpx.AsyncClient,
        symbol: str,
        timeframe: int,
        maturity: Optional[str],
        underlying_asset_type: Optional[str],
        display_name: Optional[str] = None,
    ):
        super().__init__(
            queue, config, auth, client, symbol, timeframe, MarketType.DERIVATIVES
        )
        self.maturity = maturity
        self.underlying_asset_type = underlying_asset_type
        self.display_name = display_name
        self._last_fetch_minute: Optional[str] = None

    async def fetch_data(self) -> Dict[str, Any]:
        if not self.is_trading_hours():
            logging.debug(
                f"Outside trading hours for options {self.symbol or self.underlying_asset_type}"
            )
            return {}

        current_minute = datetime.now().strftime("%H%M")
        if self._last_fetch_minute == current_minute:
            return {}
        
        self._last_fetch_minute = current_minute

        url = f"{self.config.base_url}/uapi/domestic-futureoption/v1/quotations/display-board-callput"
        headers = await self.get_headers()
        headers["tr_id"] = self.config.option_chain_tr_id

        params = {
            "fid_cond_mrkt_div_code": "O",
            "fid_cond_scr_div_code": "20503",
            "fid_mrkt_cls_code": "CO",
            "fid_mtrt_cnt": self.maturity,
            "fid_cond_mrkt_cls_code": self.underlying_asset_type,
            "fid_mrkt_cls_code1": "PO",
        }

        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("rt_cd") != "0":
            logging.error(
                f"Error fetching option chain for {self.symbol}: {data.get('msg1')}"
            )
            return {}

        calls_raw = data.get("output1", [])
        puts_raw = data.get("output2", [])

        if not calls_raw and not puts_raw:
            return {}

        underlying_price_source = calls_raw[0] if calls_raw else puts_raw[0]
        underlying_price = float(underlying_price_source.get("unch_prpr", 0.0))

        calls = [self._process_option_data(o) for o in calls_raw]
        puts = [self._process_option_data(o) for o in puts_raw]

        underlying_symbol = f"{self.maturity}_KOSPI200" if self.maturity else "unknown"
        
        chain_data = OptionChainData(
            timestamp=datetime.now(),
            underlying_symbol=underlying_symbol,
            underlying_price=underlying_price,
            calls=[c for c in calls if c],
            puts=[p for p in puts if p],
        )

        processed_data = chain_data.to_dict()
        await self.queue.put(processed_data)
        logging.info(
            f"📈 Fetched option chain for {self.underlying_asset_type}: {len(chain_data.calls)} calls, {len(chain_data.puts)} puts."
        )
        return processed_data

    def _process_option_data(self, option: Dict) -> Optional[OptionData]:
        if not option:
            return None

        return OptionData(
            symbol=option.get("optn_shrn_iscd", ""),
            atm_class=option.get("atm_cls_name", ""),
            strike_price=float(option.get("acpr", 0)),
            price=float(option.get("optn_prpr", 0)),
            iv=float(option.get("hts_ints_vltl", 0)),
            delta=float(option.get("delta_val", 0)),
            gamma=float(option.get("gama", 0)),
            vega=float(option.get("vega", 0)),
            theta=float(option.get("theta", 0)),
            rho=float(option.get("rho", 0)),
            volume=int(option.get("acml_vol", 0)),
            open_interest=int(option.get("hts_otst_stpl_qty", 0)),
        )

    def _process_candle_data(self, candle: Dict) -> Optional[CandleData]:
        return None 