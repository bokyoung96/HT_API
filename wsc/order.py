import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

import httpx

from .base import KISConfig, KISAuth


class OrderInterface(ABC):
    @abstractmethod
    async def place_order(self, stock_code: str, order_type: str, quantity: int, **kwargs) -> Dict[str, Any]:
        pass


class KISTrader(OrderInterface):
    def __init__(self, config: KISConfig, auth: KISAuth, client: httpx.AsyncClient):
        self._config = config
        self._auth = auth
        self._client = client

    async def place_order(self, stock_code: str, order_type: str, quantity: int, **kwargs) -> Dict[str, Any]:
        path = "/uapi/v1/trading/order-cash"
        url = f"{self._config.base_url}{path}"
        
        access_token = await self._auth.get_access_token()
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": self._config.app_key,
            "appsecret": self._config.app_secret,
            "tr_id": self._config.tr_id,
        }
        
        body = {
            "CANO": self._config.account_no.split('-')[0],
            "ACNT_PRDT_CD": self._config.account_no.split('-')[1],
            "PDNO": stock_code, 
            "ORD_DVSN": order_type, 
            "ORD_QTY": str(quantity), 
            "ORD_UNPR": "0",
        }
        if order_type == "01":
            if 'price' not in kwargs: 
                raise ValueError("Limit order requires 'price'.")
            body["ORD_UNPR"] = str(kwargs['price'])
        
        logging.info(f"Executing order: {body}")
        response = await self._client.post(url, headers=headers, json=body)
        
        if response.status_code == 200: 
            logging.info(f"Order successful: {response.json()}")
        else: 
            logging.error(f"Order failed: {response.json()}")
        return response.json() 