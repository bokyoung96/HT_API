from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import BaseReader
from services.time_service import TimeService


class SignalsReader(BaseReader):
    def __init__(self, db, table_name: str = "dolpha1_signal"):
        super().__init__(db)
        self._table = table_name

    async def fetch_range(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        parts = [
            f"SELECT timestamp, symbol, close, monitor_signal, trade_signal, reason, ub, lb, atr, move_open, sigma_open, vwap, min_from_open",
            f"FROM {self._table}",
            "WHERE symbol = $1",
        ]
        args: List[Any] = [symbol]
        idx = 2

        if start is not None:
            parts.append(f"AND timestamp >= ${idx}")
            args.append(TimeService.to_kst_naive(start))
            idx += 1
        if end is not None:
            parts.append(f"AND timestamp <= ${idx}")
            args.append(TimeService.to_kst_naive(end))
            idx += 1

        parts.append("ORDER BY timestamp ASC")
        if limit is not None:
            parts.append(f"LIMIT {int(limit)}")

        query = " ".join(parts)
        return await self.fetch_all(query, *args)

    async def latest(self, symbol: str) -> Optional[Dict[str, Any]]:
        query = f"""
            SELECT * FROM {self._table}
            WHERE symbol = $1
            ORDER BY timestamp DESC
            LIMIT 1
        """
        return await self.fetch_one(query, symbol)