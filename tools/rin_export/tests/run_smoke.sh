#!/usr/bin/env bash
# ダミーの RIN を立てて、ログイン →事業所 →利用者一覧 →提供実績記録表 →HTML保存
# までを通しで確認する。本物の RIN には一切接続しない。
set -euo pipefail

cd "$(dirname "$0")/.."
PORT=8799
OUT_DIR="out-smoke"

python3 tests/fake_rin_server.py "$PORT" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2

export RIN_USER=demo
export RIN_PASSWORD=demo-password

rm -rf "$OUT_DIR" state.json
python3 save_support_records.py login --config tests/fixtures/config.fake.json --headless
python3 save_support_records.py run \
  --config tests/fixtures/config.fake.json \
  --headless --months 2026-01..2026-07 --out-dir "$OUT_DIR"

OUT_DIR="$OUT_DIR" python3 - <<'PY'
import os
import pathlib

root = pathlib.Path(os.environ["OUT_DIR"])
files = sorted(root.rglob("提供実績_*.html"))
assert len(files) == 28, f"利用者4名×7か月=28ファイルのはずが {len(files)} でした"

for path in files:
    _, name, year_month = path.stem.split("_")
    year, month = int(year_month[:4]), int(year_month[5:])
    html = path.read_text(encoding="utf-8")
    assert path.parent.name == year_month, f"保存フォルダの年月が違います: {path}"
    assert f"{year}年{month}月" in html, f"別の年月のページが保存されています: {path}"
    assert name in html, f"別の利用者のページが保存されています: {path}"

# 「岩村  伸一」のように氏名に入った連続スペースが保たれていること。
expected = root / "さくら生活介護センター" / "2026-07" / "提供実績_岩村  伸一_2026-07.html"
assert expected.exists(), f"氏名の連続スペースが保持されていません: {expected}"

for office in ("さくら生活介護センター", "みどり就労支援センター"):
    for name in ("利用者一覧.html", "利用者一覧.csv"):
        assert (root / office / name).exists(), f"{office}/{name} がありません"

assert (root / "保存一覧.csv").exists(), "保存一覧.csv がありません"
print("スモークテスト OK: 2事業所・利用者4名・7か月分（28ファイル）を保存できました")
PY

# ★を埋める前でも inspect が画面を保存できること（セレクタを調べるための
# コマンドなので、たどれない段階があっても止まらずに保存して進む）。
rm -rf out-smoke-inspect
python3 save_support_records.py inspect \
  --config tests/fixtures/config.unfilled.json \
  --headless --out-dir out-smoke-inspect

for name in 00_ログイン直後.html 01_事業所一覧.html 02_利用者一覧.html; do
  test -s "out-smoke-inspect/$name" \
    || { echo "inspect が $name を保存できていません" >&2; exit 1; }
done
echo "inspect OK: ★が未設定でも画面を保存できました"

# ★のまま run した場合は、どこを埋めればよいかを示して止まること。
if python3 save_support_records.py run \
     --config tests/fixtures/config.unfilled.json \
     --headless --months 2026-01 --out-dir out-smoke-unfilled 2>out-smoke-inspect/unfilled-run.log; then
  echo "★が未設定なのに run が成功してしまいました" >&2
  exit 1
fi
grep -q "offices.list_url" out-smoke-inspect/unfilled-run.log \
  || { echo "run のエラーに、埋めるべき項目名が出ていません" >&2; cat out-smoke-inspect/unfilled-run.log >&2; exit 1; }
rm -rf out-smoke-unfilled
echo "未設定チェック OK: 埋めるべき項目を示して停止しました"

# 2回目は既存ファイルをスキップして0件保存になること。
python3 save_support_records.py run \
  --config tests/fixtures/config.fake.json \
  --headless --months 2026-01..2026-07 --out-dir "$OUT_DIR" | tail -1 | tee /dev/stderr | grep -q "保存 0件" \
  && echo "レジューム OK: 2回目は既存分をすべてスキップしました"
