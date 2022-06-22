# サービスの構成

バージョン 3.5.3 以降、予備的なサポートとして高度なサービス呼び出しが構成されています。 現在、次のデバイスがホームアシスタントサービスをサポートしています。

## ECHONET Lite 対応給湯器 (リンナイ給湯器で動作確認済)

ECHONET Lite 対応給湯器は、`echonetlite.set_on_timer_time`サービスコールを使用して自動湯はりタイマーを設定できます。 これは、以下の例のように自動化で使用して、対応する入力エンティティを作成できます。

自動化のサンプル

- センサーエンティティID: sensor.hot_water_set_value_of_on_timer_time
- 時刻入力エンティティID: input_datetime.hot_water_value_of_on_timer_time

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
