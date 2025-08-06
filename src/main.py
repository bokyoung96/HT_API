import asyncio
import logging
from datetime import datetime

import httpx
from base import KISAuth, KISConfig, setup_logging
from orchestration import DataFeedBuilder
from database import DatabaseConfig, DatabaseConnection, DataWriter


async def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = KISConfig("config.json")

    setup_logging(config.config_dir)

    print(f"🕐 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️ Polling interval: {config.polling_interval} seconds")
    print("🏢 Stock market hours: 09:00 ~ 15:30")
    print("📈 Derivatives market hours: 08:45 ~ 15:45")
    print("━" * 50)
    
    db_config = DatabaseConfig.from_json("db_config.json")
    db_connection = DatabaseConnection(db_config)
    data_writer = DataWriter(db_connection)
    
    await db_connection.initialize()
    print("✅ Database connected")
    print("━" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        auth = KISAuth(config, client)

        builder = (
            DataFeedBuilder(config, auth, client)
            # .add_stock("005930", timeframe=1, name="Samsung Electronics")
            # .add_deriv("101W09", timeframe=1, name="KOSPI200 Futures")
            .add_deriv("106W09", timeframe=1, name="KOSDAQ150 Futures")
            .add_option_chain(
                maturity="202509",
                underlying_asset_type="",
                name="KOSPI200_Monthly_Options",
            )
        )

        builder.show_subscriptions()
        print("━" * 50)

        orchestrator = builder.build()
        orchestrator.set_data_writer(data_writer)
        
        await orchestrator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Program terminated by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("👋 Goodbye!")
