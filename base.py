import os
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any


@dataclass
class AuthToken:
    """
    Class representing an authentication token.

    Args:
        access_token (str): The access token string
        access_token_token_expired (str): Token expiration timestamp
        token_type (str): Type of token (e.g. "Bearer")
        expires_in (int): Token lifetime in seconds
        _created_at (datetime): Token creation timestamp. Defaults to current time.
    """
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
    """
    Base class providing authentication and configuration functionality.

    Args:
        config_path (str, optional): Path to configuration file. Defaults to DEFAULT_CONFIG.
    """
    DEFAULT_CONFIG = "config.json"

    def __init__(self, config_path: str = None):
        config_path = config_path or self.DEFAULT_CONFIG
        self.config = json.load(open(config_path))
        self.token_path = "token.json"
        self._auth_token: Optional[AuthToken] = None

    @classmethod
    def get_auth(cls, config_path: str = None) -> 'Base':
        """
        Create an authenticated instance of the class.

        Args:
            config_path (str, optional): Path to configuration file. Defaults to DEFAULT_CONFIG.

        Returns:
            Base: Authenticated instance
        """
        config_path = config_path or cls.DEFAULT_CONFIG
        inst = cls(config_path=config_path)
        inst.token_info
        return inst

    @property
    def token_info(self) -> AuthToken:
        """
        Get current authentication token, fetching or refreshing if needed.

        Returns:
            AuthToken: Current valid authentication token
        """
        if not self._auth_token or not self._auth_token.is_valid:
            self._auth_token = self._load_cached_token() or self._fetch_new_token()
        return self._auth_token

    @property
    def access_token(self) -> str:
        """Get the current access token string"""
        return self.token_info.access_token

    @property
    def api_key(self) -> str:
        """Get the API key from config"""
        return self.config.get('APP_KEY')

    @property
    def api_secret(self) -> str:
        """Get the API secret from config"""
        return self.config.get('APP_SECRET')

    @property
    def account_no(self) -> str:
        """Get the account number from config"""
        return self.config.get('ACCOUNT_NO')

    @property
    def url(self) -> str:
        """Get the API base URL from config"""
        return self.config.get('URL')

    def _load_cached_token(self) -> Optional[AuthToken]:
        """
        Load cached token from file if it exists and is valid.

        Returns:
            Optional[AuthToken]: Cached token if valid, None otherwise
        """
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
        """
        Save token to cache file.

        Args:
            token (AuthToken): Token to save
        """
        with open(self.token_path, 'w') as f:
            json.dump(token.to_dict(), f, indent=4)

    def _fetch_new_token(self) -> AuthToken:
        """
        Fetch new authentication token from API.

        Returns:
            AuthToken: New authentication token
        """
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
