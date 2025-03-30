import requests
import pandas as pd

from base import Base
from tools import Tools


class DerivativesFetcher(Base):
    """
    Class for fetching derivatives (futures/options) data from the exchange.

    Args:
        config_path (str, optional): Path to configuration file. Defaults to None.
    """

    def __init__(self, config_path: str = None):
        super().__init__(config_path)

    def get_current_price(self,
                          fid_cond_mrkt_div_code: str = "F",
                          fid_input_iscd: str = None) -> dict:
        """
        Get current price of futures/options from the exchange.

        Args:
            fid_cond_mrkt_div_code (str, optional): Market division code. Defaults to "F".
                Available codes:
                - "F": Futures
                - "O": Options
            fid_input_iscd (str, optional): Ticker symbol. Defaults to None.

        Returns:
            dict: Response containing price data
        """
        PATH = "uapi/domestic-futureoption/v1/quotations/inquire-price"
        URL = f"{self.url}/{PATH}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appKey": self.api_key,
            "appSecret": self.api_secret,
            "tr_id": "FHMIF10000000"
        }

        params = {
            "fid_cond_mrkt_div_code": fid_cond_mrkt_div_code,
            "fid_input_iscd": fid_input_iscd
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return {k: Tools.convert_data_types(value=v) for k, v in resp.json().items()}
        else:
            raise Exception(
                f"Failed to fetch price: {str(resp.status_code)}" + "|" + f"{resp.text}")

    def get_futures_list(self,
                         fid_cond_mrkt_div_code: str = "F",
                         fid_mrkt_cls_code: str = "MKI") -> dict:
        """
        Get futures list from the exchange.

        Args:
            fid_cond_mrkt_div_code (str, optional): Market division code. Defaults to "F".
            fid_mrkt_cls_code (str, optional): Market class code. Defaults to "MKI".
                Available codes:
                - "": KOSPI200 futures
                - "MKI": Mini KOSPI200 futures
                - "WKM": KOSPI200 weekly futures (Monday)
                - "WKI": KOSPI200 weekly futures (Thursday)
                - "KQI": KOSDAQ150 futures

        Returns:
            dict: Response containing futures list data
        """
        PATH = "uapi/domestic-futureoption/v1/quotations/display-board-futures"
        URL = f"{self.url}/{PATH}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appKey": self.api_key,
            "appSecret": self.api_secret,
            "tr_id": "FHPIF05030200"
        }

        params = {
            "fid_cond_mrkt_div_code": fid_cond_mrkt_div_code,
            "fid_cond_scr_div_code": "20503",
            "fid_cond_mrkt_cls_code": fid_mrkt_cls_code
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return Tools.convert_data_types(resp.json()['output'])
        else:
            raise Exception(
                f"Failed to fetch futures list: {str(resp.status_code)}" + "|" + f"{resp.text}")

    def get_options_list(self,
                         fid_cond_mrkt_div_code: str = "O",
                         fid_mrkt_cls_code: str = "CO",
                         fid_mtrt_cnt: str = "202506",
                         fid_cond_mrkt_cls_code: str = "",
                         fid_mrkt_cls_code1: str = "PO") -> dict:
        """
        Get options list from the exchange.

        Args:
            fid_cond_mrkt_div_code (str, optional): Market division code. Defaults to "O".
            fid_mrkt_cls_code (str, optional): Market class code. Defaults to "CO".
            fid_mtrt_cnt (str, optional): Market maturity code. Defaults to "202506".
                Available codes:
                - "YYYYMM": KOSPI200 options
                - "YYMMWW": KOSPI200 weekly options (Monday)
                - "YYMMDD": KOSPI200 weekly options (Thursday)
            fid_cond_mrkt_cls_code (str, optional): Market class condition code. Defaults to "".
                Available codes:
                - "": KOSPI200 options
                - "MKI": Mini KOSPI200 options 
                - "WKM": KOSPI200 weekly options (Monday)
                - "WKI": KOSPI200 weekly options (Thursday)
                - "KQI": KOSDAQ150 options
            fid_mrkt_cls_code1 (str, optional): Market class code 1. Defaults to "PO".

        Returns:
            dict: Response containing options list data
        """
        PATH = "uapi/domestic-futureoption/v1/quotations/display-board-callput"
        URL = f"{self.url}/{PATH}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "appKey": self.api_key,
            "appSecret": self.api_secret,
            "tr_id": "FHPIF05030100"
        }

        params = {
            "fid_cond_mrkt_div_code": fid_cond_mrkt_div_code,
            "fid_cond_scr_div_code": "20503",
            "fid_mrkt_cls_code": fid_mrkt_cls_code,
            "fid_mtrt_cnt": fid_mtrt_cnt,
            "fid_cond_mrkt_cls_code": fid_cond_mrkt_cls_code,
            "fid_mrkt_cls_code1": fid_mrkt_cls_code1
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            data = resp.json()
            return {
                'call': data.get('output1', []),
                'put': data.get('output2', [])
            }
        else:
            raise Exception(
                f"Failed to fetch options list: {str(resp.status_code)}" + "|" + f"{resp.text}")


if __name__ == "__main__":
    fetcher = DerivativesFetcher.get_auth()
    print(fetcher.get_current_price(
        fid_cond_mrkt_div_code="F", fid_input_iscd="101W06"))
    print(fetcher.get_futures_list(
        fid_cond_mrkt_div_code="F", fid_mrkt_cls_code="MKI"))
    print(fetcher.get_options_list(fid_cond_mrkt_div_code="O",
                                   fid_mrkt_cls_code="CO",
                                   fid_mtrt_cnt="202506",
                                   fid_cond_mrkt_cls_code="",
                                   fid_mrkt_cls_code1="PO"))
