#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lw_parallel_check.py — 並走テスト（経路b）用の集計・突き合わせ（件数だけを出す）

  python3 lw_parallel_check.py --month 2026-08 --raw-dir <lw_raw_YYYY-MM_part*.csv の場所> \
      --keywords <lw_keywords.csv> --summary <初代の lw_summary_YYYY-MM.csv> --out <出力先>

初代（Cowork・Mac）の lw_export.py / lw_monthly.py と同じ規則で
  ・SHA1（日時+送信者+チャンネルID+本文）で行の重複を落とす
  ・除外語つきキーワード判定（1発言はカテゴリごとに1件）
  ・前後2行のブロック化（重点＝優先度A／全体＝A+B）
を計算し、初代の lw_summary_YYYY-MM.csv と件数で突き合わせる。

設計メモ 2026-09-03（クロ採用）で決めたこと：
  1. raw CSV の「ルーム種別」列は読まない（その1行の受信者数で作られた値であり、rooms表ではない）
  2. ルーム種別の突き合わせ先は lw_summary の「労務安全事象_ルーム別(集計のみ)」「ルーム別上位」
     「ルーム別上位(ヒットのみ)」の補足欄（rooms表＝全期間MAX 由来）。参加者名は読まない・書かない
  3. 出す数字は 対象ルーム数／一致／二代目＜初代／二代目＞初代（逆向き）の4つ
  4. 月内MAXは part1+part2+… を合算した後にだけ計算する。全量でなければ止まる

