# Mitsubishi ECHONET Climate Component for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]


A Home Assistant custom component for use with ECHONET enabled Mitsubishi
HVAC systems using the MAC-568IF-E WiFi Adaptor.
This custom component makes use of the 'mitsubishi_echonet'
Python library also written by yours truly:
(https://github.com/scottyphillips/mitsubishi_echonet)

**This component will set up the climate platform.**

# Current working systems:
Based upon feedback this custom component works on the following Mitsubishi
HVAC systems all equipped with the MAC-568IF-E WiFi Adaptor:
MSZ-GE42VAD
MSZ-GE24VAD
MSZ-GL50VGD
MSZ-GL35VGD
PEA-RP140GAA

## Installation - Enable ECHONET protocol
This Custom Component makes use of the official Mitsubishi MAC-568IF-E WiFi
Adaptor. Other adaptors (indeed other vendors!) may work, but they
must support the 'ECHONET lite' protocol.

From the official Mitsubishi AU/NZ Wifi App, you will need to enable
the 'ECHONET lite' protocol under the 'edit unit' settings.

![echonet][echonetimg]

## Installation - Home Assistant
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `mitsubishi`.
4. Download _all_ the files from the `custom_components/mitsubishi/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. Add `climate:` to your HA configuration as per the example below.

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/mitsubishi/__init__.py
custom_components/mitsubishi/climate.py
custom_components/mitsubishi/manifest.json
```

## Example configuration.yaml
```yaml
climate:
  - platform: mitsubishi
    ip_address: 1.2.3.4
```

## Configuration options

Key | Type | Required | Description
-- | -- | -- | --
`ip_address` | `string` | `True` | IP Address for the HVAC system.
`name` | `string` | `False` | Friendly name for the HVAC system
`climate` | `list` | `False` | Configuration for the `climate` platform.

### Configuration options for `climate` list

Key | Type | Required | Default | Description
-- | -- | -- | -- | --
`fan_modes` | `list` | `False` | `True` | Fine tune fan settings.

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
