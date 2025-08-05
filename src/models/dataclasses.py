from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.enums import DataType


@dataclass
class CandleData:
    symbol: str
    timestamp: datetime
    timeframe: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    data_type: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "timeframe": f"{self.timeframe}m",
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "type": f"{self.data_type}_candle",
        }


@dataclass
class OptionData:
    symbol: str
    atm_class: str
    strike_price: float
    price: float
    iv: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    volume: int
    open_interest: int

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class OptionChainData:
    timestamp: datetime
    underlying_symbol: str
    underlying_price: float
    calls: List[OptionData]
    puts: List[OptionData]
    data_type: str = "option_chain"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "underlying_symbol": self.underlying_symbol,
            "underlying_price": self.underlying_price,
            "calls": [c.to_dict() for c in self.calls],
            "puts": [p.to_dict() for p in self.puts],
            "type": self.data_type,
        }


@dataclass
class SubscriptionConfig:
    data_type: DataType
    symbol: str
    timeframe: int = 1
    display_name: Optional[str] = None
    maturity: Optional[str] = None
    underlying_asset_type: Optional[str] = None 