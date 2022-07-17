# ECHONETLite Platform Custom Component for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

ECHONETLite互換機器で使用するためのHomeAssistantカスタムコンポーネント。
このカスタムコンポーネントは「pychonet」Python3ライブラリを利用しています。
また、そのコンポーネントもこの作者によって維持されています。
(https://github.com/scottyphillips/pychonet)

**このコンポーネントは、エアコン・ファン・センサー・選択およびスイッチプラットフォームをセットアップします**

# 現在動作確認されている機器:
フィードバックに基づいて、このカスタムコンポーネントは以下の互換性のあるECHONETLite機器で動作します:

* 三菱電機 MAC-568IF-E WiFi アダプターでコントロールされている以下の機器:
  * GE シリーズ
     * MSZ-GE42VAD
     * MSZ-GE24VAD
     * MSZ-GL71VGD
     * MSZ-GL50VGD
     * MSZ-GL35VGD
     * MSZ-GL25VGD
  * AP シリーズ
     * MSZ-AP22VGD
     * MSZ-AP25VGD
     * MSZ-AP50VGD
  * 換気システム
     * PEA-M100GAA
     * PEA-RP140GAA

* 三菱電機 HM-W002-AC WiFi アダプターでコントロールされている以下の機器:
  * JXV シリーズ
     * MSZ-JXV4018S

* 三菱電機 MAC-578IF2-E WiFi アダプターでコントロールされている以下の機器:
  * AP シリーズ
     * MSZ-AP22VGD
     * MSZ-AP35VGD
     * MSZ-AP50VGD
  * 換気システム
     * PEAD-RP71


* 'MoekadenRoom' ECHONETLite シミュレーター: https://github.com/SonyCSL/MoekadenRoom
     * エアコンオブジェクト
     * 照明オブジェクト
     * 電子錠オブジェクト
     * 温度計オブジェクト

* シャープ
     * エアコン
         * AY-J22H
         * AY-L40P
     * 加湿空気清浄機
         * KI-HS70

* パナソニック
     *  エアコン
         *　CS-221DJ

* コイズミ照明
     * スマートブリッジ AE50264E (https://www.koizumi-lt.co.jp/product/jyutaku/tree/ )

* リンナイ
     * 給湯器 (Wi-Fi機能(ECHONETLite)搭載のリモコン)
         * スイッチエンティティで、運転・ふろ自動・おいだき・タイマー予約をコントロール可能
         * タイマー予約を設定するための入力エンティティは、テンプレートと[サービスコール]((Services.ja.md))を使用して設定できます。

* ダイキン
     * エアコン
          * ECHONET Lite 対応機器

* オムロン
    * 太陽光発電用ゲートウェイ
        * 太陽光発電とグリッド消費を含むホームアシスタントエネルギーダッシュボードの完全サポート。
        * 各種センサーの負荷状態。

上記の他にも[ECHONET Lite規格](https://echonet.jp/product/echonet-lite/)にリストアップされている多くの機器がコントロールできる可能性があります。

## インストール - ECHONETプロトコルを有効にする
このカスタムコンポーネントは、もともと三菱 MAC-568IF-E WiFi アダプター用に設計されました。
ECHONETliteを有効にするための基本ガイドを以下に示します。

公式の Mitsubishi AU/NZ Wifi アプリで「edit unit」設定の「ECHONETlite」プロトコル有効にする必要があります。

※ 日本で発売されている ECHONET Lite 対応のアダプター(HM-W002-AC, HM-W002-ACB など)では設定の必要はないかも知れません。

![echonet][echonetimg]

他の多くの製品はこのカスタムコンポーネントを使用して動作しますが、「ECHONETlite」プロトコルを正しくサポートしている必要があります。 作者は、他のベンダー製品で ECHONET Lite を有効にすることを支援することはできません。

## インストール

### HACS利用
1. 統合でECHONETLiteを検索します
2. [インストール]をクリックします

### ダウンロードして配置
1. 選択したツールを使用して、HA構成（ `configuration.yaml`がある場所）のディレクトリ（フォルダー）を開きます。
2. そこに`custom_components`ディレクトリ（フォルダ）がない場合は、それを作成する必要があります。
3.  `custom_components`ディレクトリ（フォルダ）に`echonetlite`という新しいフォルダを作成します。
4. このリポジトリの`custom_components/echonetlite/`ディレクトリ（フォルダ）から_すべての_ファイルをダウンロードします。
5. ダウンロードしたファイルを作成した新しいディレクトリ（フォルダ）に配置します。

## コンポーネントの有効化
1.  ホームアシスタントを再起動し、ブラウザのキャッシュをクリアします
2. 「構成」->「統合」->「統合の追加」に移動します。
3. 「echonetlite」統合を選択します。 ホストフィールドにIPアドレスを入力し、プラットフォームに名前を付けます。
4. プラットフォームは、サポートされているプラットフォームを自動的に構成します。 気候、センサー、スイッチ、ファン、選択。
5. 構成する追加のデバイスがある場合は、手順2を繰り返します。

## サポートされているエアコンおよび空気清浄機の風量および風向スイングモード設定のオプションの構成
統合を追加したら、構成->統合に戻ることができます。
ECHONETLiteデバイスの下で[構成]をクリックします。
必要な風量と風向スイングモードの設定を微調整します。 設定では、統合によりあなたのシステムでサポートされている機能を判別できます。
注：ECHONETLiteはこれらの設定に対して許可された値を返す手段を提供しないため、適切な特定のオプションを選択することは「試行錯誤」のプロセスです。

オプションを構成して保存するとすぐに、設定が有効になります。


## 栄誉殿堂
スイッチエンティティを作成し、カスタムサービスコールフレームワークを作成してくれた Naoki Sawada (nao-pon) に感謝します。

コードベースとドキュメントの全体的な質の向上してくれた JasonNader に感謝します。

古いコードのリファクタリングとテストを手伝ってくれた khcnz (Karl Chaffey) と gvs に感謝します。

Dick Swart、Masaki Tagawa、Paul、khcnz、Kolodnerd、およびAlfie Gernerに、元の "mitsubishi_hass" へのコード更新とこのカスタムコンポーネントへの適用に貢献してくれたことに感謝します。

ホームアシスタント用に独自のネイティブ Python ECHONET ライブラリを作成するように促してくれた JeffroCarr に感謝します。
彼自身のリポジトリのいくつかのアイデアは、私自身のコードに実装されました。
(https://github.com/jethrocarr/echonetlite-hvac-mqtt-service.git)

"pychonet"ライブラリの基礎を形成した Node JS の高品質で十分に文書化された ECHONET Lite ライブラリをオープンソーシングしてくれた Futomi Hatano に感謝します。
(https://github.com/futomi/node-echonet-lite)


## ライセンス

このアプリケーションはMITライセンスの下でライセンスされています。詳細については、ライセンスを参照してください。

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
