"""Constants for the CenSys Gate Remote integration."""

from __future__ import annotations

DOMAIN = "centsys_remote"

CONF_MOBILE_NUMBER = "mobile_number"
CONF_COUNTRY = "country"
CONF_TOKEN = "token"
CONF_NAME = "name"
CONF_EMAIL = "email"

# OTP delivery channel (matches the app's OtpPlatformEnum).
OTP_PLATFORM_WHATSAPP = 1
OTP_PLATFORM_SMS = 2
DEFAULT_OTP_PLATFORM = OTP_PLATFORM_WHATSAPP

CONF_OTP_PLATFORM = "otp_platform"

# Cloud polling cadence (seconds) for device list + operator status.
DEFAULT_SCAN_INTERVAL = 60

# Wi-Fi MQTT telemetry wake interval (seconds).  The persistent MQTT listener
# sends a wake packet to each Wi-Fi gate at this cadence to keep its telemetry
# radio active.  This drives near-real-time state updates (~1-2 s latency).
TELEMETRY_SCAN_INTERVAL = 15

# Persistent MQTT listener wake interval (seconds) — mirrors TELEMETRY_SCAN_INTERVAL.
MQTT_WAKE_INTERVAL = 15

# Maximum age (seconds) for an MQTT overview frame to be considered
# authoritative over the HTTP poll.  If the persistent listener hasn't
# delivered a fresh frame within this window, the cover entity falls back to
# the HTTP-polled status.  45 s ≈ 3 missed wake cycles.
OVERVIEW_FRESHNESS_TTL = 45.0

# WARNING: The 15-second telemetry cadence above is designed for Wi-Fi
# operators ONLY.  GSM/ULTRA devices communicate over the cellular network and
# should NOT be polled at this rate — doing so would generate excessive
# cellular traffic and could deplete prepaid airtime.  GSM diagnostics use
# the dedicated GSM_DIAG_SCAN_INTERVAL below.
GSM_DIAG_SCAN_INTERVAL = 900  # 15 minutes — safe for cellular devices

# Legacy GWeb (GSM/ULTRA) device config changes rarely; refresh it on a slower
# cadence than the main cloud status to avoid extra round-trips every poll.
GSM_SCAN_INTERVAL = 300

# After an on-demand airtime request, the operator queries its balance over the
# cellular network and syncs back asynchronously, so poll the cached status a
# few times to pick up the result.
AIRTIME_POLL_INTERVAL = 8
AIRTIME_POLL_ATTEMPTS = 12

PLATFORMS = ["binary_sensor", "button", "cover", "sensor"]

MANUFACTURER = "Centurion Systems (CenSys)"
