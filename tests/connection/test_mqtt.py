from types import SimpleNamespace

import pytest
from awscrt import mqtt5

from pyhon.connection.mqtt import MQTTClient


def connect(settings: mqtt5.NegotiatedSettings | None) -> MQTTClient:
    """Run the connection success callback on a client marked as subscribed."""
    hon = SimpleNamespace(api=None, appliances=[])
    client = MQTTClient(hon, "test")  # type: ignore[arg-type]
    client._subscribed = True
    client._on_lifecycle_connection_success(
        mqtt5.LifecycleConnectSuccessData(negotiated_settings=settings)
    )
    return client


@pytest.mark.parametrize(
    "settings",
    [None, mqtt5.NegotiatedSettings(rejoined_session=False)],
    ids=["no negotiated settings", "new session"],
)
def test_resubscribe_after_connection(
    settings: mqtt5.NegotiatedSettings | None,
) -> None:
    assert connect(settings)._subscribed is False


def test_keep_subscriptions_when_session_rejoined() -> None:
    settings = mqtt5.NegotiatedSettings(rejoined_session=True)
    assert connect(settings)._subscribed is True
