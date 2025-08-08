from datetime import time
from models.enums import MarketType
from consts import Constants
from services.time_service import TimeService


def is_market_open(market_type: MarketType) -> bool:
    now_kst = TimeService.now_kst_naive().time()

    if market_type == MarketType.STOCK:
        return Constants.MARKET_HOURS_STOCK_START <= now_kst <= Constants.MARKET_HOURS_STOCK_END
    elif market_type == MarketType.DERIVATIVES:
        return Constants.MARKET_HOURS_DERIV_START <= now_kst <= Constants.MARKET_HOURS_DERIV_END

    return False