import requests
import pandas as pd
from typing import Optional

from base import Base
from tools import Tools


class EventFetcher(Base):
    """
    Class for fetching event data from the exchange.

    Args:
        config_path (str, optional): Path to configuration file. Defaults to None.
    """

    def __init__(self, config_path: str = None):
        super().__init__(config_path)

    def get_dividend_rank(self,
                          div_type: int = 2,
                          f_dt: str = None,
                          t_dt: str = None) -> dict:
        """
        Get dividend rank data from the exchange.

        Args:
            div_type (int, optional): Dividend type. Defaults to 2.
                Available codes:
                - 1: Stock dividend
                - 2: Cash dividend
            f_dt (str, optional): From date in YYYYMMDD format. Defaults to None.
            t_dt (str, optional): To date in YYYYMMDD format. Defaults to None.

        Returns:
            dict: Response containing dividend rank data
        """
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
                f"Failed to fetch dividend rank: {str(resp.status_code)}" + "|" + f"{resp.text}")

    def get_ipo_list(self,
                     sht_cd: Optional[str] = None,
                     f_dt: str = None,
                     t_dt: str = None) -> dict:
        """
        Get IPO list data from the exchange.

        Args:
            sht_cd (str, optional): Ticker code. Defaults to None.
            f_dt (str, optional): From date in YYYYMMDD format. Defaults to None.
            t_dt (str, optional): To date in YYYYMMDD format. Defaults to None.

        Returns:
            dict: Response containing IPO list data
        """
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
            "sht_cd": sht_cd
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return resp.json()['output1']
        else:
            raise Exception(
                f"Failed to fetch ipo list: {str(resp.status_code)}" + "|" + f"{resp.text}")

    def get_short_sell_rank(self,
                            fid_input_iscd: str = "0000",
                            fid_period_div_code: str = "D",
                            fid_input_cnt_1: str = "000000000001",
                            fid_trgt_exls_cls_code: str = "0",
                            fid_trgt_cls_code: str = "0",
                            fid_aply_rang_prc_1: str = "",
                            fid_aply_rang_prc_2: str = "",
                            fid_aply_rang_vol_1: str = "") -> dict:
        """
        Get short sell rank data from the exchange.

        Args:
            fid_input_iscd (str, optional): Industry code. Defaults to "0000".
                Available codes:
                - "0000": All
                - "0001": KOSPI
                - "1001": KOSDAQ
                - "2001": KOSPI200
            fid_period_div_code (str, optional): Period type. Defaults to "D".
                Available codes:
                - "D": For days/weeks
                - "M": For months
            fid_input_cnt_1 (str, optional): Period count. Defaults to "000000000001".
                For days/weeks (D):
                - "000000000000": 1 day
                - "000000000001": 2 days
                - "000000000004": 1 week
                - "000000000009": 2 weeks
                For months (M):
                - "000000000001": 1 month
                - "000000000002": 2 months
            fid_trgt_exls_cls_code (str, optional): Target exclusion code. Defaults to "0" (all).
            fid_trgt_cls_code (str, optional): Target classification code. Defaults to "0" (all).
            fid_aply_rang_prc_1 (str, optional): Price range start. Defaults to "".
            fid_aply_rang_prc_2 (str, optional): Price range end. Defaults to "".
            fid_aply_rang_vol_1 (str, optional): Volume threshold. Defaults to "".
                "0": All volumes
                "100": 100 shares or more

        Returns:
            dict: Response containing short sell rank data
        """
        PATH = "uapi/domestic-stock/v1/ranking/short-sale"
        URL = f"{self.url}/{PATH}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appKey": self.api_key,
            "appSecret": self.api_secret,
            "tr_id": "FHPST04820000"
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20482",
            "fid_input_iscd": fid_input_iscd,
            "fid_period_div_code": fid_period_div_code,
            "fid_input_cnt_1": fid_input_cnt_1,
            "fid_trgt_exls_cls_code": fid_trgt_exls_cls_code,
            "fid_trgt_cls_code": fid_trgt_cls_code,
            "fid_aply_rang_prc_1": fid_aply_rang_prc_1,
            "fid_aply_rang_prc_2": fid_aply_rang_prc_2,
            "fid_aply_rang_vol_1": fid_aply_rang_vol_1
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return resp.json()['output']
        else:
            raise Exception(
                f"Failed to fetch short sell rank: {str(resp.status_code)}" + "|" + f"{resp.text}")


if __name__ == "__main__":
    event_fetcher = EventFetcher()
    print(event_fetcher.get_short_sell_rank())
