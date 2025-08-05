import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from models.dataclasses import CandleData, OptionChainData, OptionData
from processing.matrix_processor import OptionMatrixProcessor
from protocols import DataProcessor as DataProcessorProtocol


class CandleProcessor:
    def __init__(self, symbol: str, timeframe: int, queue: asyncio.Queue):
        self.symbol = symbol
        self.timeframe = timeframe
        self.queue = queue
        self._last_processed_time: Optional[str] = None

    async def process_candle_data(
        self,
        current_time: Optional[str],
        completed_candle: Optional[Dict],
        log_format: str,
        process_func: Callable[[Dict], Optional[CandleData]],
    ) -> Dict[str, Any]:
        if not current_time or not completed_candle:
            return {}

        if self._last_processed_time and self._last_processed_time >= current_time:
            return {}

        if not self._last_processed_time:
            print(f"⏳ [{self.symbol}] First run - processing first available candle...")
        else:
            print(f"📊 [{self.symbol}] Processing new candle: {current_time}")
        
        self._last_processed_time = current_time

        processed_candle = process_func(completed_candle)
        if not processed_candle:
            return {}

        candle_data = processed_candle.to_dict()
        log_message = log_format.format(
            symbol=self.symbol,
            timeframe=self.timeframe,
            open=processed_candle.open,
            high=processed_candle.high,
            low=processed_candle.low,
            close=processed_candle.close,
            volume=processed_candle.volume,
        )
        logging.info(log_message)
        print(log_message)
        
        await self.queue.put(candle_data)
        return candle_data


class DataProcessor(DataProcessorProtocol):
    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._processed_count = 0
        self._matrix_processor = OptionMatrixProcessor(
            metrics=[
                "iv",
                "delta",
                "gamma",
                "theta",
                "vega",
                "price",
                "volume",
                "open_interest",
            ],
            num_strikes=10,
        )

    async def process_data(self) -> None:
        while True:
            try:
                data = await self._queue.get()
                if data.get("type") == "option_chain":
                    self._process_option_chain(data)
                else:
                    await self._process_single_data(data)
                self._processed_count += 1
                self._queue.task_done()
            except Exception as e:
                logging.error(f"Error processing data: {e}")

    def _process_option_chain(self, data: Dict[str, Any]) -> None:
        try:
            calls = [OptionData(**c) for c in data["calls"]]
            puts = [OptionData(**p) for p in data["puts"]]

            chain_data = OptionChainData(
                timestamp=datetime.fromisoformat(data["timestamp"]),
                underlying_symbol=data["underlying_symbol"],
                underlying_price=data["underlying_price"],
                calls=calls,
                puts=puts,
            )
            self._matrix_processor.update(chain_data)
        except Exception as e:
            logging.error(f"Failed to process and update option matrix: {e}")

    def _process_option_chain_summary(self, data: Dict[str, Any]) -> None:
        symbol = data.get("underlying_symbol")
        price = data.get("underlying_price")

        otm_calls = [c for c in data["calls"] if c["atm_class"] == "OTM"]
        atm_calls = [c for c in data["calls"] if c["atm_class"] == "ATM"]
        itm_calls = [c for c in data["calls"] if c["atm_class"] == "ITM"]

        otm_puts = [p for p in data["puts"] if p["atm_class"] == "OTM"]
        atm_puts = [p for p in data["puts"] if p["atm_class"] == "ATM"]
        itm_puts = [p for p in data["puts"] if p["atm_class"] == "ITM"]

        info_str = (
            f"⛓️ Option Chain for {symbol} @ {price:.2f} | "
            f"Calls (OTM/ATM/ITM): {len(otm_calls)}/{len(atm_calls)}/{len(itm_calls)} | "
            f"Puts (OTM/ATM/ITM): {len(otm_puts)}/{len(atm_puts)}/{len(itm_puts)}"
        )
        logging.info(info_str)

    async def _process_single_data(self, data: Dict[str, Any]) -> None:
        data_type = data.get("type", "unknown")
        symbol = data.get("symbol", "unknown")
        timestamp = data.get("timestamp", "")

        logging.debug(f"📦 Processing {data_type} data for {symbol} at {timestamp}")

    @property
    def processed_count(self) -> int:
        return self._processed_count 