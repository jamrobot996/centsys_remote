# CenSys Gate Remote for Home Assistant (Custom Fork)

> **Note:** This repository is a custom fork of the original [lex-campbell/centsys_remote](https://github.com/lex-campbell/centsys_remote). We have built upon the original foundation to add persistent MQTT telemetry, delivering near-instant status updates for sliding gates. Please see our [Improvements Report](centsys_improvements_report.md) for full details on the enhancements we made.

Control and monitor your Centurion gate operator directly from Home Assistant. Works flawlessly with **SMART Wi-Fi operators** (including the **Centurion D3 Smart+** and **D5 Evo SMART**) and older **GSM/ULTRA** operators via cellular.

## Features & Improvements
- **Gate Cover Control**: Open and close your gate directly from HA.
- **Near-Instant Live Status**: Our custom persistent MQTT listener updates your gate's status (`opening → open → closing → closed`) in 1-2 seconds.
- **Rich Diagnostics**: Monitor battery voltage, mains/power status, safety beams, and Wi-Fi signal.
- **Dedicated Debug Logging**: Optional log file (`Centsys_cloud_logs.txt`) for easy troubleshooting.
- **Simple Onboarding**: Sign in with your phone number and an OTP via WhatsApp or SMS.

## Installation
1. Download this repository.
2. Copy the `custom_components/centsys_remote` folder into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant (a full restart is required to install dependencies).
4. Go to **Settings → Devices & Services → Add Integration**, search for **CenSys Gate Remote**, and complete the setup using your mobile number.

## Requirements
- Home Assistant 2024.1+
- A Centurion gate operator already set up in the official MyCentsys Remote app.
- The phone number must be added as a **remote user** on the operator in the app.
- Outbound internet access from Home Assistant.

## Advanced Usage
You can use the integration to build advanced automations, such as:
- **Audio alerts**: Trigger a chime on a wall-mounted tablet when the gate opens using Browser Mod.
- **iOS critical notifications**: Get a critical push notification if the gate is left open for an extended period.

For full technical details on our architectural modifications and performance enhancements, refer to the [Improvements Report](centsys_improvements_report.md).

---
*Original base integration released under the [MIT License](LICENSE).*
