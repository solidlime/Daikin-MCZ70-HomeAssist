# Daikin MCZ70 Air Purifier for Home Assistant

ダイキン うるるとさらら 空気清浄機（MCZ704A / MCZ70Z 系）を Home Assistant に統合するカスタムコンポーネント。

除湿・加湿・空気清浄のすべてを制御できます。

## 特徴

- **読み取りはローカル API**（`http://<ip>:80`、認証なし、2秒ポーリング）——高速・無料
- **書き込みは Daikin Smart DB クラウド API**——この機種（adp_kind=4）はローカル書き込みがファームウェアで無効化されており、電源・モード変更はクラウド経由のみ
- **トークン自動管理**——アクセストークンは期限前に自動リフレッシュされ、refresh_token は永続化されるため再起動でも再認証不要。401 時は自動でトークンをリフレッシュ
- クラウド書き込みは 30 秒に 1 回にレート制限（連続操作しても安全）

## 対応機種

| 機種 | 状態 |
|------|------|
| MCZ704A-T | ✅ 実機確認済み |
| MCZ70Z / ACZ70Z 系 | 🔶 同一機能の兄弟機（動作見込み） |
| MCK70X / MCK55X 系 | ❌ こちらは [hgn32/daikin-aircleaner](https://github.com/hgn32/daikin-aircleaner) を推奨（ローカル書き込みが可能な旧世代） |

## エンティティ

| 種別 | 内容 |
|------|------|
| ファン | 電源 + プリセット（自動 / 手動 / おまかせ / 節電 / 花粉 / のどはだ / サーキュ） |
| セレクト | 風量（弱 / 標準 / 高 / 最高）、湿度モード（オフ / 低め / 標準 / 高め / 自動 / **除湿**）、LED表示（点灯 / 暗め / 消灯） |
| センサー | 室温 / 室内湿度 / PM2.5 / ほこり / におい |
| バイナリセンサー | 給水が必要 / 加湿タンク未装着 / 除湿タンク満水（要排水） |

## インストール

### HACS（推奨）

1. HACS → 3つのドット → **Custom repositories**
2. リポジトリ: `https://github.com/<あなたのアカウント>/Daikin-MCZ70-HomeAssist`、カテゴリ: **Integration**
3. 統合を追加 → 検索で **Daikin MCZ70** を探してインストール
4. Home Assistant を再起動

### 手動

`custom_components/daikin_mcz70/` ディレクトリごと HA の `custom_components/` にコピーして再起動。

## セットアップ（3ステップ）

### ステップ 1: クラウド認証情報の取得（書き込み制御に必要。読み取りのみなら省略可）

付属スクリプトが Daikin の OAuth2 フローを直接実行し、設定に必要な **Refresh Token** を出力します（スマホやプロキシ傍受は不要）。

```
$env:DAIKIN_USER="you@example.com"; $env:DAIKIN_PW="your-password"; python scripts/get_credentials.py --ip <実機IP>
```

- `DAIKIN_USER` / `DAIKIN_PW` は Daikin Smart DB アカウントのメールアドレスとパスワード（必須）
- `--ip` は任意。指定するとデバイスの LAN エンドポイントから `id` / `spw` / `port` も取得して表示します（指定しなくてもセットアップ時に自動補完されます）
- 認証情報はファイルに保存されません（stdout に表示されるのみ）
- bash の場合: `DAIKIN_USER=... DAIKIN_PW=... python3 scripts/get_credentials.py`

### ステップ 2: 統合を追加

1. **設定 → デバイスとサービス → 統合を追加 → Daikin MCZ70**
2. **IP アドレスのみ入力** → ローカル接続テスト成功で完了

Client ID / Client Secret / Redirect URI / UUID は自動入力済み（アプリに埋め込まれた公開定数）、ID / SPW / Port は `basic_info` から自動補完、Terminal ID は**空欄で OK** です。

### ステップ 3: Refresh Token を設定

統合の **オプション** を開き、ステップ 1 で取得した Refresh Token を貼り付けて保存 → Home Assistant を再起動。書き込み（電源・風量・湿度モード・LED）が有効になります。

読み取り専用で使う場合はステップ 1・3 は不要です（クラウド認証なしでもローカル読み取りは動作します）。

## 免責事項

- 非公式の自作コンポーネントです。ダイキン工業株式会社とは無関係です。
- クラウド API は公式に公開されたものではなく、予告なく仕様変更・廃止される可能性があります。自己責任でご使用ください。
- ご利用前にダイキンの利用規約をご確認ください。
- クラウド書き込みは 30 秒に 1 回にレート制限されています（連続操作してもデバイスとサーバーに負荷をかけません）。
- refresh_token 等の認証情報は Home Assistant の設定にローカル保存されます。外部へ送信されるのはダイキンの公式サーバーへの書き込みリクエストのみです。

## 上級者向け: アプリ通信傍受による認証情報取得（従来方式）

スクリプトが使えない環境向けに、Daikin アプリの通信傍受で認証情報を取得する方法も残しています。**Client ID / Client Secret / Redirect URI / UUID はアプリに埋め込まれた公開定数が自動入力されるため、入力不要**です（変更が必要な場合のみ上書き）。

必要な項目と取得元：

| 項目 | 取得元 |
|------|--------|
| UUID / Terminal ID | アプリをログアウト→再ログインした際の `GET /dsioti/oauth2/authorize` クエリの `uuid` / `client_device_id`（UUID はサーバーで検証されないため任意、Terminal ID は空欄で可） |
| Port / ID / SPW | アプリで設定変更（モード切替など）した際の `GET /cleaner/set_control_info` クエリの `port` / `id` / `spw`（セットアップ時に `basic_info` から自動補完されます） |
| Refresh Token | ログイン成功時の `POST /dsioti/oauth2/auth` の `Location: daikinsmartapp://callback?code=...` から `code` を取得し、トークン交換 API（`POST https://prod-dsioti.daikinsmartdb.jp/dsioti/oauth2/token`、`grant_type=authorization_code` / `code` / `client_id` / `client_secret` / `code_verifier` / `redirect_uri`）で交換して取得 |

mitmproxy による傍受の基本（PC で `mitmweb` を起動 → スマホの Wi-Fi プロキシを PC の IP:8080 に設定 → `http://mitm.it` から証明書インストール）は [dylannlaw/homebridge-daikin-air-purifier](https://github.com/dylannlaw/homebridge-daikin-air-purifier) の README が参考になります。

終わったらスマホのプロキシ設定を元に戻すのを忘れずに。

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 読み取りは動くが書き込みが動かない | クラウド認証情報の誤り。統合のオプションから再入力 → HA 再起動 |
| ログに `cloud token refresh failed` | refresh_token が失効している可能性。`scripts/get_credentials.py` で再取得して統合のオプションから再入力 → HA 再起動 |
| 書き込みが遅い | クラウド書き込みの 30 秒レート制限による正常動作 |
| LED セレクトが動かない | `set_device_setting` のクラウドエンドポイントは実機未検証。アプリの通信傍受で `led_dsp` 送信時のクエリを確認してください |

## 技術メモ

- ローカル読み取りエンドポイント: `/common/basic_info`, `/cleaner/get_control_info`, `get_unit_status`, `get_sensor_info`, `get_device_setting`
- MCZ70 固有: 除湿は `humd=5`（`mode` とは独立）、加湿は `humd=1-3`、`acOpeMode` / `airdir` / `swing` は読み取りのみ
- クラウド API: トークン交換・リフレッシュは `POST https://prod-dsioti.daikinsmartdb.jp/dsioti/oauth2/token`（リフレッシュは旧 `https://api.daikinsmartdb.jp/premise/dsiot/token` でも動作確認済み）、書き込みは `https://api.daikinsmartdb.jp/cleaner/set_control_info` を GET + Bearer 認証（`id` / `spw` / `terminalid` / `port` 付き）

## 既知の制限（実機検証結果）

- **空気質センサー（PM2.5 / ほこり / におい）**: この機種のファームウェア（ver 3.8.0）では、ローカル API の現在値が**常に 0** を返します。デバイス側の日次/週次履歴（`get_day_snsr_count` / `get_week_snsr_count`）には実値が記録されており、Daikin アプリはクラウド経由で現在値を表示しています（センサー自体は正常）。クラウド認証導入後にクラウド側の `get_sensor_info` を試す価値があります。
- **タンクフラグ**（実機検証済み）: 加湿タンク・除湿タンクのフラグは両方とも **1 = 正常（装着・空） / 0 = 警告（未装着・満水）** です。加湿タンクが「空」の時に 0 になるかは未検証（加湿シーズンに確認予定）。
- **給水警告（water_supply）**: この機種での動作は未検証（加湿運転中にタンクが空になった時の挙動は未確認）。

## クレジット

- ベース実装: [hgn32/daikin-aircleaner](https://github.com/hgn32/daikin-aircleaner) (MIT)
- クラウド API 実装の参考: [dylannlaw/homebridge-daikin-air-purifier](https://github.com/dylannlaw/homebridge-daikin-air-purifier)

## 免責事項

非公式の自作コンポーネントです。ダイキン工業株式会社とは無関係です。
