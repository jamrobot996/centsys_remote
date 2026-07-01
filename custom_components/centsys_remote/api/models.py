"""Typed models for the Centsys Remote client.

Field names mirror the JSON keys returned by the backend.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from . import enums


def _random_player_id() -> str:
    return str(uuid.uuid4())


@dataclass
class DeviceInfo:
    """Client identity sent to the backend (largely informational)."""

    manufacturer: str = "Apple"
    device_model: str = "iPhone17,2"
    device_platform: str = "iOS"
    operating_version: str = "26.5"
    # A stable per-install OneSignal id; the GWeb config call rejects an empty one.
    onesignal_player_id: str = field(default_factory=_random_player_id)

    @property
    def device_string(self) -> str:
        """Concatenated identity used in the GWeb MCROTPNumb auth header.

        Format: "<manufacturer><device_model><operating_version>".
        """
        return f"{self.manufacturer}{self.device_model}{self.operating_version}"


@dataclass
class Device:
    """A gate operator returned by GetDevicesByRemoteUserNumber."""

    serial_number: str
    device_name: str
    product_type: int | None = None
    product_code: int | None = None
    is_wifi_device: bool = False
    is_online: bool | None = None
    latitude: str | None = None
    longitude: str | None = None
    faulty_device: bool | None = None
    warranty_void: bool | None = None
    last_seen: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Device":
        wifi_status = data.get("deviceWiFiStatus") or {}
        return cls(
            serial_number=data.get("serialNumber", ""),
            device_name=data.get("deviceName", ""),
            product_type=data.get("productType"),
            product_code=data.get("productCode"),
            is_wifi_device=bool(data.get("isWifiDevice", False)),
            is_online=wifi_status.get("isOnline"),
            latitude=data.get("lattitude"),  # note: backend misspells "latitude"
            longitude=data.get("longitude"),
            faulty_device=data.get("faultyDevice"),
            warranty_void=data.get("warrantyVoid"),
            last_seen=wifi_status.get("lastBackendConnectionDate"),
            raw=data,
        )


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present key (case-tolerant) from a dict."""
    for key in keys:
        if key in data:
            return data[key]
    lowered = {k.lower(): v for k, v in data.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return default


@dataclass
class GsmIo:
    """A single configurable button/output on a legacy GSM/ULTRA device."""

    io_number: int
    io_name: str = ""
    io_direction: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GsmIo":
        return cls(
            io_number=int(_pick(data, "IONumber", "IoNumber", default=0)),
            io_name=str(_pick(data, "IOName", "IoName", default="") or ""),
            io_direction=_pick(data, "IODirection", "IoDirection"),
            raw=data,
        )

    @property
    def is_gate_trigger(self) -> bool:
        """Whether this IO looks like the main gate trigger (TRG/gate)."""
        name = self.io_name.upper()
        return any(tag in name for tag in ("TRG", "TRIGGER", "GATE"))


@dataclass
class GsmDevice:
    """A legacy GSM/ULTRA operator from the GWeb config (MCRConfEnV3).

    These reach the cloud through a GSM/ULTRA module rather than SMART Wi-Fi,
    and are controlled by "activating" one of their IOs (see
    ``CentsysRemoteClient.trigger_gsm_activation``).
    """

    device_id: int
    name: str = ""
    imei: str | None = None
    device_type: int | None = None
    online: bool | None = None
    is_admin: bool | None = None
    ios: list[GsmIo] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Stable id for this device within coordinator data / entities."""
        return f"gsm-{self.device_id}"

    @property
    def trigger_io(self) -> GsmIo | None:
        """The IO to use for a gate open/close (a TRG-like IO, else the first)."""
        if not self.ios:
            return None
        for io in self.ios:
            if io.is_gate_trigger:
                return io
        return self.ios[0]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GsmDevice":
        ios_raw = _pick(data, "IOConfigs", "IoConfigs", "Ios", default=[]) or []
        return cls(
            device_id=int(_pick(data, "DeviceId", default=0)),
            name=str(_pick(data, "DeviceName", default="") or ""),
            imei=_pick(data, "DeviceImei", "Imei"),
            device_type=_pick(data, "DeviceType"),
            online=_pick(data, "DeviceOnline", "Online"),
            is_admin=_pick(data, "DeviceAdmin", "IsAdmin"),
            ios=[GsmIo.from_json(io) for io in ios_raw if isinstance(io, dict)],
            raw=data,
        )


@dataclass
class OperatorStatus:
    """Live status from GetOperatorOverview."""

    operator_serial_number: str
    operator_status: int | None = None
    power_supply_status: int | None = None
    closing_beam_status: int | None = None
    opening_beam_status: int | None = None
    theft_alarm_state: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "OperatorStatus":
        return cls(
            operator_serial_number=data.get("operatorSerialNumber", ""),
            operator_status=data.get("operatorStatus"),
            power_supply_status=data.get("powerSupplyStatus"),
            closing_beam_status=data.get("closingBeamStatus"),
            opening_beam_status=data.get("openingBeamStatus"),
            theft_alarm_state=data.get("theftAlarmState"),
            raw=data,
        )

    @property
    def operator_status_label(self) -> str | None:
        """e.g. 'closed', 'open', 'opening' (None if unmappable)."""
        return enums._label(enums.OperatorStatus, self.operator_status)

    @property
    def power_supply_status_label(self) -> str | None:
        return enums._label(enums.PowerStatus, self.power_supply_status)

    @property
    def theft_alarm_state_label(self) -> str | None:
        return enums._label(enums.TheftAlarmState, self.theft_alarm_state)

    @property
    def closing_beam_label(self) -> str | None:
        """Simplified safety-beam condition (clear/obstructed/disabled/...)."""
        return enums.beam_state(self.closing_beam_status)

    @property
    def opening_beam_label(self) -> str | None:
        return enums.beam_state(self.opening_beam_status)

    @property
    def is_closed(self) -> bool | None:
        if self.operator_status is None:
            return None
        return self.operator_status == enums.OperatorStatus.CLOSED

    @property
    def is_opening(self) -> bool:
        return self.operator_status == enums.OperatorStatus.OPENING

    @property
    def is_closing(self) -> bool:
        return self.operator_status == enums.OperatorStatus.CLOSING
