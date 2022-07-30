# Configuring Services

Preliminary support for advanced service calls has been configured as of version 3.5.3. At the moment the follow devices support Home Assistant services:

## Hot Water Heater System

ECHONET Lite compatible Hot Water Heaters can have their hot water heater timers configured using the `echonetlite.set_on_timer_time` service call. This in turn can be used in automation as per the below example to create a corresponding input entity:

### Automation example

- Sensor entity id as: `sensor.hot_water_set_value_of_on_timer_time`
- Input entity id as: `input_datetime.hot_water_value_of_on_timer_time`

```yaml
alias: Relay Hot Water On Timer time
description: ''
trigger:
  - platform: state
    entity_id:
      - input_datetime.hot_water_value_of_on_timer_time
    for:
      hours: 0
      minutes: 0
      seconds: 5
    id: set
  - platform: state
    entity_id:
      - sensor.hot_water_set_value_of_on_timer_time
    id: get
condition:
  - condition: template
    value_template: >-
      {{strptime(states('input_datetime.hot_water_value_of_on_timer_time'), '%H:%M:%S') !=
      strptime(states('sensor.hot_water_set_value_of_on_timer_time')+':00',
      '%H:%M:%S')}}
action:
  - if:
      - condition: trigger
        id: set
    then:
      - service: echonetlite.set_on_timer_time
        entity_id: sensor.hot_water_set_value_of_on_timer_time
        data_template:
          timer_time: '{{ states(''input_datetime.hot_water_value_of_on_timer_time'') }}'
    else:
      - service: input_datetime.set_datetime
        entity_id: input_datetime.hot_water_value_of_on_timer_time
        data_template:
          time: '{{ states(''sensor.hot_water_set_value_of_on_timer_time'') }}'
mode: single
```
## Single-byte integer value setting services

We can create a numeric setting entity with the following automation with the number input helper.

Of course, it can also be used for various automations.

With future expansion, parameters that can be set numerically on other devices can be added, so I think it can be used conveniently. (Thanks @nao-pon)

  - Sensor entity id as: `sensor.set_value_of_hot_water_temperature`
  - Input entity id as: `input_number.set_value_of_hot_water_temperature`

### Automation example

```yaml
alias: Relay Set Value Of Hot Water Temperature
description: ''
trigger:
  - platform: state
    entity_id:
      - input_number.set_value_of_hot_water_temperature
    for:
      hours: 0
      minutes: 0
      seconds: 2
    id: set
  - platform: state
    entity_id:
      - sensor.set_value_of_hot_water_temperature
    id: get
condition:
  - condition: template
    value_template: >-
      {{int(states('input_number.set_value_of_hot_water_temperature'), 0) !=
      int(states('sensor.set_value_of_hot_water_temperature'), 0)}}
action:
  - if:
      - condition: trigger
        id: set
    then:
      - service: echonetlite.set_value_int_1b
        entity_id: sensor.set_value_of_hot_water_temperature
        data_template:
          value: '{{ states(''input_number.set_value_of_hot_water_temperature'') }}'
    else:
      - service: input_number.set_value
        entity_id: input_number.set_value_of_hot_water_temperature
        data_template:
          value: '{{ states(''sensor.set_value_of_hot_water_temperature'') }}'
mode: queued
max: 2
```
