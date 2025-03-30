from base import Base


class DerivativesFetcher(Base):
    def __init__(self, config_path: str = None):
        super().__init__(config_path)


if __name__ == "__main__":
    fetcher = DerivativesFetcher.get_auth()
    print(f"Access Token: {fetcher.access_token}")
