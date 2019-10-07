[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

_Component to integrate with [mitsubishi_echonet][mitsubishi_echonet]._

**This component will set up the following platforms.**

Platform | Description
-- | --
`climate` | Interface to Mitsubishi ECHONET API.

![example][exampleimg]

{% if not installed %}
## Installation

1. Click install.
1. Add `mitsubishi:` to your HA configuration.

{% endif %}

## Example configuration.yaml
Add to configuration.yaml:

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

### Fine tuning fan settings.
Optionally, you can also specify what fan settings work with your specific
HVAC system. If no fan speeds are configured, the system will default to 'low'
and 'medium-high'.

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

***
[mitsubishi_echonet]: https://github.com/scottyphillips/mitsubishi_echonet
[mitsubishi_hass]: https://github.com/scottyphillips/mitsubishi_hass
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/scottyphillips/mitsubishi_hass.svg?style=for-the-badge
[releases]: https://github.com/scottyphillips/mitsubishi_hass/releases
[license-shield]:https://img.shields.io/github/license/scottyphillips/mitsubishi_hass?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/RgKWqyt?style=for-the-badge
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/Maintainer-Scott%20Phillips-blue?style=for-the-badge
[exampleimg]: Mitsubishi.jpg
