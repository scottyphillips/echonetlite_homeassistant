# mitsubishi_hass
A Home Assistant custom component for use with ECHONET enabled Mitsubishi
HVAC systems. This custom component makes use of the 'mitsubishi_echonet'
Python library also written by yours truly:
(https://github.com/scottyphillips/mitsubishi_echonet)

## Using the library with Home Assistant
'/custom_components/mitsubishi/' is for use with Home Assistant (v0.96+)
Clone this repo and copy the entire contents of '/custom_components/mitsubishi/'
into your 'custom_components' folder within Home Assistant.

In configuration.yaml add the following lines:
```yaml
climate:
  - platform: mitsubishi
    ip_address: 1.2.3.4
```

## Enable ECHONET protocol
This Custom Component makes use of the official Mitsubishi MAC-568IF-E WiFi
Adaptor. Other adaptors (indeed other vendors!) may work, but they
must support the 'ECHONET lite' protocol.

From the official Mitsubishi AU/NZ Wifi App, you will need to enable
the 'ECHONET lite' protocol under the 'edit unit' settings.
Refer to the attached JPEG 'How to turn on ECHONET' for the location in the app.

# Current working systems:
Based upon feedback this custom component works on the following Mitsubishi
HVAC systems all equipped with the MAC-568IF-E WiFi Adaptor:
MSZ-GE42VAD
MSZ-GE24VAD
MSZ-GL50VGD
MSZ-GL35VGD
PEA-RP140GAA

## Fine tuning fan settings.
Optionally, you can also specify what fan settings work with your specific
HVAC system. If no fan speeds are configured, the system will default to 'low'
and 'medium-high'. Just delete the ones you don't need.
A bit of trial and error might be required here.

```yaml
climate:
  - platform: mitsubishi
    ip_address: 192.168.1.6
    name: "mitsubishi_ducted"
    fan_modes:
      - 'minimum'
      - 'low'
      - 'medium-low'
      - 'medium'
      - 'medium-high'
      - 'high'
      - 'very-high'
      - 'max'
```
Comments and suggestions are welcome!

## Thanks
Thanks to Dick Swart and Alfie Gerner who have both contributed code and great
ideas in support of this project.

Thanks to Jeffro Carr who inspired me to write my own native Python ECHONET
library for Home Assistant. I could not get his Node JS Docker container
to work properly on Hass.io :-)
Some ideas in his own repo got implemented in my own code.
(https://github.com/jethrocarr/echonetlite-hvac-mqtt-service.git)

Also big thanks to Futomi Hatano for open sourcing a high quality and
extremely well documented ECHONET Lite library in Node JS that formed
the basis of my reverse engineering efforts.
(https://github.com/futomi/node-echonet-lite)

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

## License

This application is licensed under an MIT license, refer to LICENSE for details.

***
[mitsubishi_hass]: https://github.com/scottyphillips/mitsubishi_hass
[commits-shield]: https://img.shields.io/github/commit-activity/scottyphillips/mitsubishi_hass
[commits]: https://github.com/scottyphillips/mitsubishi_hass/commits/master
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/custom-components/blueprint.svg?style=for-the-badge
[releases]: https://github.com/custom-components/blueprint/releases
[license-shield]:https://img.shields.io/github/license/scottyphillips/mitsubishi_hass
[buymecoffee]: https://www.buymeacoffee.com/RgKWqyt
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Scott%20Phillips-blue
