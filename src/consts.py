from datetime import time


class Constants:
    MARKET_HOURS_STOCK_START: time = time(9, 0)
    MARKET_HOURS_STOCK_END: time = time(15, 32)

    MARKET_HOURS_DERIV_START: time = time(8, 45)
    MARKET_HOURS_DERIV_END: time = time(15, 47)

    EXPECTED_CANDLES_PER_DAY: int = 411

    MAX_RETRIES_DEFAULT: int = 3
    RETRY_SLEEP_BASE_SECONDS: float = 1.0