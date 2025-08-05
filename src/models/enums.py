from enum import Enum


class DataType(Enum):
    S_CANDLE = "s_candle"
    D_CANDLE = "d_candle"
    O_CHAIN = "o_chain"


class MarketType(Enum):
    STOCK = "stock"
    DERIVATIVES = "derivatives" 