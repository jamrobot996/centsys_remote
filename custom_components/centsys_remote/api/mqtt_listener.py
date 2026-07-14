"""Persistent MQTT listener for real-time gate telemetry.

Maintains a single long-lived MQTT connection (mutual TLS, MQTT v5) to the
CenSys broker.  Subscribes to ``<serial>/deviceOverview`` for every registered
Wi-Fi gate and periodically sends wake packets to keep the operator's
telemetry radio active.  Incoming frames are parsed and pushed to the HA event
loop via a callback, giving the coordinator near-real-time gate state.

Replaces the previous "connect-fetch-disconnect" one-shot pattern with a
persistent subscription, so state changes triggered by *any* source (physical
remote, app, keypad) are captured immediately.
"""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Reconnection backoff bounds (seconds).
_RECONNECT_MIN = 5
_RECONNECT_MAX = 120


@dataclass
class GateInfo:
    """Per-gate context held by the listener."""

    serial: str
    wake_cmd01: bytes  # cmd 01 identity packet, or b"" for passive listen


class MqttListener:
    """Long-lived MQTT connection for real-time gate telemetry.

    The listener is started once (via :meth:`async_start`) and stays connected
    for the lifetime of the config entry.  It automatically reconnects with
    exponential backoff if the connection drops, re-fetching the mTLS
    certificate on each attempt (in case the old one expired).

    Gate movements are detected via ``deviceOverview`` MQTT messages.  The gate
    broadcasts at ~1 msg/sec while moving; when idle, it only broadcasts after
    being woken with a ``connectionRequest`` + ``cmd01`` identity packet.  The
    listener sends these wake packets on a configurable cadence.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        fetch_certificate: Callable[[], Any],
        mobile_number: str,
        on_overview: Callable[[str, Any], None],
        wake_interval: float = 15.0,
        au: bool = False,
    ) -> None:
        from .const import MQTT_CLIENT_ID_PREFIX, MQTT_IP_AU, MQTT_IP_ZA, MQTT_PORT

        self._hass = hass
        self._fetch_certificate = fetch_certificate
        self._on_overview = on_overview
        self._wake_interval = wake_interval

        # MQTT session client-id is deliberately different from the trigger
        # client-id (``mcr:<number>``) so both can coexist on the broker.
        # The application-level identity the gate expects on every publish.
        # The broker strictly enforces that the MQTT client_id exactly matches
        # the certificate (mcr:<number>). If we append a UUID, it silently
        # drops our subscriptions and kills real-time telemetry!
        self._user_client_id = f"{MQTT_CLIENT_ID_PREFIX}{mobile_number}"
        self._session_client_id = self._user_client_id
        self._host = MQTT_IP_AU if au else MQTT_IP_ZA
        self._port = MQTT_PORT

        self._gates: dict[str, GateInfo] = {}
        self._mqtt: Any | None = None  # paho.mqtt.client.Client
        self._cert_pem: bytes | None = None
        self._key_pem: bytes | None = None
        self._cert_file: str | None = None
        self._key_file: str | None = None

        self._running = False
        self._connected = False
        self._wake_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._backoff = _RECONNECT_MIN

    # -- public API --------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Whether the MQTT client is currently connected to the broker."""
        return self._connected

    def update_gates(self, gates: dict[str, GateInfo]) -> None:
        """Update the set of monitored gates.

        New serials are subscribed immediately if the connection is live.
        Removed serials are explicitly unsubscribed.
        """
        new_serials = set(gates.keys()) - set(self._gates.keys())
        removed_serials = set(self._gates.keys()) - set(gates.keys())
        self._gates = dict(gates)

        if self._mqtt and self._connected:
            if new_serials:
                topics = []
                for serial in new_serials:
                    topics.append((f"{serial}/deviceOverview", 0))
                    topics.append((f"{serial}/connectionRequestResponse", 0))
                if topics:
                    try:
                        self._mqtt.subscribe(topics)
                    except Exception:  # noqa: BLE001
                        _LOGGER.debug("MQTT listener: subscribe for new gates failed")
            if removed_serials:
                topics_to_remove = []
                for serial in removed_serials:
                    topics_to_remove.append(f"{serial}/deviceOverview")
                    topics_to_remove.append(f"{serial}/connectionRequestResponse")
                if topics_to_remove:
                    try:
                        self._mqtt.unsubscribe(topics_to_remove)
                    except Exception:  # noqa: BLE001
                        pass

    async def async_start(self) -> None:
        """Start the persistent MQTT connection and wake loop."""
        if self._running:
            return
        self._running = True
        _LOGGER.info("MQTT listener: starting persistent connection")
        await self._async_connect()
        self._wake_task = self._hass.async_create_background_task(
            self._wake_loop(), name="centsys_mqtt_wake"
        )

    async def async_stop(self) -> None:
        """Stop the listener and clean up all resources."""
        _LOGGER.info("MQTT listener: stopping")
        self._running = False
        if self._wake_task:
            self._wake_task.cancel()
            self._wake_task = None
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        await self._async_disconnect()
        self._cleanup_temp_files()

    # -- connection lifecycle ----------------------------------------------

    async def _async_connect(self) -> None:
        """Fetch the mTLS certificate and connect to the broker."""
        try:
            cert = await self._fetch_certificate()
            from .mqtt_remote import pfx_to_pem

            self._cert_pem, self._key_pem = (
                await self._hass.async_add_executor_job(
                    pfx_to_pem, cert["pfx_base64"], cert["password"]
                )
            )
            await self._hass.async_add_executor_job(self._connect_blocking)
            self._backoff = _RECONNECT_MIN
            _LOGGER.info("MQTT listener: connecting to %s:%s", self._host, self._port)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT listener: connection failed: %s", err)
            self._schedule_reconnect()

    def _connect_blocking(self) -> None:
        """Create paho client, configure TLS, connect, start loop.  Executor."""
        import paho.mqtt.client as mqtt

        self._cleanup_temp_files()

        fd_c, self._cert_file = tempfile.mkstemp(suffix=".pem")
        os.write(fd_c, self._cert_pem)
        os.close(fd_c)
        fd_k, self._key_file = tempfile.mkstemp(suffix=".pem")
        os.write(fd_k, self._key_pem)
        os.close(fd_k)

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._session_client_id,
            protocol=mqtt.MQTTv5,
        )
        client.on_connect = self._on_connect
        client.on_subscribe = self._on_subscribe
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(certfile=self._cert_file, keyfile=self._key_file)
        client.tls_set_context(ctx)

        client.connect(self._host, self._port, keepalive=60, clean_start=True)
        client.loop_start()
        self._mqtt = client

    async def _async_disconnect(self) -> None:
        """Disconnect the MQTT client gracefully."""
        if self._mqtt:
            try:
                await self._hass.async_add_executor_job(self._disconnect_blocking)
            except Exception:  # noqa: BLE001
                pass
            self._mqtt = None
            self._connected = False

    def _disconnect_blocking(self) -> None:
        """Stop paho loop and disconnect.  Executor."""
        if self._mqtt:
            try:
                self._mqtt.loop_stop()
                self._mqtt.disconnect()
            except Exception:  # noqa: BLE001
                pass

    def _cleanup_temp_files(self) -> None:
        """Remove temporary PEM files from disk."""
        for path in (self._cert_file, self._key_file):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
        self._cert_file = None
        self._key_file = None

    # -- paho callbacks (called from paho's network thread) ----------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = getattr(reason_code, "value", reason_code)
        if rc != 0:
            _LOGGER.warning(
                "MQTT listener: broker refused connection (rc=%s)", reason_code
            )
            return
        _LOGGER.debug("MQTT listener: connected (rc=%s)", reason_code)
        self._connected = True
        # Subscribe to all known gate topics.
        topics = []
        for serial in self._gates:
            topics.append((f"{serial}/deviceOverview", 0))
            topics.append((f"{serial}/connectionRequestResponse", 0))
        if topics:
            client.subscribe(topics)

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties=None):
        _LOGGER.debug("MQTT listener: subscribed (mid=%s)", mid)

    def _on_message(self, client, userdata, msg):
        if not msg.topic.endswith("/deviceOverview") or not msg.payload:
            return
        serial = msg.topic.rsplit("/", 1)[0]
        try:
            from .mqtt_remote import parse_device_overview

            gate = self._gates.get(serial)
            is_garage = not gate.wake_cmd01 if gate else False
            overview = parse_device_overview(msg.payload, is_garage=is_garage)
        except (ValueError, Exception) as err:  # noqa: BLE001
            _LOGGER.debug(
                "MQTT listener: failed to parse overview for %s: %s", serial, err
            )
            return
        _LOGGER.debug(
            "MQTT listener: %s gate=%s batt=%.2fV",
            serial,
            overview.gate_status,
            overview.battery_voltage or 0,
        )
        # Push to the HA event loop.
        self._hass.loop.call_soon_threadsafe(self._on_overview, serial, overview)

    def _on_disconnect(self, client, userdata, flags=None, reason_code=None, properties=None):
        _LOGGER.debug(
            "MQTT listener: disconnected (rc=%s, flags=%s)", reason_code, flags
        )
        was_connected = self._connected
        self._connected = False
        if self._running and was_connected:
            self._hass.loop.call_soon_threadsafe(self._schedule_reconnect)

    # -- reconnection ------------------------------------------------------

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt (event-loop side)."""
        if not self._running:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return  # already scheduled
        _LOGGER.debug(
            "MQTT listener: scheduling reconnect in %.0fs", self._backoff
        )
        self._reconnect_task = self._hass.async_create_background_task(
            self._reconnect(), name="centsys_mqtt_reconnect"
        )

    async def _reconnect(self) -> None:
        """Wait, then reconnect with a fresh certificate."""
        await asyncio.sleep(self._backoff)
        self._backoff = min(self._backoff * 2, _RECONNECT_MAX)
        if self._running:
            await self._async_disconnect()
            await self._async_connect()

    # -- wake loop ---------------------------------------------------------

    async def _wake_loop(self) -> None:
        """Periodically wake all gates to keep their telemetry streaming."""
        try:
            while self._running:
                if self._connected and self._mqtt:
                    for serial, gate in self._gates.items():
                        self._send_wake(serial, gate.wake_cmd01)
                await asyncio.sleep(self._wake_interval)
        except asyncio.CancelledError:
            pass

    def _send_wake(self, serial: str, wake_cmd01: bytes) -> None:
        """Publish connectionRequest + cmd01 wake to one gate."""
        if not self._mqtt or not self._connected:
            return
        from paho.mqtt.packettypes import PacketTypes
        from paho.mqtt.properties import Properties

        t_req = f"{serial}/connectionRequest"
        t_req_resp = f"{serial}/connectionRequestResponse"
        t_trig = f"{serial}/userRemoteTrigger"

        props = Properties(PacketTypes.PUBLISH)
        props.ResponseTopic = t_req_resp
        props.UserProperty = [("ClientId", self._user_client_id)]

        try:
            self._mqtt.publish(t_req, b"", qos=2, properties=props)
            if wake_cmd01:
                self._mqtt.publish(t_trig, wake_cmd01, qos=0, properties=props)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("MQTT listener: wake failed for %s: %s", serial, err)
