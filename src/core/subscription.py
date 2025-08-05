from typing import List

from models.dataclasses import SubscriptionConfig
from protocols import SubscriptionManager as SubscriptionManagerProtocol


class SubscriptionManager(SubscriptionManagerProtocol):
    def __init__(self):
        self._subscriptions: List[SubscriptionConfig] = []

    def add_subscription(self, config: SubscriptionConfig) -> None:
        self._subscriptions.append(config)

    def get_subscriptions(self) -> List[SubscriptionConfig]:
        return self._subscriptions.copy()

    def clear_subscriptions(self) -> None:
        self._subscriptions.clear() 