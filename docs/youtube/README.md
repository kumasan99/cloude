# YouTube チャンネル分析（@bhellowonder4846）

広報部「メガホ」による分析成果物の置き場。

- `2026-08-28_現状分析と対策案.md` — 初回ミッション成果物（Google Drive「00_連絡板/メガホ」にも同内容を格納）
- `analyze.py` — YouTube Analytics エクスポートCSV（表データ/グラフデータ/合計）を集計するスクリプト

## 使い方

```
pip install pandas
# CSVを展開したディレクトリを L / Y に指定して実行
python3 analyze.py
```

分析に使ったデータは YouTube Studio → アナリティクス → 詳細モード → エクスポート で得られる
`表データ.csv` / `グラフデータ.csv` / `合計.csv` の3点セット（累計・直近365日の2期間）。
CSV自体は社内データのためリポジトリには含めない。