出力（--out 配下）: check_YYYY-MM.json と check_YYYY-MM.md。個人名・本文・除外語は一切含まない。
終了コード: 0=完了 ／ 1=全量でないため停止 ／ 2=実行エラー
"""
import argparse, csv, glob, hashlib, json, os, re, sys
from collections import Counter, defaultdict

csv.field_size_limit(10 ** 9)
CONTEXT = 2
RAW_HEADER = ["日時", "送信者", "受信者", "チャンネルID", "ルーム種別", "トーク"]
RE_MEMBER_SCAN = re.compile(r"[^,]+?\([^()]*\)")
RE_LABEL_N = re.compile(r"\((\d+)名\)")
SUMMARY_ROOM_KINDS_C = ("労務安全事象_ルーム別(集計のみ)",)
SUMMARY_ROOM_KINDS_TOP = ("ルーム別上位", "ルーム別上位(ヒットのみ)")


# ------------------------------------------------------------ 初代と同じ規則
def count_recipients(s):
    s = (s or "").strip()
    if not s:
        return 0
    hits = RE_MEMBER_SCAN.findall(s)
    if hits:
        return len(hits)
    return len([x for x in s.split(",") if x.strip()])


def row_id(ts, sender, channel, body):
    h = hashlib.sha1()
    h.update(("\x1f".join([ts, sender, channel, body])).encode("utf-8"))
    return h.hexdigest()


def load_keywords(path):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            kw = (row.get("キーワード") or "").strip()
            if not kw:
                continue
            ex = [x for x in (row.get("除外語") or "").split("|") if x.strip()]
            pri = (row.get("優先度") or "A").strip().upper()[:1] or "A"
            out.append((row.get("カテゴリ", "").strip(), kw, ex, pri))
    return out


def occurrences(hay, needle):
    i = hay.find(needle)
    while i >= 0:
        yield i
        i = hay.find(needle, i + 1)


def hit_keywords(body, keywords):
    hits = []
    for cat, kw, excl, pri in keywords:
        pos = list(occurrences(body, kw))
        if not pos:
            continue
        if excl:
            spans = []
            for e in excl:
                for p in occurrences(body, e):
                    spans.append((p, p + len(e)))
            pos = [i for i in pos if not any(s <= i and i + len(kw) <= t for s, t in spans)]
        if not pos:
            continue
        hits.append((cat, kw, pri))
    return hits


def label_of(n):
    return "1対1" if n <= 1 else "グループ(%d名)" % n


def label_num(label):
    m = RE_LABEL_N.search(label or "")
    return int(m.group(1)) if m else 1


# ------------------------------------------------------------ 入力
def find_parts(raw_dir, ym):
    pat = re.compile(r"^lw_raw_%s(?:_part(\d+))?\.csv$" % re.escape(ym))
    parts = []
    for p in sorted(glob.glob(os.path.join(raw_dir, "lw_raw_%s*.csv" % ym))):
        m = pat.match(os.path.basename(p))
        if not m:
            continue  # _v2 などの別版は対象外（どれが正かは人が決める）
        parts.append((int(m.group(1)) if m.group(1) else 1, p))
    parts.sort()
    return parts


def read_raw(parts):
    """設計メモ1: 「ルーム種別」列（index 4）は読まない。"""
    rows, seen = [], set()
    dup = bad = 0
    per_file = {}
    for _, p in parts:
        n = 0
        with open(p, encoding="utf-8-sig", newline="") as f:
            r = csv.reader(f)
            hdr = [h.strip() for h in next(r)]
            if hdr[:6] != RAW_HEADER:
                raise SystemExit("列が想定と違います: %s" % os.path.basename(p))
            for row in r:
                if len(row) < 6:
                    bad += 1
                    continue
                ts, sender, rcpt, cid, _ignored_label, body = row[:6]
                ts, sender, cid = ts.strip(), sender.strip(), cid.strip()
                if len(ts) < 10:
                    bad += 1
                    continue
                rid = row_id(ts, sender, cid, body)
                if rid in seen:
                    dup += 1
                    continue
                seen.add(rid)
                n += 1
                rows.append((ts, ts[:7], cid, count_recipients(rcpt), body))
        per_file[os.path.basename(p)] = n
    return rows, dup, bad, per_file


def read_summary(path):
    """初代の lw_summary から ①月次合計 ②カテゴリ別 ③キーワード別 ④C語×ルーム ⑤ルームID→種別 を取る。
    設計メモ2: 種別は補足欄から種別だけを切り出し、参加者名は捨てる（変数にも残さない）。"""
    total = None
    by_cat, by_kw, by_c = {}, {}, {}
    room_label, room_conflict = {}, set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r)
        for kind, ym, key, note, n in r:
            n = int(n)
            if kind == "月次合計":
                total = n
            elif kind == "カテゴリ別":
                by_cat[key] = n
            elif kind == "キーワード別":
                by_kw[key] = n
            elif kind in SUMMARY_ROOM_KINDS_C:
                kw, _, lab = note.partition(" / ")
                by_c[(kw.strip(), key)] = n
                lab = lab.strip()
                if lab:
                    if key in room_label and room_label[key] != lab:
                        room_conflict.add(key)
                    room_label[key] = lab
            elif kind in SUMMARY_ROOM_KINDS_TOP:
                lab = note.split(" / ", 1)[0].strip()  # 先頭の種別だけ。以降（参加者）は捨てる
                if lab:
                    if key in room_label and room_label[key] != lab:
                        room_conflict.add(key)
                    room_label[key] = lab
    return total, by_cat, by_kw, by_c, room_label, room_conflict


# ------------------------------------------------------------ 集計
def aggregate(rows, keywords):
    by_cat, by_kw, by_c, by_room = Counter(), Counter(), Counter(), Counter()
    per_channel = defaultdict(list)
    hit_a, hit_ab = set(), set()
    maxn = defaultdict(int)
    for i, (ts, ym, cid, nr, body) in enumerate(rows):
        maxn[cid] = max(maxn[cid], nr)
        by_room[cid] += 1
        per_channel[cid].append(i)
        hits = hit_keywords(body or "", keywords)
        for cat, kw, pri in hits:
            by_kw[kw] += 1
            if pri == "C":
                by_c[(kw, cid)] += 1
        for cat in {c for c, _, _ in hits}:
            by_cat[cat] += 1
        if any(p == "A" for _, _, p in hits):
            hit_a.add(i)
        if any(p in ("A", "B") for _, _, p in hits):
            hit_ab.add(i)

    def blocks(hitset):
        nb = 0
        for cid, idxs in per_channel.items():
            idxs = sorted(idxs, key=lambda i: rows[i][0])
            marks = [k for k, i in enumerate(idxs) if i in hitset]
            if not marks:
                continue
            spans = []
            for m in marks:
                lo, hi = max(0, m - CONTEXT), min(len(idxs) - 1, m + CONTEXT)
                if spans and lo <= spans[-1][1] + 1:
                    spans[-1][1] = max(spans[-1][1], hi)
                else:
                    spans.append([lo, hi])
            nb += len(spans)
        return nb

    extract = {"重点_hits": len(hit_a), "重点_blocks": blocks(hit_a),
               "全体_hits": len(hit_ab), "全体_blocks": blocks(hit_ab)}
    return by_cat, by_kw, by_c, by_room, maxn, extract


def diff_table(a, b, keys):
    out = []
    for k in keys:
        x, y = a.get(k, 0), b.get(k, 0)
        out.append((k, y, x, x - y))  # (キー, 初代, 二代目, 差)
    return out


# ------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--keywords", required=True)
    ap.add_argument("--summary", required=True, help="初代の lw_summary_YYYY-MM.csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-parts", type=int, default=None,
                    help="READMEに書かれた part の本数。省略時は連番の欠けだけを見る")
    a = ap.parse_args()
    ym = a.month
    os.makedirs(a.out, exist_ok=True)

    parts = find_parts(a.raw_dir, ym)
    nums = [n for n, _ in parts]
    # 設計メモ4: 全量でなければ計算しない
    problems = []
    if not parts:
        problems.append("raw CSV が見つからない")
    if nums and nums != list(range(1, len(nums) + 1)):
        problems.append("part の連番に欠けがある: %s" % nums)
    if a.expect_parts is not None and len(nums) != a.expect_parts:
        problems.append("part の本数が README と違う: %d≠%d" % (len(nums), a.expect_parts))

    total_ref, cat_ref, kw_ref, c_ref, label_ref, label_conflict = read_summary(a.summary)
    rows, dup, bad, per_file = read_raw(parts) if parts else ([], 0, 0, {})
    rows_ym = [r for r in rows if r[1] == ym]
    if total_ref is not None and len(rows_ym) != total_ref:
        problems.append("対象月の行数が初代の月次合計と違う: %d≠%d（全量ではない可能性）" % (len(rows_ym), total_ref))

    res = {"month": ym, "parts": [os.path.basename(p) for _, p in parts], "rows_per_file": per_file,
           "rows_total": len(rows), "rows_ym": len(rows_ym), "dup_within": dup, "bad_rows": bad,
           "summary_total": total_ref, "stopped": bool(problems), "problems": problems}
    if problems:
        json.dump(res, open(os.path.join(a.out, "check_%s.json" % ym), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("停止（全量ではありません）: " + "／".join(problems))
        sys.exit(1)

    keywords = load_keywords(a.keywords)
    by_cat, by_kw, by_c, by_room, maxn, extract = aggregate(rows_ym, keywords)

    # 設計メモ3: ルーム種別の4つの数字（相手は lw_summary の補足欄）
    cmp = Counter()
    reverse_rooms = []
    for cid, lab_ref in label_ref.items():
        if cid not in maxn:
            cmp["初代側のみ（対象月の raw に無い）"] += 1
            continue
        mine = maxn[cid]
        ref = label_num(lab_ref)
        if label_of(mine) == lab_ref:
            cmp["一致"] += 1
        elif mine < ref:
            cmp["二代目＜初代"] += 1
        else:
            cmp["二代目＞初代（逆向き）"] += 1
            reverse_rooms.append(cid[:8])
    room_cmp = {"対象ルーム数": len(label_ref), **{k: cmp.get(k, 0) for k in
                ("一致", "二代目＜初代", "二代目＞初代（逆向き）", "初代側のみ（対象月の raw に無い）")},
                "初代側で種別が行により食い違うルーム数": len(label_conflict)}

    cats = sorted(set(cat_ref) | set(by_cat), key=lambda k: -max(cat_ref.get(k, 0), by_cat.get(k, 0)))
    kws = sorted(set(kw_ref) | set(by_kw), key=lambda k: -max(kw_ref.get(k, 0), by_kw.get(k, 0)))
    c_words_ref = Counter()
    for (kw, cid), n in c_ref.items():
        c_words_ref[kw] += n
    c_words = Counter()
    for (kw, cid), n in by_c.items():
        c_words[kw] += n
    c_room_ref = Counter()
    for (kw, cid), n in c_ref.items():
        c_room_ref[cid] += n
    c_room = Counter()
    for (kw, cid), n in by_c.items():
        c_room[cid] += n

    res.update({
        "category": diff_table(by_cat, cat_ref, cats),
        "keyword": diff_table(by_kw, kw_ref, kws),
        "c_word": diff_table(c_words, c_words_ref, sorted(set(c_words_ref) | set(c_words))),
        "c_room_pairs": {"初代": len(c_ref), "二代目": len(by_c),
                         "一致": sum(1 for k in c_ref if by_c.get(k) == c_ref[k])},
        "c_room_top10_ref": [(cid[:8], n) for cid, n in c_room_ref.most_common(10)],
        "c_room_top10_code": [(cid[:8], n) for cid, n in c_room.most_common(10)],
        "extract": extract,
        "room_label": room_cmp,
        "room_label_reverse_examples": reverse_rooms[:10],
        "rooms_in_month": len(maxn),
    })
    json.dump(res, open(os.path.join(a.out, "check_%s.json" % ym), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    L = ["# 並走テスト 突き合わせ結果｜%s（件数のみ・個人名・本文なし）" % ym, "",
         "**ヒット＝問題ではありません。** 差の原因は断定しません。", "",
         "## 1. 入力", "",
         "- part: %s" % "、".join(res["parts"]),
         "- 行数: %s（対象月 %s／初代の月次合計 %s／ファイル内重複 %d／壊れた行 %d）" % (
             format(len(rows), ","), format(len(rows_ym), ","), format(total_ref, ","), dup, bad), "",
         "## 2. カテゴリ別ヒット発言数（初代 → 二代目）", "",
         "| カテゴリ | 初代 | 二代目 | 差 |", "|---|---|---|---|"]
    L += ["| %s | %d | %d | %+d |" % r for r in res["category"]]
    L += ["", "## 3. キーワード別（差のあるものだけ）", "", "| 語 | 初代 | 二代目 | 差 |", "|---|---|---|---|"]
    L += ["| %s | %d | %d | %+d |" % r for r in res["keyword"] if r[3] != 0] or ["| （差なし） | | | |"]
    L += ["", "## 4. 労務安全事象（優先度C・集計のみ）", "", "| 語 | 初代 | 二代目 | 差 |", "|---|---|---|---|"]
    L += ["| %s | %d | %d | %+d |" % r for r in res["c_word"]]
    L += ["", "語×ルームの組: 初代 %d／二代目 %d／件数まで一致 %d" % (
        res["c_room_pairs"]["初代"], res["c_room_pairs"]["二代目"], res["c_room_pairs"]["一致"]), "",
         "## 5. 抽出CSVの規模（二代目の計算値。初代の値は実行ログ `_out_YYYYMM.txt` と突き合わせる）", "",
         "重点 %(重点_hits)d ヒット／%(重点_blocks)d ブロック、全体 %(全体_hits)d ヒット／%(全体_blocks)d ブロック" % extract, "",
         "## 6. ルーム種別（相手＝lw_summary の補足欄・rooms表由来）", "",
         "| 項目 | 件数 |", "|---|---|"]
    L += ["| %s | %d |" % kv for kv in room_cmp.items()]
    if reverse_rooms:
        L += ["", "逆向きのルーム（ID先頭8桁）: " + "、".join(reverse_rooms[:10]),
              "→ 切り出し以外の原因を疑う材料。原因は断定しない。"]
    open(os.path.join(a.out, "check_%s.md" % ym), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # 原因は断定せず、全文を残して止める
        import traceback
        traceback.print_exc()
        print("実行エラー: %s" % e)
        sys.exit(2)
