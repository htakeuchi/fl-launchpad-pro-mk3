# FL Studio Launchpad Pro MK3 Midi/DAW Scripts

Launchpad Pro MK3 for FL Studio の実験用連携スクリプトです。

目的は、通常は Launchpad 本体の Note / Chord / Session などの通常モードを使い、Session ボタンで FL Studio 制御モードへ切り替え、もう一度 Session ボタンで通常モードへ戻すことです。

## 現在の挙動

- FL Studio 起動時には Programmer Mode へ入りません。
- `LPProMK3 DAW` 用の補助スクリプトが起動時に DAW Mode をONにし、Sessionボタンを選択可能にします。
- 通常モード中は、Session ボタン以外のMIDIイベントをFLへ素通しします。
- 通常モード中に補助スクリプトがSessionボタン/Sessionレイアウト切り替えを受けると、MIDI側スクリプトへ通知し、Programmer Mode をONにして元スクリプト由来のFL制御/LED更新を開始します。
- FL制御モード中にもう一度 Session ボタンを押すと Programmer Mode をOFFに戻します。
- FL制御モード中に Note / Chord / Custom ボタンを押すと Programmer Mode をOFFにし、それぞれの通常モードへ戻ります。
- Customモード中はFactory Custom ModeのMIDIを処理せずFL Studioへ渡します。Customページ番号も保持し、FL制御モードから戻るときに直前のCustomページへ戻します。
- FL制御モード中はスクリプト側でModeボタン行を明示的に点灯します。Programmer ModeのLED番号差を吸収するため、通常の座標更新に加えて直接RGB SysExでも点灯します。
- 終了時は MIDI側が Programmer Mode OFF、DAW側が DAW Mode OFF を送信します。

## 推奨MIDI設定

| Port | Controller Type | Enabled |
| --- | --- | --- |
| Launchpad Pro MK3 LPProMK3 MIDI | NovationLaunchpadProMK3Midi | On |
| Launchpad Pro MK3 LPProMK3 DAW | NovationLaunchpadProMK3DAW | On |
| Launchpad Pro MK3 LPProMK3 DIN | None / Generic | Off unless DIN is needed |

DAWポートには `NovationLaunchpadProMK3DAW` だけを割り当ててください。MIDI側の `NovationLaunchpadProMK3Midi` をDAWポートへ割り当てないでください。

## インストール

FL Studioを終了してから実行します。

```sh
./scripts/install-to-fl.sh
```

コピー先:

```text
~/Documents/Image-Line/FL Studio/Settings/Hardware/NovationLaunchpadProMK3Midi
~/Documents/Image-Line/FL Studio/Settings/Hardware/NovationLaunchpadProMK3DAW
```

必要なスクリプトフォルダだけを `NovationLaunchpadProMK3Midi` / `NovationLaunchpadProMK3DAW` としてコピーします。

## 実機確認ポイント

DAW補助スクリプトを有効にしてもSessionボタンが薄く点灯しない場合は、FL側が `LPProMK3 DAW` の出力ポートを開けていない可能性があります。MIDI SettingsでDAW入力のController Typeと、同名のDAW出力ポート番号を確認してください。

Programmer Mode中の Session 相当イベントは既存スクリプトの `0x5D` を根拠にしています。通常モード中はDAW補助スクリプト側でSessionレイアウト通知またはSessionボタンイベントを受けて、MIDI側へ `device.dispatch` で通知します。
