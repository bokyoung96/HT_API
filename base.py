import os
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any


@dataclass
class AuthToken:
    access_token: str
    access_token_token_expired: str
    token_type: str
    expires_in: int
    _created_at: datetime = field(default_factory=datetime.now, repr=False)

    @property
    def is_valid(self) -> bool:
        try:
            expiry_time = datetime.strptime(self.access_token_token_expired,
                                            '%Y-%m-%d %H:%M:%S')
            return datetime.now() < (expiry_time - timedelta(minutes=10))
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if not k.startswith('_')}


class Base:
    DEFAULT_CONFIG = "config.json"

    def __init__(self, config_path: str = None):
        config_path = config_path or self.DEFAULT_CONFIG
        self.config = json.load(open(config_path))
        self.token_path = "token.json"
        self._auth_token: Optional[AuthToken] = None

    @classmethod
    def get_auth(cls, config_path: str = None) -> 'Base':
        config_path = config_path or cls.DEFAULT_CONFIG
        inst = cls(config_path=config_path)
        inst.token_info
        return inst

    @property
    def token_info(self) -> AuthToken:
        if not self._auth_token or not self._auth_token.is_valid:
            self._auth_token = self._load_cached_token() or self._fetch_new_token()
        return self._auth_token

    @property
    def access_token(self) -> str:
        return self.token_info.access_token

    @property
    def api_key(self) -> str:
        return self.config.get('APP_KEY')

    @property
    def api_secret(self) -> str:
        return self.config.get('APP_SECRET')

    @property
    def account_no(self) -> str:
        return self.config.get('ACCOUNT_NO')

    @property
    def url(self) -> str:
        return self.config.get('URL')

    def _load_cached_token(self) -> Optional[AuthToken]:
        if not os.path.exists(self.token_path):
            return None

        try:
            with open(self.token_path, 'r') as f:
                data = json.load(f)
                token = AuthToken(**data)
                return token if token.is_valid else None
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def _save_token(self, token: AuthToken) -> None:
        with open(self.token_path, 'w') as f:
            json.dump(token.to_dict(), f, indent=4)

    def _fetch_new_token(self) -> AuthToken:
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.config["APP_KEY"],
            "appsecret": self.config["APP_SECRET"]
        }

        PATH = "/oauth2/tokenP"
        resp = requests.post(self.config["URL"] + PATH,
                             headers=headers,
                             data=json.dumps(body))
        token_data = resp.json()
        token = AuthToken(**token_data)
        self._save_token(token)
        return token


if __name__ == "__main__":
    base = Base.get_auth()
