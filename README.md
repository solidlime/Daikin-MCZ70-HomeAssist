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
| バイナリセンサー | 給水が必要 / 加湿タンク満水 / 除湿タンク満水 |

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
3. クラウド認証情報を入力（書き込み用・下記参照）
4. ローカル接続に成功すればセットアップ完了。クラウドログインが失敗していても読み取り専用で動作します（警告表示あり）

クラウド認証情報は後から **統合のオプション** から再入力できます（反映は再起動後）。

## クラウド認証情報の取得方法（プロキシ傍受）

Daikin アプリの通信を傍受して取得します。**約10分の作業**です。

### 準備（PC）

```
pip install mitmproxy
mitmweb        # Web UI が http://127.0.0.1:8081 で開く
ipconfig       # 自分の PC の IP を確認
```

### スマホ

1. Wi-Fi 設定 → プロキシ → 手動 → ホスト: PC の IP / ポート: `8080`
2. ブラウザで `http://mitm.it` → Android/iOS 用証明書をインストール

### キャプチャ

1. **Daikin Smart APP をログアウト → 再ログイン**
2. mitmweb で **`POST /premise/dsiot/login`** のリクエストボディを確認：
   `code`, `clientId`, `uuid`, `clientSecret` → **config flow の `code` / `client_id` / `uuid` / `client_secret` に入力**
3. アプリで適当な設定変更（モード切替など）→ **`GET /cleaner/set_control_info`** のクエリパラメータを確認：
   `terminalid`, `port`, `id`, `spw` → **config flow の `terminal_id` / `port` / `id` / `spw` に入力**
4. 終わったらプロキシ設定を元に戻すのを忘れずに

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 読み取りは動くが書き込みが動かない | クラウド認証情報の誤り。統合のオプションから再入力 → HA 再起動 |
| ログに `Cloud login failed` | `code` がワンタイムの可能性。もう一度傍受し直して `code` を更新 |
| 書き込みが遅い | クラウド書き込みの 30 秒レート制限による正常動作 |
| LED セレクトが動かない | `set_device_setting` のクラウドエンドポイントは実機未検証。アプリの通信傍受で `led_dsp` 送信時のクエリを確認してください |

## 技術メモ

- ローカル読み取りエンドポイント: `/common/basic_info`, `/cleaner/get_control_info`, `get_unit_status`, `get_sensor_info`, `get_device_setting`
- MCZ70 固有: 除湿は `humd=5`（`mode` とは独立）、加湿は `humd=1-3`、`acOpeMode` / `airdir` / `swing` は読み取りのみ
- クラウド API: `https://api.daikinsmartdb.jp`（`/premise/dsiot/login` → トークン発行 → `/cleaner/set_control_info` を GET + Bearer 認証）

## クレジット

- ベース実装: [hgn32/daikin-aircleaner](https://github.com/hgn32/daikin-aircleaner) (MIT)
- クラウド API 実装の参考: [dylannlaw/homebridge-daikin-air-purifier](https://github.com/dylannlaw/homebridge-daikin-air-purifier)

## 免責事項

非公式の自作コンポーネントです。ダイキン工業株式会社とは無関係です。
