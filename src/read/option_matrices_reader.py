from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import BaseReader
from services.time_service import TimeService


class OptionMatricesReader(BaseReader):
    def _table(self, underlying_symbol: str) -> str:
        return f"option_matrices_{underlying_symbol.lower()}"

    async def fetch_metrics(
        self,
        underlying_symbol: str,
        metrics: Optional[List[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        table = self._table(underlying_symbol)
        parts = [
            f"SELECT * FROM {table}",
            "WHERE 1=1",
        ]
        args: List[Any] = []
        idx = 1

        if metrics:
            placeholders = ", ".join([f"${i}" for i in range(idx, idx + len(metrics))])
            parts.append(f"AND metric_type IN ({placeholders})")
            args.extend(metrics)
            idx += len(metrics)

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