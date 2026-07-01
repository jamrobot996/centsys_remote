"""Buttons for CenSys Gate Remote."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.exceptions import CentsysError
from .const import DOMAIN
from .coordinator import CentsysCoordinator
from .entity import CentsysGsmEntity, async_setup_dynamic_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CentsysCoordinator = hass.data[DOMAIN][entry.entry_id]

    def _factory(key: str):
        data = coordinator.data.get(key) or {}
        if data.get("kind") == "gsm":
            return [CentsysGsmAirtimeButton(coordinator, key)]
        return []

    async_setup_dynamic_entities(entry, coordinator, async_add_entities, _factory)


class CentsysGsmAirtimeButton(CentsysGsmEntity, ButtonEntity):
    """Request a network-balance (airtime) refresh for a GSM/ULTRA operator.

    Pressing this asks the operator to query its balance over the cellular
    network (a billable action), then the call/SMS token sensors update once the
    result syncs back. It is the only way to populate those sensors, so airtime
    is never fetched automatically.
    """

    _attr_translation_key = "gsm_refresh_airtime"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CentsysCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{key}_refresh_airtime"

    async def async_press(self) -> None:
        device = self._gsm_device
        if device is None:
            raise HomeAssistantError("This gate has no GSM device to query.")
        try:
            await self.coordinator.client.request_gsm_airtime(device.device_id)
        except CentsysError as err:
            raise HomeAssistantError(f"Couldn't request airtime: {err}") from err
        self.coordinator.async_schedule_airtime_refresh(self._key, device.device_id)
