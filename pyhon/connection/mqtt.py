import asyncio
import json
import logging
import secrets
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from awscrt import mqtt5
from awsiot import mqtt5_client_builder  # type: ignore[import-untyped]

from pyhon import const
from pyhon.appliance import HonAppliance
from pyhon.attributes import HonAttribute

if TYPE_CHECKING:
    from pyhon import Hon

_LOGGER = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self, hon: "Hon", mobile_id: str) -> None:
        self._client: mqtt5.Client | None = None
        self._hon = hon
        self._mobile_id = mobile_id or const.MOBILE_ID
        self._api = hon.api
        self._appliances = hon.appliances
        self._connection = False
        self._subscribed = False
        self._needs_reauth = False
        self._watchdog_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    @property
    def client(self) -> mqtt5.Client:
        if self._client is not None:
            return self._client
        raise AttributeError("Client is not set")

    async def create(self) -> "MQTTClient":
        self._loop = asyncio.get_running_loop()
        await self._start()
        await self.start_watchdog()
        return self

    def _on_lifecycle_stopped(
        self, lifecycle_stopped_data: mqtt5.LifecycleStoppedData
    ) -> None:
        _LOGGER.info("Lifecycle Stopped: %s", str(lifecycle_stopped_data))

    def _on_lifecycle_connection_success(
        self,
        lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData,
    ) -> None:
        self._connection = True
        _LOGGER.info(
            "Lifecycle Connection Success: %s", str(lifecycle_connect_success_data)
        )
        if not lifecycle_connect_success_data.negotiated_settings.rejoined_session:
            # Resubscribe to all topics after reconnection
            # This is needed because we use a new client_id each time (no session persistence)
            _LOGGER.info("MQTT connection established, marking as not subscribed")
            self._subscribed = False
        else:
            _LOGGER.info("Rejoined existing session")

    def _on_lifecycle_attempting_connect(
        self,
        lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData,
    ) -> None:
        _LOGGER.info(
            "Lifecycle Attempting Connect - %s", str(lifecycle_attempting_connect_data)
        )

    def _on_lifecycle_connection_failure(
        self,
        lifecycle_connection_failure_data: mqtt5.LifecycleConnectFailureData,
    ) -> None:
        self._connection = False
        _LOGGER.info(
            "Lifecycle Connection Failure - %s", str(lifecycle_connection_failure_data)
        )
        connack = lifecycle_connection_failure_data.connack_packet
        if connack is not None and connack.reason_code in (
            mqtt5.ConnectReasonCode.NOT_AUTHORIZED,
            mqtt5.ConnectReasonCode.BAD_USERNAME_OR_PASSWORD,
        ):
            _LOGGER.info(
                "MQTT connection rejected as unauthorized, will re-authenticate"
            )
            self._needs_reauth = True
            if self._client is not None:
                # Stop the client's own reconnect loop immediately, otherwise it
                # keeps retrying with the same stale token until the watchdog
                # notices and restarts with a fresh one.
                self._client.stop()

    def _on_lifecycle_disconnection(
        self,
        lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData,
    ) -> None:
        self._connection = False
        _LOGGER.info("Lifecycle Disconnection - %s", str(lifecycle_disconnect_data))

    def _on_publish_received(self, data: mqtt5.PublishReceivedData) -> None:
        # AWS CRT invokes callbacks on a worker thread. Mutate appliance state
        # and notify consumers on the owning asyncio loop, including HA.
        if not self._closed and self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._process_publish, data)

    def _process_publish(self, data: mqtt5.PublishReceivedData) -> None:
        if self._closed:
            return
        if not (data and data.publish_packet and data.publish_packet.payload):
            return
        try:
            payload = json.loads(data.publish_packet.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            _LOGGER.warning("Ignoring malformed MQTT payload")
            return
        if not isinstance(payload, dict):
            return
        topic = data.publish_packet.topic
        appliance = next(
            (
                a
                for a in self._appliances
                if topic in a.info.get("topics", {}).get("subscribe", [])
            ),
            None,
        )
        if appliance is None:
            return
        self._apply_publish(appliance, topic, payload)
        appliance.push_updated()
        self._hon.notify()
        _LOGGER.debug("%s - %s", topic, payload)

    def _apply_publish(
        self, appliance: HonAppliance, topic: str | None, payload: dict[str, Any]
    ) -> None:
        if topic and "appliancestatus" in topic:
            self._update_parameters(appliance, payload.get("parameters", []))
        elif topic and "disconnected" in topic:
            appliance.connection = False
        elif topic and "connected" in topic:
            appliance.connection = True

    @staticmethod
    def _update_parameters(appliance: HonAppliance, parameters: Any) -> None:
        if not isinstance(parameters, list):
            return
        current = appliance.attributes.setdefault("parameters", {})
        for parameter in parameters:
            if not isinstance(parameter, dict) or not isinstance(
                parameter.get("parName"), str
            ):
                continue
            name = parameter["parName"]
            if name in current:
                current[name].update(parameter)
            else:
                current[name] = HonAttribute(parameter)
        appliance.sync_params_to_command("settings")

    async def close(self) -> None:
        """Stop reconnects and ignore queued callbacks after unload."""
        self._closed = True
        if self._watchdog_task:
            self._watchdog_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._watchdog_task
            self._watchdog_task = None
        if self._client:
            self._client.stop()
            self._client = None
        self._connection = False
        self._subscribed = False

    async def _start(self) -> None:
        if self._client is not None:
            self._client.stop()
        if self._needs_reauth:
            _LOGGER.info("Re-authenticating before reconnecting to mqtt")
            await self._api.auth.refresh()
            self._needs_reauth = False
        aws_token = await self._api.load_aws_token()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, MQTTClient._build_mqtt_client, self, aws_token)
        self.client.start()

    def _build_mqtt_client(self, aws_token) -> None:
        self._client = mqtt5_client_builder.websockets_with_custom_authorizer(
            endpoint=const.AWS_ENDPOINT,
            auth_authorizer_name=const.AWS_AUTHORIZER,
            auth_authorizer_signature=aws_token,
            auth_token_key_name="token",
            auth_token_value=self._api.auth.id_token,
            client_id=f"{self._mobile_id}_{secrets.token_hex(8)}",
            on_lifecycle_stopped=self._on_lifecycle_stopped,
            on_lifecycle_connection_success=self._on_lifecycle_connection_success,
            on_lifecycle_attempting_connect=self._on_lifecycle_attempting_connect,
            on_lifecycle_connection_failure=self._on_lifecycle_connection_failure,
            on_lifecycle_disconnection=self._on_lifecycle_disconnection,
            on_publish_received=self._on_publish_received,
            enable_metrics_collection=False,
        )

    def _subscribe_appliances(self) -> None:
        try:
            for appliance in self._appliances:
                self._subscribe(appliance)
            self._subscribed = True
        except Exception as e:
            _LOGGER.error("Error subscribing to appliances: %s - %s", repr(e), str(e))

    def _subscribe(self, appliance: HonAppliance) -> None:
        for topic in appliance.info.get("topics", {}).get("subscribe", []):
            self.client.subscribe(
                mqtt5.SubscribePacket([mqtt5.Subscription(topic)])
            ).result(10)
            _LOGGER.info("Subscribed to topic %s", topic)

    async def start_watchdog(self) -> None:
        if not self._watchdog_task or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog())

    async def _watchdog(self) -> None:
        while not self._closed:
            await asyncio.sleep(5)
            try:
                if not self._connection:
                    _LOGGER.info("Restart mqtt connection")
                    await self._start()
                    # Give the fresh client time to finish its handshake before
                    # the next check, otherwise it gets torn down and rebuilt
                    # every 5 seconds while still connecting.
                    await asyncio.sleep(25)
                elif not self._subscribed:
                    _LOGGER.info("Resubscribing to appliance topics")
                    self._subscribe_appliances()
            except Exception as error:  # pylint: disable=broad-except
                # A transient failure inside _start() (token refresh, AWS token
                # fetch, client build) used to escape and kill this task
                # silently; the connection was then never restarted and all
                # updates stopped until a manual reload. Log and keep going.
                _LOGGER.warning("MQTT watchdog iteration failed, retrying: %r", error)
