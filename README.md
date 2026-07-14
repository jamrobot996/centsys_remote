# CenSys Gate Remote for Home Assistant (Custom Fork)

> **Note:** This repository is a custom fork of the original [lex-campbell/centsys_remote](https://github.com/lex-campbell/centsys_remote). We have completely overhauled the architecture to add persistent MQTT telemetry and optimistic UI updates, delivering **0ms latency** for Home Assistant triggers and real-time telemetry for sliding gates. Please see our [Improvements Report](centsys_improvements_report.md) for full details on the enhancements we made.

Control and monitor your Centurion gate operator directly from Home Assistant. Works flawlessly with **SMART Wi-Fi operators** (including the **Centurion D3 Smart+** and **D5 Evo SMART**) and older **GSM/ULTRA** operators via cellular.

## Features & Improvements
- **Gate Cover Control**: Open and close your gate directly from HA.
- **Zero-Latency UI Updates**: Local optimistic UI updates instantly force the HA state to `opening` or `closing` the millisecond you click the button, triggering your automations with 0ms delay.
- **Real-Time Live Status**: Our custom 24/7 persistent MQTT listener continuously streams your gate's status, instantly pushing physical remote triggers to Home Assistant with < 2ms latency.
- **Rich Diagnostics**: Live monitoring of battery voltage, mains/power status, safety beams, and Wi-Fi signal.
- **Dedicated Debug Logging**: Optional log file (`Centsys_cloud_logs.txt`) for easy troubleshooting.

## ⚠️ Important: The "Service Account" Best Practice
The Centsys cloud MQTT broker enforces a strict rule: **Only one real-time connection is allowed per phone number.**
If you log into Home Assistant using your primary phone number, Home Assistant will permanently monopolize the connection and kick your official MyCentsys Remote phone app off the live stream, causing a 60-second delay for native phone notifications.

**To achieve 0ms latency in Home Assistant WITHOUT breaking your phone app:**
1. Create a "Service Account" using a secondary/backup phone number.
2. In the MyCentsys Remote app (logged in as your primary number), share the gate with the secondary number.
3. **CRITICAL:** You must upgrade the secondary number to an **Admin** in the app. Standard "Remote Users" do not receive live MQTT telemetry.
4. Log into this Home Assistant integration using that secondary number.

## Installation
1. Download this repository.
2. Copy the `custom_components/centsys_remote` folder into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant (a full restart is required to install dependencies).
4. Go to **Settings → Devices & Services → Add Integration**, search for **CenSys Gate Remote**, and complete the setup using your secondary "Service Account" mobile number.

## Requirements
- Home Assistant 2024.1+
- A Centurion gate operator already set up in the official MyCentsys Remote app.
- Outbound internet access from Home Assistant.

## Advanced Usage
Because this fork operates with 0ms latency, it is perfect for real-time automations:
- **Instant Audio Alerts**: Trigger an alarm chime on a wall-mounted tablet the exact millisecond the gate begins to move.
- **Critical Security Pushes**: Receive critical iOS push notifications if the gate is opened via an unauthorized physical remote.

For full technical details on our architectural modifications and performance enhancements, refer to the [Improvements Report](centsys_improvements_report.md).

---
*Original base integration released under the [MIT License](LICENSE).*
