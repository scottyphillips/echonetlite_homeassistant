# ECHONETLite Platform Custom Component for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]


A Home Assistant custom component for use with ECHONETLite compatible devices.
This custom component makes use of the 'pychonet'
Python library also written by yours truly:
(https://github.com/scottyphillips/pychonet)

**This component will set up the climate, sensor and select platforms.**

# Current working systems:
Based upon feedback this custom component works with the following
compatible ECHONETLite Devices:

* Mitsubishi MAC-568IF-E WiFi Adaptor connected to the following systems:
  * GE Series
     * MSZ-GE42VAD
     * MSZ-GE24VAD
     * MSZ-GL50VGD
     * MSZ-GL35VGD
  * AP Series
     * MSZ-AP22VGD
     * MSZ-AP25VGD
     * MSZ-AP50VGD
  * Ducted
     * PEA-RP140GAA
* 'MoekadenRoom' ECHONETLite Simulator: https://github.com/SonyCSL/MoekadenRoom
     * Generic HVAC Climate
     * Light Sensor
     * Lock Sensor
     * Temperature Sensor
* Sharp AC
     * AY-J22H
     * AY-L40P


## Installation - Enable ECHONET protocol
This Custom Component makes use of the official Mitsubishi MAC-568IF-E WiFi
Adaptor. Other adaptors (indeed other vendors!) may work, but they
must support the 'ECHONET lite' protocol.

From the official Mitsubishi AU/NZ Wifi App, you will need to enable
the 'ECHONET lite' protocol under the 'edit unit' settings.

![echonet][echonetimg]

## Installation - if previously installed versions prior to 3.0.1 (mitsubishi component)
1. Delete 'mitsubishi' from your 'custom_components' directory
2. Remove references to 'mitsubishi' from 'configuration.yaml'

## Installation - Home Assistant
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `echonetlite`.
4. Download _all_ the files from the `custom_components/echonetlite/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant and clear your browser cache
7. Go to configuration -> integrations -> ADD INTEGRATION.
5. Select the 'echonetlite' integration. Enter your IP address in the host field, and give the platform a name.
6. Platform should automatically configure 'climate', and depending on your system will automatically configure 'sensor' and 'select'.
7. If you have additional HVACs to configure then repeat step 4.

## Configuring Options for Fan and swing mode settings for supported hvac_modes.
Once you have added the integration, you can go back to configuration -> integrations
Under your ECHONETLite device click 'configure'
Fine tune your required fan and swing mode settings. The integration will be able to determine what settings are supported for your system in question.
NOTE: Selecting which specific options are suitable is a 'trial and errror' process as ECHONETLite does not provide a means of returning permittted values for these settings
As soon as you configure your options and save, the settings will take effect.


## Hall of Fame
Thanks to Jason Nader for all the quality of life updates to the codebase and doco.

Thanks to khcnz (Karl Chaffey) and gvs for helping refector the old code
and contributing to testing.

Thanks to Dick Swart, Masaki Tagawa, Paul, khcnz,  Kolodnerd, and Alfie Gerner
for each contributing code updates to to the original 'mitsubishi_hass'
and therefore this custom component.

Thanks to Jeffro Carr who inspired me to write my own native Python ECHONET
library for Home Assistant. I could not get his Node JS Docker container
to work properly on Hass.io :-)
Some ideas in his own repo got implemented in my own code.
(https://github.com/jethrocarr/echonetlite-hvac-mqtt-service.git)

Also big thanks to Futomi Hatano for open sourcing a high quality and
extremely well documented ECHONET Lite library in Node JS that formed
the basis of my reverse engineering efforts.
(https://github.com/futomi/node-echonet-lite)


## License

This application is licensed under an MIT license, refer to LICENSE for details.

***
[mitsubishi_hass]: https://github.com/scottyphillips/mitsubishi_hass
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/scottyphillips/mitsubishi_hass.svg?style=for-the-badge
[releases]: https://github.com/scottyphillips/mitsubishi_hass/releases
[license-shield]:https://img.shields.io/github/license/scottyphillips/mitsubishi_hass?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/RgKWqyt?style=for-the-badge
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Scott%20Phillips-blue?style=for-the-badge
[echonetimg]: ECHONET.jpeg
