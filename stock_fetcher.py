import requests
import pandas as pd

from base import Base
from tools import Tools


class StockFetcher(Base):
    """
    Class for fetching stock data from the exchange.

    Args:
        config_path (str, optional): Path to configuration file. Defaults to None.
    """

    def __init__(self, config_path: str = None):
        super().__init__(config_path)

    def get_current_price(self,
                          fid_cond_mrkt_div_code: str = "J",
                          fid_input_iscd: str = None) -> dict:
        """
        Get current price of stock from the exchange.

        Args:
            fid_cond_mrkt_div_code (str, optional): Market division code. Defaults to "J".
                Available codes:
                - "J": STOCK, ETF, ETN
                - "W": ELW
            fid_input_iscd (str, optional): Ticker symbol. Defaults to None.

        Returns:
            dict: Response containing price data
        """
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
            "fid_cond_mrkt_div_code": fid_cond_mrkt_div_code,
            "fid_input_iscd": fid_input_iscd
        }

        resp = requests.get(URL, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get("rt_cd") == "0":
            return {k: Tools.convert_data_types(value=v) for k, v in resp.json().items()}
        else:
            raise Exception(
                f"Failed to fetch price: {str(resp.status_code)}" + "|" + f"{resp.text}")


if __name__ == "__main__":
    fetcher = StockFetcher.get_auth()
    print(fetcher.get_current_price(
        fid_cond_mrkt_div_code="J", fid_input_iscd="005930"))
