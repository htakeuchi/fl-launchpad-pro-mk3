# FL Studio Launchpad Pro MK3 Hybrid Script

Launchpad Pro MK3 for FL Studio の実験用ハイブリッドスクリプトです。

目的は、通常は Launchpad 本体の Note / Chord / Session などの通常モードを使い、Session ボタンで FL Studio 制御モードへ切り替え、もう一度 Session ボタンで通常モードへ戻すことです。

## 現在の挙動

- FL Studio 起動時には Programmer Mode へ入りません。
- 通常モード中は、Session ボタン以外のMIDIイベントをFLへ素通しします。
- Session ボタンの `0x5D` イベントを受けると Programmer Mode をONにし、元スクリプト由来のFL制御/LED更新を開始します。
- FL制御モード中にもう一度 Session ボタンを押すと Programmer Mode をOFFに戻します。
- 終了時も Programmer Mode OFF を送信します。

## 推奨MIDI設定

| Port | Controller Type | Enabled |
| --- | --- | --- |
| Launchpad Pro MK3 LPProMK3 MIDI | Novation Launchpad Pro MK3 Hybrid | On |
| Launchpad Pro MK3 LPProMK3 DAW | Generic Controller | On, or Off if unstable |
| Launchpad Pro MK3 LPProMK3 DIN | None / Generic | Off unless DIN is needed |

DAWポートにこのHybridスクリプトを割り当てないでください。このスクリプトは `LPProMK3 MIDI` 用です。

## インストール

FL Studioを終了してから実行します。

```sh
./scripts/install-to-fl.sh
```

コピー先:

```text
~/Documents/Image-Line/FL Studio/Settings/Hardware/Novation Launchpad Pro MK3 Hybrid
```

## 実機確認ポイント

通常モード中に Session ボタンが `LPProMK3 MIDI` ポートへ出ない場合、このスクリプト単体では通常モードからFL制御モードへ入れません。その場合は、`LPProMK3 DAW` 側でSession押下だけを受ける補助スクリプトを追加する必要があります。

この点は仕様上の不確定要素です。Programmer Mode中の Session 相当イベントは既存スクリプトの `0x5D` を根拠にしていますが、通常モード中の送信先ポートは実機で確認してください。

