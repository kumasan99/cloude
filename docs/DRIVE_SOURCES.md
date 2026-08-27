# Drive連携 — クロが読む場所と、絶対に読まない場所

ReSowグループの資料は Google Drive の `00.ReSow参謀AI` に集約されています。
クロはローカルの `data/inbox/` ではなく、この Drive を直接読みます。
入口は **`ReSow_00_MAP_v2`**（全フォルダIDの台帳）です。

## 読む場所

| Drive上の場所 | フォルダID | 何に使うか |
|---|---|---|
| `01_data/master` | `184QYV6WNP4Vw6Sl7fqSo62u0h8TYfWIT` | 決算統合、法人事業所マスタ、資本関係図 |
| `01_data/finance` | `1cbdMSrWgU6LZbA2BMN0obal-LDGtn25a` | 資金繰り表、借入一覧 |
| `01_data/finance/決算書` | `1bVR3TbjxwHxb6STGiFSuIPzLK-dYPfvd` | 決算書原本（7法人）＋インデックス |
| `01_data/operations` | `1IZ1uYu27t_0tiQpNuapO5sxdlYLlnZx9` | 月次売上、売上計画、事業所レポート |
| `01_data/hr/00_人事マスタ` | `1nBeJakDndaz8Q23cQJGuVFk9mcIN3H4i` | 従業員名簿、組織図 |
| `01_data/compliance` | `1fTeMaWwBCI7PQaUPr60qGGxAKFqpZs70` | 運営指導・行政報告・苦情 |
| `01_data/market` | `1Z9rSpN4Pj1YXOPmkMdaLXa8v39ucMpUT` | TDB、ベンチマーク、制度改定 |
| `02_docs/議事録` | `14LMcjX8Ti3b5k1UBBMTzIP2oKhCsOwti` | 経営会議・アクション管理 |
| `10_projects/*` | `1xd6lAr2JHRKLO-AOsz94wqR8T2yo1-hm` | 進行中プロジェクトの状況 |

## 読まない場所（社長の指定）

MAPに記載されている除外指定を、そのままクロの動作ルールにしています。
`config/company.yaml` の `reporting.excluded_sources` にフォルダIDで固定してあります。

| 場所 | フォルダID | 理由 |
|---|---|---|
| `01_data/hr/30_健康情報` | `1Jhq0dgJFrD3JKZ8IXYdiVRIztCaZuqyq` | 要配慮個人情報 |
| `01_data/private` | `1IbOzditKSK15HAgM-fQg5KP0EyYcvgor` | 個人資産・非共有 |
| `支援記録PJ` | `1BlY7zkzYBBzJA6CadDZkLYLkfwHpTvCu` | 利用者の支援記録・要配慮個人情報 |

## 制限つきで扱う場所

| 場所 | フォルダID | ルール |
|---|---|---|
| `01_data/hr/20_給与` | `1kli-XUe2z3gJ_DkJu-kfH4izBPdyR4Wm` | **個人別データは参照しない。** 法人別・月別の集計値（人数・給与総額・法定福利費）のみ扱う |

除外・制限の変更は、`config/company.yaml` を編集してください。
クロは毎回このファイルを読んでから資料にあたります。

## MAPと実体のズレ（2026-08-22時点）

- `ReSow_決算統合_v11.xlsx` は MAP では `01_data/finance` と記載されていますが、**実体は `01_data/master`** にあります。
- `02_docs/議事録` は**中身が空**です。

## 資料を追加するとき

MAPに行を追加すれば、クロはそれを読みます。
新しいフォルダを作った場合は、MAPへの追記を忘れないでください。
MAPに無いフォルダは、クロからは存在しないのと同じです。
