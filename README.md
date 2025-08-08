## Korea realtime trading : Trading Data Pipeline & Strategy Engine

Production‑ready system for collecting, processing, and storing Korean market data (futures, options, stocks) with KIS API. Built on asyncio, robust error handling, and a clean, modular architecture.

### Highlights
- Real‑time data feeds for KOSPI/KOSDAQ futures, KOSPI200 options, and stocks
- Strict time policy: all DB writes/comparisons use KST‑naive (TIMESTAMP)
- Dynamic tables per instrument/underlying with safe UPSERT behavior
- Clear separation of concerns: fetchers, core, processing, database, strategies

For full architecture details, see pipeline.md.

---

## Project Layout (src/)
- base.py: KISConfig, KISAuth, setup_logging
- core/: Polling/Feed/Subscriptions (PollingManager, KISDataFeed, SubscriptionManager)
- fetchers/: StockPriceFetcher, DerivPriceFetcher, OptionChainFetcher, FetcherFactory
- processing/: DataProcessor, OptionMatrixProcessor
- database/: DatabaseConnection, DataWriter, schemas
- services/time_service.py: TimeService (KST aware/naive helpers)
- strategies/dolpha1/: Realtime/Historical collectors, verification, signal generation
- consts.py: Constants (market hours, etc.)
- utils.py: is_market_open
- orchestration.py: DataFeedBuilder, DataFeedOrchestrator
- main.py: Entry point for the core data feed

---

## Time & DB Policy (Must‑read)
- All stored/compared timestamps are KST‑naive (datetime with tzinfo=None)
- Any tz‑aware datetime must be normalized via TimeService.to_kst_naive(dt)
- PostgreSQL columns are TIMESTAMP (no time zone)

Example schema
```sql
CREATE TABLE futures_106 (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP NOT NULL,
  symbol VARCHAR(20) NOT NULL,
  open NUMERIC(10,2) NOT NULL,
  high NUMERIC(10,2) NOT NULL,
  low NUMERIC(10,2) NOT NULL,
  close NUMERIC(10,2) NOT NULL,
  volume BIGINT NOT NULL,
  UNIQUE(timestamp, symbol)
);
```

---

## Quick Start
1) Configure credentials and endpoints
   - src/config.json (KIS API base_url, keys, polling interval, tr_id)
   - src/db_config.json (Postgres URL, pool settings)

2) Run (recommended via batch)
   - Core feed: HT_API/run.bat
   - Strategy: HT_API/src/strategies/dolpha1/dolpha1.bat

Alternative
- From repo root: `python -m src.main`
- Or: `cd src && python main.py`

---

## Data Pipeline (Summary)
1) main.py initializes DB and subscriptions → DataFeedOrchestrator.start()
2) PollingManager runs per‑minute+interval fetch cycles
3) fetchers push to a shared queue → DataProcessor
4) Candles are batch‑upserted; option chains are aggregated into matrices and upserted
5) strategies/dolpha1 performs realtime/historical collection, verification, and signal writes

---

## Configuration
- src/config.json
  - base_url, app_key/app_secret, account_no/_sub, polling_interval, tr_id
- src/db_config.json
  - postgres_url, pool_settings (min/max size, server_settings)

See pipeline.md for full examples.

---

## Extensibility
- New fetcher: subclass PriceFetcher → register in FetcherFactory
- New metrics/matrices: extend OptionMatrixProcessor and DataWriter.save_option_matrices
- New strategy: add under strategies/<name> with feeder/signals modules

---

## Troubleshooting
- Error: "can't compare offset‑naive and offset‑aware datetimes"
  - Cause: mixing tz‑aware and naive timestamps
  - Fix: always normalize to KST‑naive via TimeService.to_kst_naive(dt) before comparing or storing

---

## Security
- Keep API keys out of VCS; use config.json only locally or via a secrets manager
- Access tokens are cached in src/access_token.json and auto‑rotated before expiry

---

## License
See LICENSE in this directory.

---

## Further Reading
For a deep dive (architecture diagrams, class responsibilities, runtime sequences, FAQs), read pipeline.md.

