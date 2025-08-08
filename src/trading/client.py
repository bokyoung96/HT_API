from __future__ import annotations
import asyncio
import json
from typing import Any, Dict, Optional, AsyncIterator

import httpx

from base import KISAuth, KISConfig


class TradingAPI:
    def __init__(self, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient):
        self._config = config
        self._auth = auth
        self._client = client

    async def post(self, path: str, tr_id: str, body: Dict[str, Any], custtype: str = "P") -> Dict[str, Any]:
        validated_body = self._sanitize_body(body)
        hashkey = await self._create_hashkey(validated_body)
        headers = await self._build_headers(tr_id=tr_id, custtype=custtype, hashkey=hashkey)
        url = f"{self._config.base_url}{path}"
        try:
            response = await self._client.post(url, headers=headers, json=validated_body)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            details = e.response.text if e.response is not None else str(e)
            raise ValueError(f"HTTP {e.response.status_code if e.response else ''} for {path}: {details}")

    async def get(self, path: str, tr_id: str, params: Dict[str, Any], custtype: str = "P") -> Dict[str, Any]:
        safe_params = {k: v for k, v in params.items() if v is not None}
        headers = await self._build_headers(tr_id=tr_id, custtype=custtype)
        url = f"{self._config.base_url}{path}"
        try:
            response = await self._client.get(url, headers=headers, params=safe_params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            details = e.response.text if e.response is not None else str(e)
            raise ValueError(f"HTTP {e.response.status_code if e.response else ''} for {path}: {details}")

    async def place_derivatives_order(self, body: Dict[str, Any]) -> Dict[str, Any]:
        tr_id = self._config.deriv_order_tr_id
        return await self.post(path="/uapi/domestic-futureoption/v1/trading/order", tr_id=tr_id, body=body)

    async def cancel_or_modify_derivatives_order(self, body: Dict[str, Any]) -> Dict[str, Any]:
        tr_id = self._config.deriv_order_rvsecncl_tr_id
        return await self.post(path="/uapi/domestic-futureoption/v1/trading/order-rvsecncl", tr_id=tr_id, body=body)

    async def get_derivatives_balance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tr_id = self._config.deriv_balance_tr_id
        return await self.get(path="/uapi/domestic-futureoption/v1/trading/inquire-balance", tr_id=tr_id, params=params)

    async def get_derivatives_order_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tr_id = self._config.deriv_order_list_tr_id
        return await self.get(path="/uapi/domestic-futureoption/v1/trading/inquire-ccnl", tr_id=tr_id, params=params)

    def _sanitize_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(body, dict):
            raise ValueError("Request body must be a dictionary")
        sanitized: Dict[str, Any] = {}
        for key, value in body.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            else:
                sanitized[key] = json.loads(json.dumps(value, ensure_ascii=False))
        return sanitized


class BalancePoller:
    def __init__(self, api: TradingAPI, params: Dict[str, Any], interval_sec: float = 1.0):
        self._api = api
        self._params = params
        self._interval = interval_sec
        self._stop_event = asyncio.Event()

    async def start(self) -> AsyncIterator[Dict[str, Any]]:
        try:
            while not self._stop_event.is_set():
                data = await self._api.get_derivatives_balance(params=self._params)
                yield data
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
                except asyncio.TimeoutError:
                    pass
        finally:
            self._stop_event.clear()

    def stop(self) -> None:
        self._stop_event.set()

    async def _create_hashkey(self, body: Dict[str, Any]) -> str:
        url = f"{self._config.base_url}/uapi/hashkey"
        headers = {
            "content-type": "application/json; charset=utf-8",
            "appkey": self._config.app_key,
            "appsecret": self._config.app_secret,
        }
        response = await self._client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        return data.get("HASH", "") or data.get("hashkey", "")

    async def _build_headers(self, tr_id: str, custtype: str = "P", hashkey: Optional[str] = None) -> Dict[str, str]:
        access_token = await self._auth.get_access_token()
        headers: Dict[str, str] = {
            "authorization": f"Bearer {access_token}",
            "appkey": self._config.app_key,
            "appsecret": self._config.app_secret,
            "tr_id": tr_id,
            "custtype": custtype,
            "content-type": "application/json; charset=utf-8",
        }
        if hashkey:
            headers["hashkey"] = hashkey
        return headers

