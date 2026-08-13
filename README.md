# Daikin MCZ70 Air Purifier for Home Assistant

ダイキン うるるとさらら 空気清浄機（MCZ704A / MCZ70Z 系）を Home Assistant に統合するカスタムコンポーネント。

除湿・加湿・空気清浄のすべてを制御できます。

## 特徴

- **読み取りはローカル API**（`http://<ip>:80`、認証なし、2秒ポーリング）——高速・無料
- **書き込みは Daikin Smart DB クラウド API**——この機種（adp_kind=4）はローカル書き込みがファームウェアで無効化されており、電源・モード変更はクラウド経由のみ
- **トークン自動管理**——アクセストークンは期限前に自動リフレッシュされ、refresh_token は永続化されるため再起動でも再認証不要。401 時は自動で再ログインを試行
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

## セットアップ

1. **設定 → デバイスとサービス → 統合を追加 → Daikin MCZ70**
2. デバイスの IP アドレスを入力（ローカル読み取り用・必須）
3. クラウド認証情報を入力（書き込み用・下記参照）。**Client ID / Client Secret / Redirect URI は自動入力済み**（アプリに埋め込まれた公開定数）——手入力が必要なのは **UUID / Terminal ID / Port / ID / SPW / Refresh Token** の6項目
4. ローカル接続に成功すればセットアップ完了。クラウド認証が失敗していても読み取り専用で動作します（警告表示あり）

クラウド認証情報は後から **統合のオプション** から再入力できます（反映は再起動後）。

## クラウド認証情報の取得方法

書き込み制御には Daikin アプリの通信傍受で取得した認証情報が必要です。**Client ID / Client Secret / Redirect URI はアプリに埋め込まれた公開定数が自動入力されるため、入力不要**です（変更が必要な場合のみ上書き）。

必要な6項目と取得元：

| 項目 | 取得元 |
|------|--------|
| UUID / Terminal ID | アプリをログアウト→再ログインした際の `GET /dsioti/oauth2/authorize` クエリの `uuid` / `client_device_id` |
| Port / ID / SPW | アプリで設定変更（モード切替など）した際の `GET /cleaner/set_control_info` クエリの `port` / `id` / `spw` |
| Refresh Token | ログイン成功時の `POST /dsioti/oauth2/auth` の `Location: daikinsmartapp://callback?code=...` から `code` を取得し、トークン交換 API（`POST https://prod-dsioti.daikinsmartdb.jp/dsioti/oauth2/token`、`grant_type=authorization_code` / `code` / `client_id` / `client_secret` / `code_verifier` / `redirect_uri`）で交換して取得 |

mitmproxy による傍受の基本（PC で `mitmweb` を起動 → スマホの Wi-Fi プロキシを PC の IP:8080 に設定 → `http://mitm.it` から証明書インストール）は [dylannlaw/homebridge-daikin-air-purifier](https://github.com/dylannlaw/homebridge-daikin-air-purifier) の README が参考になります。

⚠️ **Refresh Token の取得は PKCE のため技術的に煩雑です**（`code_verifier` が必要）。取得が難しい場合は作者に問い合わせるのが確実です。

終わったらスマホのプロキシ設定を元に戻すのを忘れずに。

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 読み取りは動くが書き込みが動かない | クラウド認証情報の誤り。統合のオプションから再入力 → HA 再起動 |
| ログに `Cloud login failed` | refresh_token が失効している可能性。再取得して統合のオプションから再入力 → HA 再起動 |
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
