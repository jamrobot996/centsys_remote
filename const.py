"""Constants for the CenSys Gate Remote integration."""

from __future__ import annotations

DOMAIN = "centsys_remote"

CONF_MOBILE_NUMBER = "mobile_number"
CONF_TOKEN = "token"
CONF_NAME = "name"
CONF_EMAIL = "email"

DEFAULT_OTP_PLATFORM = 1

# Cloud polling cadence (seconds) for device list + operator status.
DEFAULT_SCAN_INTERVAL = 60

# MQTT telemetry (battery voltage etc.) is far heavier than the HTTP poll: it
# opens a TLS session and wakes the operator's Wi-Fi radio, so we refresh it on
# a much slower cadence than the cloud status.
TELEMETRY_SCAN_INTERVAL = 900

PLATFORMS = ["binary_sensor", "cover", "sensor"]

MANUFACTURER = "Centurion Systems (CenSys)"
