# ECHONETLite Platform Custom Component for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
([日本語](https://github.com/scottyphillips/echonetlite_homeassistant/blob/master/README.ja.md))

A Home Assistant custom component for use with ECHONETLite compatible devices.
This custom component makes use of the 'pychonet'
Python3 library also maintained by this author.
(https://github.com/scottyphillips/pychonet)

**This component will set up the climate, fan, sensor, select and switch platforms.**

# Current working systems:
Based upon feedback this custom component works with the following
compatible ECHONETLite Devices:

| **Manufacturer**    | **Device**                                     | **ECHONETLite Object Class** | **Home Assistant Entities**      | **Notes**                                                                                         |
|:--------------------|:-----------------------------------------------|:-----------------------------|:---------------------------------|:--------------------------------------------------------------------------------------------------|
| Mitsubishi Electric | MAC-568IF-E                                    | HomeAirConditioner           | Climate, Sensor, Select          | WiFi Adaptor connected to various HVAC ducted and split systems. See list below.                  |
| Mitsubishi Electric | HM-W002-AC                                     | HomeAirConditioner           | Climate, Sensor, Select          | WiFi Adaptor connected to various HVAC ducted and split systems. See list below.                  |
| Mitsubishi Electric | MAC-578IF2-E                                   | HomeAirConditioner           | Climate, Sensor, Select          | WiFi Adaptor connected to various HVAC ducted and split systems. See list below.                  |
| Sharp               | AY-J22H Air Conditioner                        | HomeAirConditioner           | Climate, Sensor, Select          |                                                                                                   |
| Sharp               | AY-L40P Air Conditioner                        | HomeAirConditioner           | Climate, Sensor, Select          |                                                                                                   |
| Sharp               | KI-HS70 Air Purifier                           | HomeAirCleaner               | Fan, Sensor, Select              |                                                                                                   |
| Panasonic           | CS-221DJ Air Conditioner                       | HomeAirConditioner           | Climate, Sensor, Select          |                                                                                                   |
| Panasonic           | CS-362DJ2 Air Conditioner                      | HomeAirConditioner           | Climate, Sensor, Select          |                                                                                                   |
| Panasonic           | HF-JA2-W                                       |                              | Sensor                           | IP/JEM-A conversion adapter.                                                                      |
| Rinnai              | Hot water systems (ECHONETLite enabled models) |                              | Sensor, Switch, Input            | Input entity to configure Hot Water Timers can be configured by using a template and a [Service Call](Services.md). |
| Koizumi             | Lighting system AE50264E bridge                | LightingSystem               | Light, Sensor                    | https://www.koizumi-lt.co.jp/product/jyutaku/tree/                                                |
| Daikin              | ECHONETLite enabled HVAC models.               | HomeAirConditioner           | Climate, Sensor, Select          |                                                                                                   |
| OMRON               | Home Solar Power Generation                    |                              | Switch, Sensor                   | Full support for Home Assistant Energy Dashboard including solar production and grid consumption. |
| JDM Electric Meters | Low voltage smart meter (B route service)      |                              | Sensor                           | Require Wi-SUN <-> Ethernet/Wifi bridge. <br> [nao-pon/python-echonet-lite](https://github.com/nao-pon/python-echonet-lite)  |
| Noritz              | Bathtub and floor heating system               | HotWaterGenerator            | Sensor, Switch                   |                                                                                                   |
| KDK                 | ECHONETLite enabled Ceiling Fans               | CeilingFan                   | Fan, Sensor                      | Rebranded Panasonic Ceiling Fan.                                                                  |
| Sony                | 'MoekadenRoom' ECHONETLite Simulator           |                              | Climate, Select, Switch, Sensor  | https://github.com/SonyCSL/MoekadenRoom.                                                          |

* Mitsubishi MAC-568IF-E WiFi Adaptor connected to the following systems:
  * GE Series
     * MSZ-GE42VAD
     * MSZ-GE24VAD
     * MSZ-GL71VGD
     * MSZ-GL50VGD
     * MSZ-GL35VGD
     * MSZ-GL25VGD
  * AP Series
     * MSZ-AP22VGD
     * MSZ-AP25VGD
     * MSZ-AP50VGD
  * LN Series
     * MSZ-LN25VG2
     * MSZ-LN35VG2
     * MSZ-LN50VG2
  * Ducted
     * PEA-M100GAA
     * PEA-RP140GAA

* Mitsubishi HM-W002-AC WiFi Adaptor connected to the following systems:
  * JXV Series
     * MSZ-JXV4018S

* Mitsubishi MAC-578IF2-E WiFi Adaptor connected to the following systems:
  * AP Series
     * MSZ-AP22VGD
     * MSZ-AP35VGD
     * MSZ-AP50VGD
  * Ducted
     * PEAD-RP71
     
## Installation - Enable ECHONET protocol
This Custom Component was originally designed for the Mitsubishi MAC-568IF-E WiFi
Adaptor, a basic guide for enabling ECHONETlite is provided below.

From the official Mitsubishi AU/NZ Wifi App, you will need to enable
the 'ECHONET lite' protocol under the 'edit unit' settings.

![echonet][echonetimg]

Many other products will work using this custom-component, but they must correctly support the 'ECHONET lite' protocol. The author cannot assist with enabling ECHONET Lite for other vendor products.

## Installation
### Install using HACS
1. Look up 'ECHONETLite Platform' in integrations
2. Click 'Download', leave the version be and click 'Download' again.
3. Restart Home Assistant

### Install manually
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `echonetlite`.
4. Download _all_ the files from the `custom_components/echonetlite/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant and clear your browser cache

## Setup
1. In Home Assistant, go to Settings -> Devices & Services -> ADD INTEGRATION.
2. Select the 'ECHONET Lite' integration. Enter the IP address of the HVAC unit in the host field, and give the platform a name.
3. Platform will automatically configure any supported platforms e.g. climate, sensor, switch, fan, select.
4. If you have additional devices to configure then repeat step 1.

## Configuring Options for Fan and swing mode settings for supported HVAC and Air Purifiers.
Once you have added the integration, you can go back to configuration -> integrations.

Under your ECHONETLite device click 'configure'.

Fine tune your required fan and swing mode settings. The integration will be able to determine what settings are supported for your system in question.

NOTE: Selecting which specific options are suitable is a 'trial and error' process as ECHONETLite does not provide a means of returning permittted values for these settings.

As soon as you configure your options and save, the settings will take effect.


## Hall of Fame
Thanks Naoki Sawada for creating the switch entity, creating the custom service call framework, and a ton of other improvements.
Most importantly of all he contributed the translation into 日本語.

Thanks to scumbug, lordCONAN, and xen2 for contributing some very interesting devices. 

Thanks to Jason Nader for all the quality of life updates to the codebase and doco.

Thanks to khcnz (Karl Chaffey) and gvs for helping refector the old code
and contributing to testing.

Thanks to Dick Swart, Masaki Tagawa, Paul, khcnz,  Kolodnerd, and Alfie Gerner
for each contributing code updates to to the original 'mitsubishi_hass' and therefore this custom component.

Thanks to Jeffro Carr who inspired me to write my own native Python ECHONET library for Home Assistant.
Some ideas in his own repo got implemented in my own code.
(https://github.com/jethrocarr/echonetlite-hvac-mqtt-service.git)

Thanks to Futomi Hatano for open sourcing a high quality and well documented ECHONET Lite library in Node JS that formed the basis of the 'Pychonet' library.
(https://github.com/futomi/node-echonet-lite)

Thanks to all other contributers who I might have missed for raising PRs and issues which has made this little weekend project into something useful for many people. 

## License

This application is licensed under an MIT license, refer to LICENSE for details.

***
[echonetlite_homeassistant]: https://github.com/scottyphillips/echonetlite_homeassistant
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/scottyphillips/echonetlite_homeassistant.svg?style=for-the-badge
[releases]: https://github.com/scottyphillips/echonetlite_homeassistant/releases
[license-shield]:https://img.shields.io/github/license/scottyphillips/echonetlite_homeassistant?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/RgKWqyt?style=for-the-badge
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Scott%20Phillips-blue?style=for-the-badge
[echonetimg]: ECHONET.jpeg
