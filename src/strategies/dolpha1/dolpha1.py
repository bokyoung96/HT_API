import asyncio
import logging
import warnings
from datetime import datetime
from typing import Any, Dict

import os
import sys
import httpx

warnings.filterwarnings('ignore', category=UserWarning, module='pandas_market_calendars')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from base import KISAuth, KISConfig, setup_logging
from orchestration import DataFeedBuilder
from database import DatabaseConfig, DatabaseConnection, DataWriter
from feeder import RealTimeDataFeeder
from signals import SignalGenerator, SignalDatabase

class Dolpha1Strategy:
    def __init__(self, symbol: str = "106W09"):
        self.symbol = symbol

        config_path = os.path.join(PROJECT_ROOT, "config.json")
        self.config = KISConfig(config_path=config_path)

        self.feeder = RealTimeDataFeeder(symbol)
        self.signal_generator = SignalGenerator()
        self.signal_database = SignalDatabase()

        self.last_signal_time = None

    async def initialize(self):
        await self.feeder.initialize()
        await self.signal_database.initialize()
        logging.info("🚀 dolpha1 system initialization complete")

    async def start_realtime_feed(self):
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth = KISAuth(self.config, client)
            
            builder = (
                DataFeedBuilder(self.config, auth, client)
                .add_deriv(self.symbol, timeframe=1, name="KOSDAQ150 Futures")
            )
            
            orchestrator = builder.build()
            
            class CustomDataWriter:
                def __init__(self, system):
                    self.system = system
                    
                async def write_derivatives_data(self, data):
                    await self.system.feeder.save_data(data)
                    await self.system._check_signal()
                    
            orchestrator.set_data_writer(CustomDataWriter(self))
            await orchestrator.start()
            
    async def _check_signal(self):
        current_time = datetime.now()
        
        if (self.last_signal_time is None or 
            (current_time - self.last_signal_time).total_seconds() >= 60):
            
            recent_data = await self._get_recent_data()
            if len(recent_data) >= 100:
                signal, reason = self.signal_generator.get_latest_signal(recent_data)
                if signal != 0:
                    latest_row = recent_data.iloc[-1]
                    await self.signal_database.save_signal(
                        latest_row['timestamp'], latest_row['symbol'], 
                        latest_row['close'], signal, reason
                    )
            
            self.last_signal_time = current_time
            
    async def _get_recent_data(self):
        try:
            async with self.feeder.db_connection.pool.acquire() as conn:
                query = f"""
                    SELECT timestamp, symbol, open, high, low, close, volume
                    FROM {self.feeder.table_name}
                    WHERE symbol = $1
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """
                records = await conn.fetch(query, self.symbol)
                
                if records:
                    import pandas as pd
                    df = pd.DataFrame([dict(record) for record in records])
                    return df.sort_values('timestamp').reset_index(drop=True)
                    
        except Exception as e:
            logging.error(f"❌ Failed to retrieve data: {e}")
            
        import pandas as pd
        return pd.DataFrame()
        
    async def close_connections(self):
        await self.feeder.close()
        await self.signal_database.close()

async def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = KISConfig("config.json")
    setup_logging(config.config_dir)

    print(f"""
═══════════════════════════════════════════
            DOLPHA1 SYSTEM                
                                          
  🎯 Target: KOSDAQ150 Futures (106W09)   
  📊 Realtime Data → dolpha1 table        
  🚨 Signal Generation → dolpha1_signal   
                                          
  ⏱️  Current Time: {datetime.now().strftime('%H:%M:%S'):<15}
  📈 Band Breakout Strategy               
═══════════════════════════════════════════
    """)
    
    user_input = input("📅 Do you want to collect historical data first? (y/n): ").lower().strip()
    if user_input == 'y':
        days = input("📅 How many days of data to collect? (default: 15): ").strip()
        days_back = int(days) if days.isdigit() else 15
        
        feeder = RealTimeDataFeeder(symbol="106W09")
        try:
            await feeder.collect_historical_data(days_back=days_back)
            await feeder.verify_historical_data(days_back=days_back)
        finally:
            await feeder.close()
        
        print("━" * 50)
    
    db_config = DatabaseConfig.from_json("db_config.json")
    db_connection = DatabaseConnection(db_config)
    data_writer = DataWriter(db_connection)
    
    await db_connection.initialize()
    print("✅ Database connected")
    print("━" * 50)
    
    system = Dolpha1Strategy(symbol="106W09")
    
    try:
        await system.initialize()
        print("📡 Starting realtime data feed...")
        print("🔄 Press Ctrl+C to exit")
        print("=" * 50)
        
        await system.start_realtime_feed()
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ System error: {e}")
        logging.error(f"System error: {e}", exc_info=True)
    finally:
        await system.close_connections()
        print("👋 System shutdown")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Program terminated")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        print("👋 Goodbye!")