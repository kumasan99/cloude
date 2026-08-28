# AI参謀 / 経営ダッシュボード

中小企業の経営者（CEO）向けの、2つの画面を持つアプリケーションです。

| 画面 | URL | 役割 |
|---|---|---|
| **経営ダッシュボード** | `/dashboard` | クロ（COO）がCEOに報告する画面。KPI・要判断事項・改善提案・リスク・不足資料 |
| AI参謀チャット | `/` | その場で相談するための対話画面（経営相談 / 財務 / 事業計画） |

---

## 何をするものか

社内に散らばった資料（試算表・案件一覧・議事録など）を `data/inbox/` に置くと、
**クロ**（COOとして振る舞うClaude）がそれを読み、CEOが**読むだけで意思決定できる**形に整理して報告します。

ダッシュボードに出るのは次の5つです。

1. **総合サマリー** — 一言で今の状態（順調 / 要注意 / 危険）と、その根拠
2. **あなたの判断が必要なもの** — CEOにしか決められないことだけ。選択肢とクロの推奨つき。その場で承認/却下/保留を記録
3. **KPI** — 出典ファイル名つき。クロが補完した値は「推定」と明記
4. **改善提案** — 課題・打ち手・期待効果・工数、そして「明日からの最初の一歩」
5. **クロが待っている資料** — 何が足りなくて、どの判断ができていないか

5番が重要です。**ダッシュボード自体が「次に何を出せばいいか」を教えてくれる**ので、
最初から資料を全部揃える必要はありません。

---

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env      # ANTHROPIC_API_KEY を設定
uvicorn main:app --reload
```

- ダッシュボード: http://localhost:8000/dashboard
- チャット: http://localhost:8000/

資料が1つも無い状態では**サンプルレポート**が表示されます。
実際の報告がどういう粒度で出てくるかは、それを見てください。

---

## 使い方（最短ルート）

1. `config/company.yaml` に会社の前提とCEOの関心事を書く（5分）
2. `data/inbox/finance/` に月次試算表を1本置く
3. ダッシュボードで「レポートを更新」を押す
4. 「クロが待っている資料」に出てきたものを次に置く

以降は `docs/OPERATIONS.md` の週次サイクルを回してください。

---

## ドキュメント

| ファイル | 内容 |
|---|---|
| [`docs/DATA_INTAKE.md`](docs/DATA_INTAKE.md) | **どの資料を、どこに、どの形式で置くか**（優先度A/B/C付き） |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | 週次・月次の運用サイクル、設定ファイルの使い分け、詰まったときの対処 |

---

## 構成

```
main.py                        FastAPI（チャット + ダッシュボードAPI）
coo/
├── config.py                  パスと設定ファイルの読み込み
├── intake.py                  data/inbox のスキャンとテキスト抽出（xlsx/pdf/csv対応）
├── schema.py                  レポートの構造定義（JSON Schemaで出力を固定）
├── analyst.py                 クロのシステムプロンプトとレポート生成
└── store.py                   レポートと決裁ログの保存・読み出し
config/
├── company.yaml               会社の前提・CEOの関心事・決裁範囲
├── kpi.yaml                   見たいKPIと目標値
└── data_requirements.yaml     必要資料のチェックリスト
data/inbox/                    ← CEOが資料を置く場所（Git管理外）
reports/                       生成されたレポートと決裁ログ（Git管理外）
static/dashboard.*             ダッシュボードの画面
```

## API

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/api/dashboard/latest` | 最新レポート（無ければサンプル） |
| GET | `/api/dashboard/reports` | レポート一覧 |
| GET | `/api/dashboard/reports/{id}` | 指定レポート |
| POST | `/api/dashboard/generate` | inbox の資料を読んでレポート生成（`{"focus": "..."}` で観点を指定可） |
| GET | `/api/dashboard/inbox` | 受領済み資料と、未提供のチェックリスト |
| POST | `/api/dashboard/decisions/{id}` | 決裁を記録（`{"report_id","status","note"}`） |
| GET | `/api/dashboard/decisions` | 決裁履歴 |

## セキュリティ上の注意

- `data/inbox/` の資料と生成レポートは `.gitignore` 済みで、コミットされません。
- 資料の内容はレポート生成時に Claude API に送信されます。社外に出せない資料は置かないでください。
- 認証機構はありません。社外に公開せず、ローカルまたは社内ネットワークで運用してください。
