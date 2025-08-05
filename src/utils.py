from datetime import datetime, time
from models.enums import MarketType


def is_market_open(market_type: MarketType) -> bool:
    now = datetime.now().time()

    if market_type == MarketType.STOCK:
        return time(9, 0) <= now <= time(15, 30)
    elif market_type == MarketType.DERIVATIVES:
        return time(8, 45) <= now <= time(15, 45)

    return False 