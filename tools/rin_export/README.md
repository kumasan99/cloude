# RIN 提供実績記録表（支援記録）の一括保存

RIN には外部 API が無いため、Playwright でブラウザを実際に操作して
次の順に画面をたどり、提供実績記録表のページを HTML で保存します。

```
ログイン → 事業所を選ぶ → 利用者一覧 → 利用者を選ぶ
        → 提供実績タブ → 提供実績記録表（年月を切替）→ HTML 保存
```

## 保存されるかたち

```
out/
  さくら生活介護センター/
    利用者一覧.html
    利用者一覧.csv
    2026-01/
      提供実績_岩村  伸一_2026-01.html
      提供実績_山田 太郎_2026-01.html
    2026-02/
      ...
  みどり就労支援センター/
    ...
  保存一覧.csv        ← いつ何を保存したかの記録
```

利用者名は RIN に登録されている表記をそのまま使います
（「岩村  伸一」のように間にスペースが2つ入っている場合もそのまま）。

## セットアップ

```bash
cd tools/rin_export

python3 -m venv .venv
source .venv/bin/activate          # Windows は .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env               # RIN_USER / RIN_PASSWORD を記入
cp config.example.json config.json
```

`.env` `config.json` `state.json` `out/` は Git 管理外です
（ログイン情報・社内URL・個人情報をコミットしないため）。

## 手順

### 1. 画面構造を調べて config.json を埋める

`config.example.json` の★印は、RIN の実際の画面を見ないと決められません。
まず `login.url` と各一覧のURLだけ埋めて、次を実行します。

```bash
python save_support_records.py login      # ブラウザが開くのでログイン
python save_support_records.py inspect    # 各画面のHTMLを保存
```

`out/inspect/` に次の3つが保存されるので、これを見ながら★印を埋めてください。

- `01_事業所一覧.html`
- `02_利用者一覧.html`
- `03_提供実績記録表.html` / `.png`

### 2. 少人数で試運転する

いきなり全員分を流さず、1名・1か月で動作を確かめます。

```bash
python save_support_records.py run --months 2026-07 --limit-users 1
```

### 3. 本番実行（2026年1月〜7月）

```bash
python save_support_records.py run --months 2026-01..2026-07
```

途中で止まっても、もう一度同じコマンドを実行すれば
**保存済みのファイルはスキップして続きから**再開します。
取り直したいときは `--overwrite` を付けてください。

## よく使うオプション

| オプション | 説明 |
| --- | --- |
| `--months 2026-01..2026-07` | 対象年月。`2026-01,2026-04` のように個別指定も可 |
| `--offices さくら生活介護センター` | 事業所を絞る（省略時は全事業所） |
| `--limit-users 1` | 各事業所の先頭N名だけ処理する（試運転用） |
| `--overwrite` | 保存済みファイルも取り直す |
| `--headless` | ブラウザを表示せずに実行する |
| `--slow-mo 300` | 操作をゆっくりにする（動きを目で追いたいとき） |
| `--manual` | 2要素認証などで手動ログインする |

## 2要素認証がある場合

一度だけ手でログインし、そのセッションを保存して使い回します。

```bash
python save_support_records.py login --manual
python save_support_records.py run --months 2026-01..2026-07
```

セッションが切れたら `login --manual` をやり直してください。

## config.json の要点

| 項目 | 説明 |
| --- | --- |
| `offices.mode` | `links`（一覧から自動取得）または `fixed`（下記のように手書き） |
| `users.row_selector` | 利用者1名分の行 |
| `users.pagination.mode` | `none` / `next_button` |
| `record.mode` | `url`（URLに利用者ID・年月を渡せる場合）または `ui`（画面をクリック） |
| `output.wait_ms` | 1件ごとの待ち時間。RIN に負荷をかけないための間隔 |

事業所を手書きする場合：

```json
"offices": {
  "mode": "fixed",
  "list": [
    { "name": "さくら生活介護センター", "id": "1" },
    { "name": "みどり就労支援センター", "id": "2" }
  ]
}
```

## 動作確認

RIN 本体に接続せず、同じ画面遷移を持つダミーサイトで通しの動作を確認できます。

```bash
./tests/run_smoke.sh
```

2事業所・利用者4名・7か月分（28ファイル）が正しい利用者・年月で保存されること、
2回目の実行で既存分がスキップされることまで検証します。

## 注意

- 提供実績記録表には利用者の氏名・支援内容などの個人情報が含まれます。
  出力先フォルダの保管場所と共有範囲には十分ご注意ください。
- 画面操作による取得なので、`output.wait_ms` を短くしすぎると RIN に負荷が
  かかります。既定の 800ms から極端に下げないでください。
- 自動取得が RIN の利用規約・社内規程に反しないか、事前にご確認ください。
