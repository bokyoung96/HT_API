import mojito

from tools import *


config_file = "config.json"
config = Tools.load_config(config_file)

broker = mojito.KoreaInvestment(
    api_key=config.get("API_KEY"),
    api_secret=config.get("API_SECRET"),
    acc_no=config.get("ACCOUNT_NO")
)
