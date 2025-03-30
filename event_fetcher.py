import requests
import pandas as pd
from typing import Optional

from base import Base


class EventFetcher(Base):
    def __init__(self, config_path: str = None):
        super().__init__(config_path)

    def get_dividend_rank(self, div_type: int = 2, f_dt: str = None, t_dt: str = None):
        PATH = "uapi/domestic-stock/v1/ranking/dividend-rate"
        URL = f"{self.url}/{PATH}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appKey": self.api_key,
            "appSecret": self.api_secret,
            "tr_id": "HHKDB13470100"
        }

        params = {
            "CTS_AREA": "",
            "GB1": "0",
            "UPJONG": "0001",
            "GB2": "0",
            "GB3": f"{div_type}",
            "F_DT": f_dt,
            "T_DT": t_dt,
            "GB4": "0"
        }
        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return resp.json()['output']
        else:
            raise Exception(
                f"Failed to fetch dividend rank: {str(resp.status_code)} + | + {resp.text}")

    def get_ipo_list(self, ticker: Optional[str] = None, f_dt: str = None, t_dt: str = None):
        PATH = "uapi/domestic-stock/v1/ranking/traded-by-company"
        URL = f"{self.url}/{PATH}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appKey": self.api_key,
            "appSecret": self.api_secret,
            "tr_id": "HHKDB669108C0"
        }

        params = {
            "cts": "",
            "f_dt": f_dt,
            "t_dt": t_dt,
            "sht_cd": ticker
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return resp.json()['output1']
        else:
            raise Exception(
                f"Failed to fetch ipo list: {str(resp.status_code)} + | + {resp.text}")
