# Configuring Services

Preliminary support for advanced service calls has been configured as of version 3.5.3. At the moment the follow devices support Home Assistant services:

## Daikin Hot Water Heater

Daikins Hot Water Heaters can have their hot water heater timers configured using the `echonetlite.set_on_timer_time` service call. This in turn can be used in automation as per the below example to create a corresponding input entity:

Automation example

```
Sensor entity id as: sensor.hot_water_set_value_of_on_timer_time
Input entity id as: input_datetime.hot_water_value_of_on_timer_time

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
