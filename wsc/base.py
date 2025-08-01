import os
import json
import httpx
import logging
import asyncio
import websockets

from datetime import datetime, timedelta


def setup_logging(config_dir: str):
    log_file = os.path.join(config_dir, "kis_api.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

class KISConfig:
    def __init__(self, config_path: str = "config.json"):
        self.config_dir = os.path.dirname(os.path.abspath(config_path)) if os.path.isabs(config_path) else os.getcwd()
        path = os.path.join(self.config_dir, os.path.basename(config_path))
        
        with open(path, 'r', encoding='utf-8') as f:
            self._config = json.load(f)

        self.base_url = self._config.get("URL")
        self.ws_url = self._config.get("WS_URL")
        
        setup_logging(self.config_dir)

    @property
    def app_key(self) -> str: return self._config.get("APP_KEY")
    @property
    def app_secret(self) -> str: return self._config.get("APP_SECRET")
    @property
    def account_no(self) -> str: return f"{self._config.get('ACCOUNT_NO')}-{self._config.get('ACCOUNT_NO_SUB')}"
    @property
    def tr_id(self) -> str: return self._config.get("TR_ID", "TTTC0802U")
    @property
    def price_tr_id(self) -> str: return self._config.get("PRICE_TR_ID", "H0STCNT0")
    @property
    def execution_tr_id(self) -> str: return self._config.get("EXECUTION_TR_ID", "H0STCNI0")
    @property
    def quote_tr_id(self) -> str: return self._config.get("QUOTE_TR_ID", "H0STASP0")
    @property
    def futures_quote_tr_id(self) -> str: return self._config.get("FUTURES_QUOTE_TR_ID", "H0IFASP0")
    @property
    def futures_price_tr_id(self) -> str: return self._config.get("FUTURES_PRICE_TR_ID", "H0IFCNT0")


class KISAuth:
    def __init__(self, config: KISConfig, client: httpx.AsyncClient):
        self._config = config
        self._client = client
        self._token_file = os.path.join(config.config_dir, "access_token.json")
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._load_token()

    def _load_token(self):
        try:
            if os.path.exists(self._token_file):
                with open(self._token_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._access_token = data.get("access_token")
                    expires_str = data.get("expires_at")
                    if expires_str:
                        self._token_expires_at = datetime.fromisoformat(expires_str)
        except Exception as e:
            logging.warning(f"Failed to load saved token: {e}")

    def _save_token(self):
        try:
            data = {
                "access_token": self._access_token,
                "expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None
            }
            with open(self._token_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save token: {e}")

    async def get_access_token(self) -> str:
        if self._access_token and self._token_expires_at and datetime.now() < self._token_expires_at:
            return self._access_token
        
        logging.info("Requesting new Access Token.")
        url = f"{self._config.base_url}/oauth2/tokenP"
        body = {"grant_type": "client_credentials", 
                "appkey": self._config.app_key, 
                "appsecret": self._config.app_secret}
        response = await self._client.post(url, json=body)
        response.raise_for_status()
        data = response.json()
        
        self._access_token = data.get("access_token")
        expires_in = data.get("expires_in", 0)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 600)
        self._save_token()
        logging.info("Access Token has been successfully renewed.")
        return self._access_token

    async def get_approval_key(self) -> str:
        logging.info("Requesting new Approval Key for WebSocket.")
        url = f"{self._config.base_url}/oauth2/Approval"
        body = {"grant_type": "client_credentials", 
                "appkey": self._config.app_key, 
                "secretkey": self._config.app_secret}
        response = await self._client.post(url, json=body)
        response.raise_for_status()
        key = response.json().get("approval_key")
        logging.info("Approval Key has been successfully issued.")
        return key