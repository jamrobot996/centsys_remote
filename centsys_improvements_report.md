# CenSys Remote — Field Report & Enhancements from a Real-World Deployment

We have been running a modified version of your integration in daily production on a Centurion D3 Smart+ sliding gate, and after some field-driven enhancements it is now **working flawlessly**. We wanted to share what we learned and built on top of your foundation, in case any of it is useful for the project going forward.

We have reviewed the latest upstream release (v0.3.3) and confirmed that all of the enhancements described below remain unique to our deployment and are not yet present in the official codebase.

> [!NOTE]
> Our deployment is **strictly a sliding gate operation** (Centurion D3 Smart+). We have not tested with garage-door operators, swing gates, or GSM/ULTRA units. All observations and enhancements below are specific to the Wi-Fi sliding gate use case.

---

## 1. Persistent MQTT Listener (`api/mqtt_listener.py`)

**What we observed:** The telemetry approach in v0.3.0 through to the current v0.3.3 uses a "connect → fetch → disconnect" one-shot pattern for MQTT (via `_maybe_refresh_telemetry()`). In practice, on our D3 Smart+, this meant the gate state in Home Assistant could lag behind the real world by up to a full polling cycle. If someone opened the gate with the physical remote or the MyCentsys app, HA wouldn't reflect the change until the next HTTP poll.

**What we built:** A new 350-line `MqttListener` class (`api/mqtt_listener.py`) that maintains a **single long-lived MQTT connection** for the lifetime of the config entry. Key design details:

- **Persistent subscription** to `<serial>/deviceOverview` and `<serial>/connectionRequestResponse` for every registered Wi-Fi gate
- **Periodic wake packets** (`connectionRequest` + `cmd01` identity) sent every 15 seconds to keep the gate's telemetry radio active — the gate broadcasts at ~1 msg/sec while moving, but goes silent when idle unless woken
- **Separate MQTT client ID** (`mcrl:<number>`) so the persistent listener and the trigger client (`mcr:<number>`) can coexist on the broker without session conflicts
- **Automatic reconnection** with exponential backoff (5s → 120s cap), re-fetching the mTLS certificate on each attempt to handle certificate expiry gracefully
- **Dynamic gate management** — new gates are subscribed immediately when discovered on a poll cycle; removed gates are explicitly unsubscribed
- **Thread-safe callback** from paho's network thread to HA's event loop via `loop.call_soon_threadsafe`
- **Temp file cleanup** for PEM certificate files on disconnect

**Result:** Gate state changes from *any* source (physical remote, MyCentsys app, keypad, HA) are now reflected in the Home Assistant UI within ~1–2 seconds.

---

## 2. Coordinator Changes (`coordinator.py`)

To support the persistent MQTT listener, we made the following changes to `CentsysCoordinator`:

| Aspect | Original (v0.3.0) | Our Enhancement |
|---|---|---|
| Telemetry fetch | `_maybe_refresh_telemetry()` — periodic one-shot MQTT connection | `_ensure_mqtt_listener()` — starts/updates the persistent listener on every poll |
| Overview storage | `_overview` dict only | `_overview` + `_overview_ts` (per-serial timestamps) |
| Freshness check | None | `is_overview_fresh(serial, max_age)` method |
| Lifecycle | No MQTT teardown | `async_stop_mqtt_listener()` called from `async_unload_entry()` |

**New constants added to `const.py`:**
- `MQTT_WAKE_INTERVAL = 15` — wake packet cadence (seconds)
- `OVERVIEW_FRESHNESS_TTL = 45.0` — max age before falling back to HTTP poll (≈ 3 missed wake cycles)

The `_handle_live_overview()` callback receives real-time MQTT frames and pushes them directly into the coordinator's data dict, then calls `async_update_listeners()` so all entities update instantly.

---

## 3. Cover Entity Simplification (`cover.py`)

With the persistent MQTT listener handling all the real-time state tracking centrally, we were able to **significantly simplify** the `CentsysGateCover` class:

**Removed:**
- `_live_status`, `_live_expiry`, `_following` instance variables
- The per-entity `_start_live_follow()` polling mechanism

**Replaced with:**
- A single `_fresh_overview` property that queries the coordinator's cached MQTT data with freshness checking via `coordinator.is_overview_fresh()`
- `is_closed`, `is_opening`, `is_closing` properties that prioritize `_fresh_overview` and gracefully fall back to the HTTP-polled `operatorStatus`

