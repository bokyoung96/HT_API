import asyncio
import logging
import warnings
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
import os
import sys
import httpx
import pandas as pd
import pandas_market_calendars as mcal

warnings.filterwarnings('ignore', category=UserWarning, module='pandas_market_calendars')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from base import KISAuth, KISConfig
from database.connection import DatabaseConnection
from database.config import DatabaseConfig

class RealTimeDataFeeder:
    def __init__(self, symbol: str = "106W09", table_name: str = "dolpha1"):
        self.symbol = symbol
        self.table_name = table_name
        
        config_path = os.path.join(PROJECT_ROOT, "config.json")
        self.config = KISConfig(config_path=config_path)
        
        db_config_path = os.path.join(PROJECT_ROOT, "db_config.json")
        db_config = DatabaseConfig.from_json(config_path=db_config_path)
        self.db_connection = DatabaseConnection(db_config)
        
    async def initialize(self):
        if not self.db_connection.pool:
            await self.db_connection.initialize()
        await self._ensure_table_exists()
        
    async def _ensure_table_exists(self):
        try:
            async with self.db_connection.pool.acquire() as conn:
                table_sql = f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    timestamp TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume BIGINT,
                    PRIMARY KEY (timestamp, symbol)
                );
                """
                await conn.execute(table_sql)
                logging.info(f"✅ {self.table_name} table ready")
        except Exception as e:
            logging.error(f"❌ Failed to create table: {e}")
            raise
            
    async def save_data(self, candle_data: Dict[str, Any]):
        try:
            async with self.db_connection.pool.acquire() as conn:
                await conn.execute(f"""
                    INSERT INTO {self.table_name} (timestamp, symbol, open, high, low, close, volume)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (timestamp, symbol) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                        close = EXCLUDED.close, volume = EXCLUDED.volume;
                """, [
                    candle_data['timestamp'], candle_data['symbol'], candle_data['open'],
                    candle_data['high'], candle_data['low'], candle_data['close'], candle_data['volume']
                ])
            logging.debug(f"💾 Data saved: {candle_data['close']}")
        except Exception as e:
            logging.error(f"❌ Failed to save data: {e}")
            
    def get_trading_days(self, days_back: int = 30) -> List[str]:
        krx = mcal.get_calendar("XKRX")
        end_date = datetime.now(timezone(timedelta(hours=9)))
        start_date = end_date - timedelta(days=days_back * 2)

        schedule = krx.schedule(start_date=start_date.date(), end_date=end_date.date())
        trading_days = schedule[schedule.index < pd.to_datetime(end_date.date())].index[-days_back:]

        return [day.strftime("%Y%m%d") for day in trading_days]

    async def fetch_day_data(self, date_str: str) -> List[Dict[str, Any]]:
        all_candles = []
        url = f"{self.config.base_url}/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"

        async with httpx.AsyncClient(timeout=10.0) as client:
            auth = KISAuth(self.config, client)
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {await auth.get_access_token()}",
                "appKey": self.config.app_key,
                "appSecret": self.config.app_secret,
                "tr_id": self.config.deriv_minute_tr_id,
            }
            
            next_query_time = "154500"
            market_start_dt = datetime.strptime(f"{date_str}084500", "%Y%m%d%H%M%S")

            for _ in range(10): 
                params = {
                    "fid_cond_mrkt_div_code": "F", "fid_input_iscd": self.symbol, "fid_hour_cls_code": "60",
                    "fid_pw_data_incu_yn": "Y", "fid_fake_tick_incu_yn": "N", "fid_input_date_1": date_str,
                    "fid_input_hour_1": next_query_time,
                }

                response_data = None
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.get(url, headers=headers, params=params)
                        response.raise_for_status()
                        response_data = response.json()
                        break
                    except (httpx.RequestError, httpx.HTTPStatusError) as e:
                        logging.warning(f"❌ Retry {attempt + 1}/{max_retries} for {next_query_time}: {e}")
                        if attempt + 1 == max_retries:
                            logging.error(f"❌ {date_str} {next_query_time} failed")
                            return []
                        await asyncio.sleep(1)

                if not response_data or response_data.get("rt_cd") != "0" or not response_data.get("output2"):
                    logging.info(f"📊 Data collection complete from {date_str} {next_query_time}")
                    break

                candles = response_data["output2"]
                all_candles.extend(candles)
                logging.info(f"📊 {len(candles)} candles collected")

                earliest_candle = candles[-1]
                earliest_time_str = earliest_candle.get("stck_cntg_hour")
                earliest_dt = datetime.strptime(f"{date_str}{earliest_time_str}", "%Y%m%d%H%M%S")

                if earliest_dt <= market_start_dt:
                    logging.info(f"✅ {date_str} Market start time reached")
                    break
                
                next_query_time = earliest_time_str
                await asyncio.sleep(0.2)

        if all_candles:
            df = pd.DataFrame(all_candles)
            df_unique = df.drop_duplicates(subset=['stck_bsop_date', 'stck_cntg_hour'])
            unique_candles = df_unique.to_dict('records')
            logging.info(f"📈 {date_str}: Total {len(unique_candles)} unique candles")
            return unique_candles

        return []

    def process_candles(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records = []
        kst = timezone(timedelta(hours=9))

        for candle in candles:
            try:
                date_str = candle.get("stck_bsop_date")
                time_str = candle.get("stck_cntg_hour")
                if not date_str or not time_str: 
                    continue

                raw_dt_obj = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                raw_hour_min = raw_dt_obj.hour * 100 + raw_dt_obj.minute

                if not (845 <= raw_hour_min <= 1545): 
                    continue

                if raw_hour_min == 1545:
                    final_dt_obj = raw_dt_obj
                else:
                    final_dt_obj = raw_dt_obj + timedelta(minutes=1)

                timestamp_kst = final_dt_obj.replace(tzinfo=kst)
                record = {
                    "timestamp": timestamp_kst, 
                    "symbol": self.symbol,
                    "open": float(candle.get("futs_oprc", 0)), 
                    "high": float(candle.get("futs_hgpr", 0)),
                    "low": float(candle.get("futs_lwpr", 0)), 
                    "close": float(candle.get("futs_prpr", 0)),
                    "volume": int(candle.get("cntg_vol", 0)),
                }
                records.append(record)
            except (ValueError, TypeError, KeyError) as e:
                logging.warning(f"⚠️ Failed to process candle: {e}")
                continue
        return records

    async def save_historical_records(self, records: List[Dict[str, Any]]):
        if not records: 
            return
        try:
            async with self.db_connection.pool.acquire() as conn:
                await conn.executemany(f"""
                    INSERT INTO {self.table_name} (timestamp, symbol, open, high, low, close, volume)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (timestamp, symbol) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                        close = EXCLUDED.close, volume = EXCLUDED.volume;
                """, [(r['timestamp'], r['symbol'], r['open'], r['high'], r['low'], r['close'], r['volume']) for r in records])
            logging.info(f"💾 {len(records)} historical records saved")
        except Exception as e:
            logging.error(f"❌ Failed to save historical data: {e}")
            raise

    async def collect_historical_data(self, days_back: int = 15):
        await self.initialize()
        trading_days = self.get_trading_days(days_back)
        logging.info(f"📅 Starting {len(trading_days)} days historical data collection: {trading_days}")
        
        total_records = 0
        for i, date_str in enumerate(trading_days, 1):
            logging.info(f"📅 [{i}/{len(trading_days)}] Processing {date_str}...")
            try:
                raw_candles = await self.fetch_day_data(date_str)
                if not raw_candles:
                    logging.warning(f"⚠️ {date_str} No data")
                    continue
                    
                processed_records = self.process_candles(raw_candles)
                if processed_records:
                    await self.save_historical_records(processed_records)
                    total_records += len(processed_records)
                    logging.info(f"✅ {date_str}: {len(processed_records)} saved (total: {total_records})")
                else:
                    logging.warning(f"⚠️ {date_str}: No processed data")
            except Exception as e:
                logging.error(f"❌ {date_str} Processing failed: {e}")
                continue
                
        logging.info(f"🎉 Historical data collection complete! Total {total_records} records saved")

    async def verify_historical_data(self, days_back: int = 15):
        logging.info("🔍 Starting data verification...")
        trading_days_set = set(self.get_trading_days(days_back))
        all_days_ok = True
        
        expected_count_per_day = 411  # 08:45 ~ 15:45, 1-minute candles

        try:
            async with self.db_connection.pool.acquire() as conn:
                query = f"""
                    SELECT DATE(timestamp AT TIME ZONE 'Asia/Seoul') as trade_date, COUNT(*) as record_count
                    FROM {self.table_name} GROUP BY trade_date ORDER BY trade_date;
                """
                daily_counts = await conn.fetch(query)
                db_days_set = {rec['trade_date'].strftime("%Y%m%d") for rec in daily_counts}
                
                missing_days = trading_days_set - db_days_set
                if missing_days:
                    all_days_ok = False
                    for day in sorted(list(missing_days)):
                        logging.error(f"❌ {day}: Missing from database!")
                        
                for record in daily_counts:
                    date_str = record['trade_date'].strftime("%Y%m%d")
                    count = record['record_count']
                    if count == expected_count_per_day:
                        logging.info(f"✅ {date_str}: OK ({count}/{expected_count_per_day})")
                    else:
                        all_days_ok = False
                        logging.warning(f"❌ {date_str}: Incomplete! ({count}/{expected_count_per_day})")
                        
            if all_days_ok:
                logging.info("🎉 Verification successful! All data complete")
            else:
                logging.error("❌ Verification failed! Some data missing")
        except Exception as e:
            logging.error(f"❌ Error during verification: {e}")

    async def close(self):
        if self.db_connection.pool:
            await self.db_connection.close()