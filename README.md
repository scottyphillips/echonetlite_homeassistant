# ECHONETLite Platform Custom Component for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
([日本語](https://github.com/scottyphillips/echonetlite_homeassistant/blob/master/README.ja.md))

A Home Assistant custom component for use with ECHONETLite compatible devices.
This custom component makes use of the [pychonet](https://github.com/scottyphillips/pychonet)
Python3 library also maintained by this author.

This integration supports any device that implements the ECHONET Lite protocol, 
regardless of whether the device class appears in the Machine Readable Appendix (MRA). 
New device classes can be added via pychonet without constraint.

## Why ECHONETLite Platform?

- **Broad device support** — any ECHONET Lite compatible device is supported, 
  including device classes not documented in the Machine Readable Appendix (MRA)
- **Battle-tested** — maintained (more or less) since 2018 across a wide range of real-world 
  hardware including non-compliant firmware
- **Hybrid push/poll** — push notifications for responsive state updates, 
  polling for EPCs not covered by the device's notification map
- **Works on any network** — no dependency on reliable multicast; always_poll option
  ensures devices are always reachable even on segmented or managed networks
- **Device quirks system** — manufacturer and model-specific EPC overrides 
  for devices that deviate from the ECHONET Lite specification
- **Compound sensor support** — sensors that combine multiple EPCs 
  (e.g. energy readings scaled by a device-reported coefficient)
- **Active development** — LLM-assisted development workflow enables rapid 
  response to bug reports and new device support

**This component will set up the climate, fan, sensor, select and switch platforms.**

---

## Supported Devices

| **Manufacturer**    | **Device**                                     | **ECHONET Class**              | **HA Entities**                  | **Notes**                                                                                         |
|:--------------------|:-----------------------------------------------|:-------------------------------|:---------------------------------|:--------------------------------------------------------------------------------------------------|
| Mitsubishi Electric | MAC-5xx/6xx/9xx WiFi Adaptors                  | HomeAirConditioner             | Climate, Sensor, Select          | See [Mitsubishi WiFi Adaptor compatibility](#mitsubishi-wifi-adaptor-compatibility) below          |
| Mitsubishi Electric | HM-W002-AC                                     | HomeAirConditioner             | Climate, Sensor, Select          | See [Mitsubishi WiFi Adaptor compatibility](#mitsubishi-wifi-adaptor-compatibility) below          |
| Mitsubishi Electric | Eco-Cute SRT-S466A + RMCB-H6SE-T               | ElectricWaterHeater            | Sensor, Select, Switch           |                                                                                                   |
| Mitsubishi Electric | REF-WLAN001                                    | Refrigerator                   | Sensor                           | MR-WZ55H confirmed                                                                                |
| Fujitsu General     | OP-J03DZ WiFi Adaptor                          | HomeAirConditioner             | Climate, Sensor, Select          | Nocria C & V Series confirmed                                                                     |
| Sharp               | AY-J22H, AY-XP12YHE, AY-XP24YHE, AY-L40P     | HomeAirConditioner             | Climate, Sensor, Select          |                                                                                                   |
| Sharp               | KI-HS70 Air Purifier                           | HomeAirCleaner                 | Fan, Sensor, Select              |                                                                                                   |
| Sharp               | JH-RWL8 Multi Energy Monitor                   | HomeSolarPower, StorageBattery | Sensor, Select                   |                                                                                                   |
| Panasonic           | CS-221DJ, CS-362DJ2 Air Conditioners           | HomeAirConditioner             | Climate, Sensor, Select          |                                                                                                   |
| Panasonic           | HF-JA2-W                                       | —                              | Sensor                           | IP/JEM-A conversion adapter                                                                       |
| Panasonic           | Link Plus WTY2001                              | GeneralLighting, LightingSystem| Light, Select                    | Lighting system is selector of preset scene                                                       |
| Panasonic           | Smart Cosmo Type LAN (MKN7350S1)               | DistributionPanelMeter         | Sensor                           |                                                                                                   |
| Daikin              | ECHONETLite enabled HVAC models                | HomeAirConditioner             | Climate, Sensor, Select          |                                                                                                   |
| Rinnai              | Hot water systems (ECHONETLite enabled)        | —                              | Sensor, Switch, Input            | Input entity for Hot Water Timers — see [Services.md](Services.md)                                |
| Noritz              | Bathtub and floor heating system               | HotWaterGenerator              | Sensor, Switch                   |                                                                                                   |
| Koizumi             | AE50264E Lighting bridge                       | LightingSystem                 | Light, Sensor                    | https://www.koizumi-lt.co.jp/product/jyutaku/tree/                                                |
| OMRON               | Home Solar Power Generation                    | —                              | Switch, Sensor                   | Full support for HA Energy Dashboard                                                               |
| KDK                 | ECHONETLite enabled Ceiling Fans               | CeilingFan, GeneralLighting    | Fan, Light, Sensor               | Rebranded Panasonic — confirmed E48GP, H56G, F40GP                                                |
| JDM Electric Meters | Low voltage smart meter (B route)              | —                              | Sensor                           | Requires Wi-SUN ↔ Ethernet/WiFi bridge — [nao-pon/python-echonet-lite](https://github.com/nao-pon/python-echonet-lite) |
| Sony                | MoekadenRoom ECHONETLite Simulator             | —                              | Climate, Select, Switch, Sensor  | https://github.com/SonyCSL/MoekadenRoom                                                           |

---

## Mitsubishi WiFi Adaptor Compatibility

| **WiFi Adaptor**  | **Compatible Systems**                                                                                                            |
|:------------------|:----------------------------------------------------------------------------------------------------------------------------------|
| MAC-568IF-E       | GE: MSZ-GE42VAD, GE24VAD, GL71VGD, GL50VGD, GL35VGD, GL25VGD<br>AP: MSZ-AP22VGD, AP25VGD, AP50VGD<br>LN: MSZ-LN25VG2, LN35VG2, LN50VG2<br>Ducted: PEA-M100GAA, PEA-M100HAA, PEA-RP140GAA<br>Bulkhead: SEZ-M71DA |
| MAC-577IF-E       | MSZ-BT35VGK                                                                                                                       |
| MAC-577IF2-E      | MSZ-BT35VGK                                                                                                                       |
| MAC-578IF2-E      | AP: MSZ-AP22VGD, AP35VGD, AP50VGD<br>Ducted: PEAD-RP71                                                                          |
| MAC-587IF-E       | Ducted: PEAD-M50JA2                                                                                                               |
| MAC-588IF-E       | Ducted: PEA-M200LAA, PEAD-M71JAA                                                                                                  |
| MAC-600IF         | Z Series: MSZ-ZW4022S                                                                                                             |
| MAC-900IF         | Z Series: MSZ-ZW4024S<br>XD Series: MSZ-XD2225<br>R Series: MSZ-BKR2223                                                         |
| HM-W002-AC        | JXV Series: MSZ-JXV4018S                                                                                                          |

---

This list reflects community-confirmed devices. Any ECHONET Lite compatible device is or can be supported — device classes not yet listed can be added to pychonet without constraint by the Machine Readable Appendix.

## Installation — Enable ECHONET Protocol

This component was originally designed for the Mitsubishi MAC-568IF-E WiFi Adaptor.
From the official Mitsubishi AU/NZ WiFi App, enable the 'ECHONET lite' protocol under 'edit unit' settings.

![echonet][echonetimg]

> Note: The proprietary Mitsubishi app (MELCloud/MELView/Kumo Cloud) controls some models in single °F or half °C, but ECHONET works in whole °C.

Many other products will work using this component but must correctly support the ECHONET Lite protocol. The author cannot assist with enabling ECHONET Lite for other vendor products.

**Network:** If you have a firewall, ensure UDP port 3610 is unblocked. ([ECHONET Lite Spec](https://echonet.jp/spec_v113_lite_en/))

---

## Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=scottyphillips&repository=echonetlite_homeassistant&category=integration)

1. Click the badge above or search 'ECHONETLite Platform' in HACS integrations
2. Click **Download**, then **Download** again
3. Restart Home Assistant

### Manual

1. Open the directory for your HA configuration (where `configuration.yaml` is located)
2. Create a `custom_components` directory if it doesn't exist
3. Inside it, create a folder called `echonetlite`
4. Download all files from `custom_components/echonetlite/` in this repository into that folder
5. Restart Home Assistant and clear your browser cache

---

## Setup

1. Go to **Settings → Devices & Services → ADD INTEGRATION**
2. Select **ECHONET Lite** and enter the IP address of your device
3. The integration will automatically configure supported platforms (climate, sensor, switch, fan, select)
4. Repeat for additional devices

---

## Enabling Hidden ECHONET Support on Additional Mitsubishi Adaptors

Some Mitsubishi WiFi adaptors have hidden ECHONET Lite support that can be unlocked:

```bash
curl -H 'Content-Type: text/xml' -d '<?xml version="1.0" encoding="UTF-8"?><ESV>7WVvmfhMYzGVi70nyFhmKEy9Jo3Hg3994vi9y1kEgDFWd/1ch9RWDUgY4HgsvMHFvP93fQ30AvEJCNcd0GTwPID0F8V5eyMVj/qAQCXFqYrRtJh8MIpm2/h7jZ2SsPj0</ESV>' "http://${ip}/smart"
```

Replace `${ip}` with your adaptor's IP address. See [issue #226](https://github.com/scottyphillips/echonetlite_homeassistant/issues/226) for details.

---

## Options — Fan and Swing Mode Settings

After adding the integration, go to **Configuration → Integrations**, find your ECHONETLite device and click **Configure** to fine-tune fan and swing mode settings.

> Note: Determining which options are supported is a trial-and-error process as ECHONET Lite does not expose permitted values for these settings.

---
## Polling Behaviour

By default, EPCs that the device reports via push notifications (STATMAP) are 
excluded from the regular poll cycle — the integration relies on the device 
pushing state changes rather than polling for them. This reduces network load 
on embedded devices.

If your network does not reliably deliver multicast packets (e.g. managed 
switches with IGMP snooping, VLANs separating IoT devices, or any network 
segmentation), push notifications may not arrive correctly. In this case, 
enable **Force Polling** in the integration options to poll all EPCs on every 
cycle regardless of the notification map.

To configure: **Configuration → Integrations → ECHONETLite → Configure → 
Force Polling**

> Note: Force Polling increases network traffic to the device but ensures 
> all sensor values are always current even without working multicast.

---
## Device Quirks

Some manufacturers implement non-standard EPCs not in the ECHONET Lite specification. To investigate quirks for your device:

1. Enable debug logging on the ECHONETLite integration screen and restart HA
2. Once startup is complete, disable debug logging and download the log
3. Using the device IP address, check the `getmap` and `setmap` data for values above 240 (0xF0)

**Example log entry:**
```
{'eojcc': 130, 'eojci': 1, 'eojgc': 2, 'getmap': [128, 224, 129, 241, 130, 131, 147, 243, 244, 245,
246, 247, 136, 248, 249, 138, 250, 251, 252, 157, 253, 158, 254, 159, 255], 'host': '192.168.0.49',
'manufacturer': 'Rinnai', ...}
```

4. Create a quirks file (e.g. `quirks/Rinnai/all/0282.py`):

```python
from homeassistant.const import CONF_NAME

def _hex(edt):
    return edt.hex()

QUIRKS = {
    0xFA: {
        "EPC_FUNCTION": _hex,
        "ENL_OP_CODE": {CONF_NAME: "FA"},
    },
    0xFD: {
        "EPC_FUNCTION": _hex,
        "ENL_OP_CODE": {CONF_NAME: "FD"},
    },
}
```

5. Restart HA — new entities will appear for the custom EPCs. Observe whether their values change meaningfully during device operation
6. If they do — please raise an issue or submit a PR! 👍

---

## Hall of Fame

Thanks to Naoki Sawada (nao-pon) for creating the switch entity, the custom service call framework, push notification support via multicast, and the Japanese translation. どうもありがとうございます！

Extra special thanks to sayurin.

Thanks to scumbug, lordCONAN, and xen2 for contributing some very interesting devices.

Thanks to Jason Nader for quality of life updates to the codebase and documentation.

Thanks to khcnz (Karl Chaffey) and gvs for helping refactor the old code and contributing to testing.

Thanks to Dick Swart, Masaki Tagawa, Paul, khcnz, Kolodnerd, and Alfie Gerner for contributing code updates to the original 'mitsubishi_hass' and therefore this component.

Thanks to Jeffro Carr who inspired me to write a native Python ECHONET library for Home Assistant.
(https://github.com/jethrocarr/echonetlite-hvac-mqtt-service.git)

Thanks to Futomi Hatano for open sourcing a high quality and well documented ECHONET Lite library in Node JS that formed the basis of the pychonet library.
(https://github.com/futomi/node-echonet-lite)

Thanks to all other contributors who have raised PRs and issues that turned this weekend project into something useful for many people.

---

## License

MIT License — refer to LICENSE for details.

***
[echonetlite_homeassistant]: https://github.com/scottyphillips/echonetlite_homeassistant
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/scottyphillips/echonetlite_homeassistant.svg?style=for-the-badge
[releases]: https://github.com/scottyphillips/echonetlite_homeassistant/releases
[license-shield]: https://img.shields.io/github/license/scottyphillips/echonetlite_homeassistant?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Scott%20Phillips-blue?style=for-the-badge
[echonetimg]: ECHONET.jpeg