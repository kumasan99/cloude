# data/inbox — 資料の置き場

ここにファイルを置くと、クロ（COO）が読み取ってレポートを作ります。

```
inbox/finance/    財務・資金繰り
inbox/sales/      売上・案件
inbox/people/     人・組織
inbox/ops/        業務・現場
inbox/strategy/   戦略・計画
```

- 何を置けばいいかは `docs/DATA_INTAKE.md` を参照してください。
- ファイル名は自由です。日付が入っていると期間を正しく認識できます。
- **この配下のファイルはGitにコミットされません**（`.gitignore` 済み）。
- 古くなった資料は `data/archive/` に移すと、レポート生成の対象から外れます。
