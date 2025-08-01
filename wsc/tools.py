from datetime import datetime, time
from typing import Tuple


def is_market_open() -> bool:
    now = datetime.now()
    current_time = now.time()
    
    if now.weekday() >= 5:
        return False
    
    market_open = time(9, 0)
    market_close = time(15, 30)
    return market_open <= current_time <= market_close


def get_market_status() -> Tuple[str, str]:
    now = datetime.now()
    status = "Open" if is_market_open() else "Closed"
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    return status, time_str


def is_weekend() -> bool:
    return datetime.now().weekday() >= 5


def get_market_info() -> dict:
    now = datetime.now()
    return {
        "is_open": is_market_open(),
        "is_weekend": is_weekend(),
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": now.weekday(),
        "market_hours": "09:00 ~ 15:30 KST"
    }
