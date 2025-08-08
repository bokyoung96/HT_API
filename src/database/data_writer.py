import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

from database.connection import DatabaseConnection
from services.time_service import TimeService


class DataWriter:
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self.batch_queue: asyncio.Queue = asyncio.Queue()
        self.batch_size = 1
        self.batch_timeout = 1.0
        self.created_tables = set()
        
    async def save_candle_data(self, candle_data: Dict[str, Any]) -> None:
        await self.batch_queue.put(candle_data)
        
    async def save_option_chain_data(self, option_data: Dict[str, Any]) -> None:
        return
        
    async def save_option_matrices(self, matrix_data: Dict[str, Any]) -> None:
        dt = datetime.fromisoformat(matrix_data["timestamp"])
        timestamp = TimeService.to_kst_naive(dt)
        underlying_symbol = matrix_data["underlying_symbol"]
        
        table_key = f"option_matrices_{underlying_symbol.lower()}"
        if table_key not in self.created_tables:
            await self.db.create_dynamic_table("option_matrices", underlying_symbol)
            self.created_tables.add(table_key)
        
        table_name = f"option_matrices_{underlying_symbol.lower()}"
        
        for metric_type in ["iv", "delta", "gamma", "vega", "theta", "rho", "price", "volume", "open_interest"]:
            metric_values = matrix_data.get(metric_type, {})
            if not metric_values:
                continue
                
            columns = ["timestamp", "underlying_symbol", "metric_type"]
            values = [timestamp, underlying_symbol, metric_type]
            placeholders = ["$1", "$2", "$3"]
            placeholder_idx = 4
            
            for option_type in ["c", "p"]:
                for strike_level in ["itm10", "itm9", "itm8", "itm7", "itm6", "itm5", "itm4", "itm3", "itm2", "itm1",
                                   "atm", "otm1", "otm2", "otm3", "otm4", "otm5", "otm6", "otm7", "otm8", "otm9", "otm10"]:
                    col_name = f"{option_type}_{strike_level}"
                    value = metric_values.get(option_type, {}).get(strike_level)
                    if value is not None:
                        columns.append(col_name)
                        values.append(value)
                        placeholders.append(f"${placeholder_idx}")
                        placeholder_idx += 1
                        
            if len(columns) > 3:
                query = f"""
                    INSERT INTO {table_name} ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    ON CONFLICT (timestamp, underlying_symbol, metric_type) DO UPDATE SET
                    {', '.join([f"{col} = EXCLUDED.{col}" for col in columns[3:]])}
                """
                
                await self.db.execute_query(query, *values)
            
        logging.info(f"✅ Saved option matrices for {underlying_symbol} to {table_name}")
        
    async def start_batch_writer(self) -> None:
        while True:
            batch = []
            deadline = asyncio.create_task(asyncio.sleep(self.batch_timeout))
            
            while len(batch) < self.batch_size:
                try:
                    get_task = asyncio.create_task(self.batch_queue.get())
                    done, pending = await asyncio.wait(
                        {get_task, deadline},
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    if get_task in done:
                        data = await get_task
                        batch.append(data)
                        if not deadline.done():
                            deadline.cancel()
                    else:
                        get_task.cancel()
                        break
                        
                except Exception as e:
                    logging.error(f"Error in batch collection: {e}")
                    break
                    
            if batch:
                await self._write_batch(batch)
                
    async def _write_batch(self, batch: List[Dict[str, Any]]) -> None:
        futures_by_symbol = {}
        stocks_data = []
        
        for data in batch:
            if "candle" in data.get("type", ""):
                symbol = data["symbol"]
                
                if symbol.startswith("1"):  # Futures
                    if symbol not in futures_by_symbol:
                        futures_by_symbol[symbol] = []
                    futures_by_symbol[symbol].append(data)
                else:  # Stocks
                    stocks_data.append(data)
                    
        for symbol, symbol_data in futures_by_symbol.items():
            table_name_suffix = symbol[:3].lower()
            table_key = f"futures_{table_name_suffix}"
            if table_key not in self.created_tables:
                await self.db.create_dynamic_table("futures", symbol)
                self.created_tables.add(table_key)
            
            table_name = f"futures_{table_name_suffix}"
            await self._bulk_insert_candles(table_name, symbol_data)
            
        if stocks_data:
            await self._bulk_insert_candles("stocks_1m", stocks_data)
            
    async def _bulk_insert_candles(self, table_name: str, candles: List[Dict[str, Any]]) -> None:
        if not candles:
            return
            
        query = f"""
            INSERT INTO {table_name} (timestamp, symbol, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (timestamp, symbol) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """
        
        params_list = []
        for candle in candles:
            params = (
                TimeService.to_kst_naive(datetime.fromisoformat(candle["timestamp"])) if isinstance(candle["timestamp"], str) else candle["timestamp"],
                candle["symbol"],
                candle["open"],
                candle["high"],
                candle["low"],
                candle["close"],
                candle["volume"]
            )
            params_list.append(params)
            
        async with self.db.pool.acquire() as conn:
            await conn.executemany(query, params_list)
            
        logging.info(f"✅ Saved {len(candles)} records to {table_name}")
        
    async def log_system_status(self, component: str, status: str, message: str = None, data_count: int = 0) -> None:
        query = """
            INSERT INTO system_status (component, status, message, data_count, last_data_time)
            VALUES ($1, $2, $3, $4, NOW())
        """
        
        await self.db.execute_query(query, component, status, message, data_count)