[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

# ECHONETLite Platform for Home Assistant

_Component to integrate ECHONETLite compatable HVAC systems using the [pychonet][pychonet] library._

**This component will set up the following platforms.**

Platform | Description
-- | --
`climate` | Interface to ECHONETLite API to control your ECHONETLite compatible HVAC (Commonly found in Asia-Pacific regions)
`sensor`  | Interface to ECHONETLite API to poll indoor and outdoor temperature sensors.
`select`  | Interface to ECHONETLite API to provide drop down menus for swing modes.
`light`   | Interface to ECHONETLite API to provide light functionality for supported devices.
`light`   | Interface to ECHONETLite API to provide fan functionality for supported devices.

![example][exampleimg]

{% if not installed %}
## Pre-installation - if previously installed versions prior to 3.0.1
1. Delete 'mitsubishi' from your 'custom_components' directory
2. Remove references to 'mitsubishi' from 'configuration.yaml'

## Installation
1. Click install and then reload Home Assistant.
2. Platform 'echonetlite' should be added to 'custom_components' directory
3. You may also need to clear your browser cache.
4. Go to configuration -> integrations -> ADD INTEGRATION.
5. Select the 'echonetlite' integration. Enter your IP address in the host field, and give the platform a name.
6. Platform should automatically configure 'climate' and depending on your system will configure 'sensor' and 'select'
6. If you have additional HVACs then repeat step 4.

{% endif %}

# Current working systems:
Based upon feedback this custom component works with the following
compatible ECHONETLite Devices:

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
  * Ducted
     * PEA-M100GAA
     * PEA-RP140GAA

* Mitsubishi HM-W002-AC WiFi Adaptor connected to the following systems:
  * JXV Series
     * MSZ-JXV4018S

* 'MoekadenRoom' ECHONETLite Simulator: https://github.com/SonyCSL/MoekadenRoom
     * Generic HVAC Climate
     * Light Sensor
     * Lock Sensor
     * Temperature Sensor

* Sharp
     * Air Conditioners
         * AY-J22H
         * AY-L40P
     * Air Purifier
         * KI-HS70

* Daikin (ECHONETLite enabled models)
* Koizumi
     * Lighting system AE50264E bridge (https://www.koizumi-lt.co.jp/product/jyutaku/tree/ )

## Mitsubishi MAC-568IF-E
From the official Mitsubishi AU/NZ Wifi App, you will need to enable
the 'ECHONET lite' protocol under the 'edit unit' settings.

## Support for Other ECHONETLite devices
At present this platform is somewhat hard coded to HVACs but can be modified for other uses as needed.
If you have ECHONETLite devices that are not HVACs and you would like to use them
via this integration then please raise an issue or better yet a PR.

![echonet][echonetimg]

***
[pychonet]: https://github.com/scottyphillips/pychonet
[echonetlite_homeassistant]: https://github.com/scottyphillips/echonetlite_homeassistant
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/scottyphillips/echonetlite_homeassistant.svg?style=for-the-badge
[releases]: https://github.com/scottyphillips/echonetlite_homeassistant/releases
[license-shield]:https://img.shields.io/github/license/scottyphillips/echonetlite_homeassistant?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/RgKWqyt?style=for-the-badge
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Scott%20Phillips-blue?style=for-the-badge
[exampleimg]: https://raw.githubusercontent.com/scottyphillips/echonetlite_homeassistant/master/Mitsubishi.jpg
[echonetimg]: https://raw.githubusercontent.com/scottyphillips/echonetlite_homeassistant/master/ECHONET.jpeg
