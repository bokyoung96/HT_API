import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

from .order import OrderInterface


class StrategyInterface(ABC):
    @abstractmethod
    async def process_event(self, event: Dict[str, Any]):
        pass


class TradingStrategy(StrategyInterface):
    def __init__(self, queue: asyncio.Queue, trader: OrderInterface, target_stock: str):
        self.queue = queue
        self.trader = trader
        self.target_stock = target_stock
        self.has_position = False

    async def process_event(self, event: Dict[str, Any]):
        if event.get("type") == "price" and event.get("code") == self.target_stock:
            if not self.has_position and event['price'] <= 70000:
                logging.info(f"Buy condition met for {self.target_stock}. Placing order.")
                await self.trader.place_order(self.target_stock, "02", 1)
                self.has_position = True

    async def run(self):
        logging.info("💡 Trading strategy engine started.")
        while True:
            event = await self.queue.get()
            logging.debug(f"Strategy received event: {event}")
            await self.process_event(event) 