This keeps the entity code clean and stateless — all the complexity lives in the listener and coordinator where it belongs.

---

## 4. Debug Logging Enhancement (`__init__.py`)

During our initial setup and troubleshooting, we found it very helpful to have a **dedicated log file** for the integration rather than hunting through the main HA log. We added a simple file logger in `async_setup_entry()`:

```python
log_path = hass.config.path("Centsys_cloud_logs.txt")
handler = await hass.async_add_executor_job(logging.FileHandler, log_path)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger = logging.getLogger("custom_components.centsys_remote")
logger.setLevel(logging.DEBUG)
if not any(isinstance(h, logging.FileHandler) and 
           h.baseFilename == log_path for h in logger.handlers):
    logger.addHandler(handler)
```

This writes all integration debug output to `Centsys_cloud_logs.txt` in the HA config directory, with a guard against duplicate handlers on reload. It was invaluable for diagnosing MQTT connection issues and understanding the telemetry payload structure.

**Suggestion:** This could potentially be offered as an optional toggle in the config flow (e.g., "Enable debug file logging") for users who need to troubleshoot without enabling debug logging for the entire HA instance.

---

## 5. Optional User-Experience Enhancements

Beyond the core integration changes, we built two companion features in our Home Assistant setup that significantly improved the daily experience of living with the gate. These are not changes to the integration code itself, but rather automations that leverage the integration's entities — shared here in case they inspire ideas for documentation or optional features.

### 5a. iOS Push Notification on Gate Open

We created a Home Assistant automation that sends an **instant push notification** to all household iPhones/iPads via the HA Companion App whenever the gate cover entity transitions to `open`. This gives everyone in the family immediate awareness when the gate opens — whether triggered by HA, the physical remote, or the MyCentsys app.

```yaml
trigger:
  - entity_id: cover.46_wilson_st  # The CenSys gate cover entity
    to: open
    trigger: state
action:
  - action: notify.mobile_app_<device>
    data:
      title: "Gate Alert"
      message: "The front gate has opened"
```

**Why it matters:** Because the persistent MQTT listener gives us near-instant state updates, the notification arrives within seconds of the gate actually moving — making it genuinely useful for security awareness.

### 5b. Browser Mod Audio Alert on Wall-Mounted Display

For our wall-mounted iPad running HA as a kiosk dashboard, we added a **Browser Mod** media player action to play an audible chime (Airbus-style alert tone) through the tablet's speakers whenever the gate opens. This gives an immediate in-home audio cue without needing a separate speaker system.

```yaml
trigger:
  - entity_id: cover.46_wilson_st
    to: open
    trigger: state
action:
  - action: media_player.play_media
    target:
      entity_id: media_player.browser_mod_<device_id>
    data:
      media_content_id: "/local/sounds/Airbus.mp3"
      media_content_type: music
```

**Dependencies:** Requires the [Browser Mod](https://github.com/thomasloven/hass-browser_mod) custom integration with the display device registered as a media player.

---

## 6. Note: Garage-Door Operator Support

We noticed that your v0.3.2/v0.3.3 releases added the `_SDO_GATE_STATUS` enum, the `input_voltage` telemetry field, and garage-door specific battery divisor logic in `mqtt_remote.py`. Our local v0.3.1 copy does **not** have these additions, as we are running a sliding gate exclusively and did not need them. We plan to sync these from your latest release to stay current.

---

## Summary

| Enhancement | Files Modified/Added | Benefit |
|---|---|---|
| Persistent MQTT Listener | `api/mqtt_listener.py` (NEW) | Near-instant gate state from any source |
| Coordinator MQTT lifecycle | `coordinator.py`, `const.py` | Centralised MQTT management with freshness TTL |
| Simplified cover entity | `cover.py` | Clean, stateless entity relying on coordinator cache |
| Debug file logging | `__init__.py` | Dedicated log file for easier troubleshooting |
| iOS notifications | HA automation (not integration code) | Mobile security awareness |
| Browser Mod audio | HA automation (not integration code) | In-home audible gate alert |

All of the above has been running in daily production on a **Centurion D3 Smart+ sliding gate** and is working flawlessly. We are happy to provide any additional detail, logs, or code if any of this is useful for the project.
