[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

# ECHONETLite Platform for Home Assistant

_Component to integrate ECHONETLite compatable HVAC systems using the [pychonet][pychonet] library._

**This component will set up the following platforms.**

Platform | Description
-- | --
`climate` | Interface to ECHONETLite API to control your ECHONETLite compatible HVAC (Commonly found in Asia-Pacific regions)
`sensor`  | Interface to ECHONETLite API to poll indoor and outdoor temperature sensors
`select`  | Interface to ECHONETLite API to provide drop down menus for swing modes

![example][exampleimg]

{% if not installed %}
## Installation

1. Click install and then reload Home Assistant.
2. Platform 'echonetlite' should be added to 'custom_components' directory
3. You may also need to clear your browser cache.
4. Go to configuration -> integrations -> ADD INTEGRATION.
5. Select the 'echonetlite' integration. Enter your IP address in the host field, and give the platform a name.
6. Platform should automatically configure 'climate' and depending on your system will configure 'sensor' and 'select'
6. If you have additional HVACs then repeat step 4.

{% endif %}

## Enable ECHONETLite protocol
This Custom Component has been designed to be compatable with the following HVAC systems:  
Mitsubishi MAC-568IF-E WiFi adaptor
MoekadenRoom ECHONETLite Emulator (https://github.com/SonyCSL/MoekadenRoom)

Other vendor HVAC systems may work, but they must support the 'ECHONETlite' protocol.

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
[mitsubishi_hass]: https://github.com/scottyphillips/mitsubishi_hass
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/scottyphillips/mitsubishi_hass.svg?style=for-the-badge
[releases]: https://github.com/scottyphillips/mitsubishi_hass/releases
[license-shield]:https://img.shields.io/github/license/scottyphillips/mitsubishi_hass?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/RgKWqyt?style=for-the-badge
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Scott%20Phillips-blue?style=for-the-badge
[exampleimg]: https://raw.githubusercontent.com/scottyphillips/mitsubishi_hass/master/Mitsubishi.jpg
[echonetimg]: https://raw.githubusercontent.com/scottyphillips/mitsubishi_hass/master/ECHONET.jpeg
