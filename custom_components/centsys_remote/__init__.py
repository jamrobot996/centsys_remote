"""The CenSys Gate Remote integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import CentsysCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CenSys Gate Remote from a config entry."""
    # Optional dedicated debug file logging.  When enabled via the integration
    # options, all debug output is also written to Centsys_cloud_logs.txt in
    # the HA config directory — invaluable for diagnosing MQTT and telemetry
    # issues without enabling debug for the entire HA instance.
    if entry.options.get("enable_debug_logging", False):
        log_path = hass.config.path("Centsys_cloud_logs.txt")
        handler = await hass.async_add_executor_job(logging.FileHandler, log_path)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger = logging.getLogger("custom_components.centsys_remote")
        logger.setLevel(logging.DEBUG)
        if not any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", None) == handler.baseFilename
            for h in logger.handlers
        ):
            logger.addHandler(handler)
            _LOGGER.info("Debug file logging enabled: %s", log_path)

    coordinator = CentsysCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: CentsysCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop_mqtt_listener()
        coordinator.dismiss_no_devices_notice()
    return unload_ok
