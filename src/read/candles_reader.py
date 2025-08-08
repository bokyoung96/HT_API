from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import BaseReader
from services.time_service import TimeService


class CandlesReader(BaseReader):
    async def fetch_range(
        self,
        table: str,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        parts = [
            f"SELECT timestamp, symbol, open, high, low, close, volume FROM {table}",
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

    async def fetch_latest(
        self, table: str, symbol: str, window: int = 1
    ) -> List[Dict[str, Any]]:
        query = f"""
            SELECT timestamp, symbol, open, high, low, close, volume
            FROM {table}
            WHERE symbol = $1
            ORDER BY timestamp DESC
            LIMIT {int(window)}
        """
        rows = await self.fetch_all(query, symbol)
        return list(reversed(rows))