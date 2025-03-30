import requests
import pandas as pd

from base import Base


class StockFetcher(Base):
    def __init__(self, config_path: str = None):
        super().__init__(config_path)

    def get_current_price(self, ticker: str):
        PATH = "uapi/domestic-stock/v1/quotations/inquire-price"
        URL = f"{self.url}/{PATH}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appKey": self.api_key,
            "appSecret": self.api_secret,
            "tr_id": "FHKST01010100"
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return resp.json()
        else:
            raise Exception(
                f"Failed to fetch price: {str(resp.status_code)} + | + {resp.text}")
