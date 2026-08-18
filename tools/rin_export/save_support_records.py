#!/usr/bin/env python3
"""RIN の提供実績記録表（支援記録）を、利用者ごと・年月ごとに HTML で保存する。

RIN には外部 API が無いため、Playwright でブラウザを実際に操作して
次の順に画面をたどり、記録表のページを保存する。

    ログイン → 事業所を選ぶ → 利用者一覧 → 利用者を選ぶ
             → 提供実績タブ → 提供実績記録表（年月を切替）→ HTML 保存

保存先は次の形になる。

    out/
      さくら生活介護センター/
        利用者一覧.html
        利用者一覧.csv
        2026-01/
          提供実績_岩村  伸一_2026-01.html
        ...

ログイン情報はコマンドライン引数ではなく環境変数（.env）から読む。
画面のセレクタはすべて config.json に外出ししてあるので、RIN 側の画面が
変わってもコードを触らずに追従できる。詳細は README.md を参照。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import Locator, Page, sync_playwright

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv が無くても環境変数さえあれば動く
    load_dotenv = None

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.json"
DEFAULT_STATE = HERE / "state.json"

# Windows / macOS のどちらでも作れるファイル名にするために潰す文字。
UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')

# 改行を含む空白の連なり（HTML のインデント）だけをまとめるための正規表現。
LAYOUT_WHITESPACE = re.compile(r"[^\S\r\n]*[\r\n]\s*")


def die(message: str) -> None:
    print(f"エラー: {message}", file=sys.stderr)
    sys.exit(1)


class NotConfigured(Exception):
    """config.json の★印が埋まっていない項目があることを表す。"""


def is_placeholder(value: Any) -> bool:
    """config.example.json の★印のまま（未設定）かどうか。"""
    return not isinstance(value, str) or not value.strip() or value.lstrip().startswith("★")


def configured(value: Any) -> str:
    """埋まっていれば値を返し、★のままなら空文字を返す（任意項目の判定用）。"""
    return "" if is_placeholder(value) else value.strip()


def need(section: dict[str, Any], key: str, path: str) -> str:
    """必須項目を取り出す。★のままなら、どこを埋めればよいかを示して止める。"""
    value = (section or {}).get(key, "")
    if is_placeholder(value):
        raise NotConfigured(
            f"config.json の {path} がまだ★のままです。"
            "inspect で保存した HTML を見てセレクタを埋めてください。"
        )
    return value.strip()


# --------------------------------------------------------------------------
# 値オブジェクト
# --------------------------------------------------------------------------
@dataclass
class Office:
    name: str
    office_id: str = ""
    url: str = ""


@dataclass
class RinUser:
    name: str
    user_id: str = ""
    url: str = ""
    extra: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------
# 設定・年月
# --------------------------------------------------------------------------
def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        die(
            f"設定ファイルが見つかりません: {path}\n"
            "config.example.json をコピーして config.json を作り、RIN の画面に合わせて編集してください。"
        )
    with path.open(encoding="utf-8") as f:
        config = json.load(f)
    for key in ("login", "users", "record"):
        if key not in config:
            die(f"設定ファイルに '{key}' セクションがありません: {path}")
    return config


def parse_months(spec: str) -> list[str]:
    """'2026-01..2026-07' や '2026-01,2026-03' を YYYY-MM のリストにする。"""
    months: list[str] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ".." in chunk:
            start, end = (part.strip() for part in chunk.split("..", 1))
            current, last = month_index(start), month_index(end)
            if current > last:
                die(f"年月の範囲が逆さまです: {chunk}")
            while current <= last:
                months.append(index_month(current))
                current += 1
        else:
            months.append(index_month(month_index(chunk)))
    if not months:
        die("対象の年月が空です。--months 2026-01..2026-07 のように指定してください。")
    return months


def month_index(value: str) -> int:
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", value.strip())
    if not match:
        die(f"年月の書式が不正です（YYYY-MM で指定してください）: {value}")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        die(f"月が 1〜12 の範囲外です: {value}")
    return year * 12 + (month - 1)


def index_month(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def safe_name(value: str) -> str:
    """ファイル名・フォルダ名に使える形に整える（利用者名の空白はそのまま残す）。"""
    cleaned = UNSAFE_FILENAME_CHARS.sub("_", value).strip().rstrip(".")
    return cleaned or "名称不明"


# --------------------------------------------------------------------------
# ページ操作の共通部品
# --------------------------------------------------------------------------
def absolute_url(config: dict[str, Any], url: str) -> str:
    base = config.get("base_url", "")
    return urljoin(base, url) if base else url


def goto(page: Page, config: dict[str, Any], url: str, ready_selector: str | None = None) -> None:
    page.goto(absolute_url(config, url), wait_until="domcontentloaded")
    ready = configured(ready_selector)
    if ready:
        page.wait_for_selector(ready)


def clean_text(raw: str) -> str:
    """HTML から取り出した文字列を整える。

    改行まじりのインデントは空白1つにまとめるが、「岩村  伸一」のように
    氏名の途中に入っている連続スペースは RIN の登録内容そのものなので残す。
    （inner_text() は表示上の見た目で空白を詰めてしまうため使わない）
    """
    return LAYOUT_WHITESPACE.sub(" ", raw or "").strip()


def text_of(locator: Locator) -> str:
    return clean_text(locator.text_content() or "") if locator.count() else ""


def extract_id(value: str, pattern: str | None) -> str:
    if not pattern:
        return ""
    match = re.search(pattern, value or "")
    return match.group(1) if match else ""


def go_to_next_page(page: Page, pagination: dict[str, Any]) -> bool:
    """一覧の「次へ」を押す。押せなければ False。"""
    if pagination.get("mode") != "next_button":
        return False
    next_selector = configured(pagination.get("next_selector"))
    if not next_selector:
        return False
    locator = page.locator(next_selector).first
    if locator.count() == 0 or not locator.is_visible() or not locator.is_enabled():
        return False
    if "disabled" in (locator.get_attribute("class") or ""):
        return False
    if locator.get_attribute("aria-disabled") == "true":
        return False
    locator.click()
    return True


# --------------------------------------------------------------------------
# ログイン
# --------------------------------------------------------------------------
def do_form_login(page: Page, config: dict[str, Any]) -> None:
    login = config["login"]
    user = os.environ.get("RIN_USER", "")
    password = os.environ.get("RIN_PASSWORD", "")
    if not user or not password:
        die(
            "環境変数 RIN_USER / RIN_PASSWORD が未設定です。\n"
            "同じフォルダに .env を置くか、シェルで export してください。\n"
            "（2要素認証などでフォームログインできない場合は login --manual を使ってください）"
        )
    goto(page, config, need(login, "url", "login.url"))
    page.fill(need(login, "user_selector", "login.user_selector"), user)
    page.fill(need(login, "password_selector", "login.password_selector"), password)
    page.click(need(login, "submit_selector", "login.submit_selector"))
    success_selector = configured(login.get("success_selector"))
    if success_selector:
        page.wait_for_selector(success_selector)
    else:
        page.wait_for_load_state("networkidle")
    print("ログインしました。")


def do_manual_login(page: Page, config: dict[str, Any]) -> None:
    goto(page, config, need(config["login"], "url", "login.url"))
    print()
    print("ブラウザが開きました。手でログインを完了させてください。")
    print("ログイン後の画面が表示されたら、このターミナルで Enter を押してください。")
    input("  → 完了したら Enter: ")


def ensure_logged_in(page: Page, config: dict[str, Any], manual: bool) -> None:
    do_manual_login(page, config) if manual else do_form_login(page, config)


# --------------------------------------------------------------------------
# 事業所
# --------------------------------------------------------------------------
def collect_offices(page: Page, config: dict[str, Any]) -> list[Office]:
    offices_cfg = config.get("offices", {}) or {}
    mode = offices_cfg.get("mode", "fixed")

    if mode == "fixed":
        entries = offices_cfg.get("list", [])
        if not entries:
            # 事業所の切り替えが無いシステム構成の場合は、1つだけ扱う。
            return [Office(name=offices_cfg.get("default_name", "事業所"))]
        return [
            Office(name=e["name"], office_id=str(e.get("id", "")), url=e.get("url", ""))
            for e in entries
        ]

    list_url = need(offices_cfg, "list_url", "offices.list_url")
    row_selector = need(offices_cfg, "row_selector", "offices.row_selector")
    goto(page, config, list_url, offices_cfg.get("ready_selector"))
    offices: list[Office] = []
    for link in page.locator(row_selector).all():
        href = link.get_attribute("href") or ""
        offices.append(
            Office(
                name=clean_text(link.text_content() or ""),
                office_id=extract_id(href, offices_cfg.get("id_pattern")),
                url=href,
            )
        )
    return offices


def filter_offices(offices: list[Office], only: list[str]) -> list[Office]:
    if not only:
        return offices
    wanted = {name.strip() for name in only}
    selected = [office for office in offices if office.name.strip() in wanted]
    missing = wanted - {office.name.strip() for office in selected}
    if missing:
        print(f"警告: 指定された事業所が見つかりません: {', '.join(sorted(missing))}", file=sys.stderr)
    return selected


# --------------------------------------------------------------------------
# 利用者一覧
# --------------------------------------------------------------------------
def collect_users(page: Page, config: dict[str, Any], office: Office) -> tuple[list[RinUser], str]:
    """利用者一覧を取得し、(利用者リスト, 一覧ページのHTML) を返す。"""
    users_cfg = config["users"]
    list_url = office.url or need(
        users_cfg, "list_url_template", "users.list_url_template"
    ).format(office_id=office.office_id)
    row_selector = need(users_cfg, "row_selector", "users.row_selector")
    goto(page, config, list_url, users_cfg.get("ready_selector"))

    pagination = users_cfg.get("pagination", {}) or {}
    max_pages = pagination.get("max_pages", 100)
    wait_ms = pagination.get("wait_ms", 500)

    users: list[RinUser] = []
    seen_ids: set[str] = set()
    first_page_html = page.content()

    for _ in range(max_pages):
        for row in page.locator(row_selector).all():
            name_selector = configured(users_cfg.get("name_selector"))
            name = text_of(row.locator(name_selector).first) if name_selector else text_of(row)
            if not name:
                continue
            link = row.locator(configured(users_cfg.get("link_selector")) or "a").first
            href = link.get_attribute("href") or "" if link.count() else ""
            user_id = extract_id(href, users_cfg.get("id_pattern"))
            key = user_id or f"{name}|{href}"
            if key in seen_ids:
                continue
            seen_ids.add(key)
            users.append(RinUser(name=name, user_id=user_id, url=href))

        if not go_to_next_page(page, pagination):
            break
        list_ready = configured(users_cfg.get("ready_selector"))
        if list_ready:
            page.wait_for_selector(list_ready)
        time.sleep(wait_ms / 1000)

    return users, first_page_html


# --------------------------------------------------------------------------
# 提供実績記録表
# --------------------------------------------------------------------------
def open_record_page(page: Page, config: dict[str, Any], user: RinUser, year: int, month: int) -> None:
    """指定した利用者・年月の提供実績記録表を表示する。"""
    record_cfg = config["record"]
    ready = configured(record_cfg.get("ready_selector"))

    if record_cfg.get("mode", "url") == "url":
        url = need(record_cfg, "url_template", "record.url_template").format(
            user_id=user.user_id,
            year=year,
            month=month,
            month2=f"{month:02d}",
            year_month=f"{year}-{month:02d}",
        )
        goto(page, config, url, ready)
        return

    # 画面をクリックしてたどる方式。
    ui = record_cfg.get("ui", {}) or {}
    detail_url = user.url or need(
        ui, "user_detail_url_template", "record.ui.user_detail_url_template"
    ).format(user_id=user.user_id)
    goto(page, config, detail_url)

    page.click(need(ui, "performance_tab_selector", "record.ui.performance_tab_selector"))
    performance_ready = configured(ui.get("performance_ready_selector"))
    if performance_ready:
        page.wait_for_selector(performance_ready)

    page.click(need(ui, "record_link_selector", "record.ui.record_link_selector"))
    if ready:
        page.wait_for_selector(ready)

    # 年月を切り替える。プルダウンや「表示」ボタンが無い画面もあるので、
    # 埋まっている項目だけを操作する。
    year_select = configured(ui.get("year_select"))
    if year_select:
        page.select_option(year_select, str(year))
    month_select = configured(ui.get("month_select"))
    if month_select:
        month_value = f"{month:02d}" if ui.get("month_zero_pad") else str(month)
        page.select_option(month_select, month_value)
    apply_selector = configured(ui.get("apply_selector"))
    if apply_selector:
        page.click(apply_selector)
        if ready:
            page.wait_for_selector(ready)
    page.wait_for_load_state("domcontentloaded")


def save_html(page: Page, path: Path, inject_base: bool) -> None:
    html = page.content()
    if inject_base and "<base " not in html:
        # 後から手元で開いたときに CSS や画像の相対パスが解決できるようにする。
        html = re.sub(
            r"(<head[^>]*>)",
            rf'\1<base href="{page.url}">',
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def write_user_list(office_dir: Path, users: list[RinUser], html: str) -> None:
    office_dir.mkdir(parents=True, exist_ok=True)
    (office_dir / "利用者一覧.html").write_text(html, encoding="utf-8")
    with (office_dir / "利用者一覧.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["利用者名", "利用者ID", "詳細URL"])
        for user in users:
            writer.writerow([user.name, user.user_id, user.url])


# --------------------------------------------------------------------------
# コマンド
# --------------------------------------------------------------------------
def build_context(playwright, args, config):
    browser = playwright.chromium.launch(
        headless=args.headless,
        slow_mo=args.slow_mo,
        executable_path=os.environ.get("RIN_CHROMIUM_PATH") or None,
    )
    state_path = Path(args.state)
    context = browser.new_context(
        storage_state=str(state_path) if state_path.exists() else None,
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
    )
    context.set_default_timeout(config.get("timeout_ms", 30000))
    return browser, context


def cmd_login(args, config) -> int:
    with sync_playwright() as playwright:
        browser, context = build_context(playwright, args, config)
        page = context.new_page()
        try:
            ensure_logged_in(page, config, args.manual)
            context.storage_state(path=args.state)
            print(f"ログイン状態を保存しました: {args.state}")
        finally:
            browser.close()
    return 0


def cmd_inspect(args, config) -> int:
    """各段階の画面を HTML で保存する。セレクタを確定させるための調査用。

    ★印がまだ埋まっていない段階で実行するコマンドなので、途中でたどれなく
    なっても止めずに、その時点で開いている画面を保存して次に進む。
    保存された HTML を見て★を埋め、また実行する、という往復を想定している。
    """
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser, context = build_context(playwright, args, config)
        page = context.new_page()
        saved: list[str] = []
        blocked: list[str] = []

        def snapshot(filename: str, html: str | None = None) -> None:
            content = page.content() if html is None else html
            (out_dir / filename).write_text(content, encoding="utf-8")
            saved.append(filename)

        def blocked_here(stage: str, exc: Exception) -> None:
            blocked.append(f"{stage}: {exc}")
            print(f"  {stage}をたどれませんでした: {exc}", file=sys.stderr)

        try:
            if not Path(args.state).exists():
                ensure_logged_in(page, config, args.manual)

            # ログイン直後の画面。事業所一覧や利用者一覧への入口を探す手がかりになる。
            goto(page, config, configured(config.get("home_url")) or config["login"]["url"])
            snapshot("00_ログイン直後.html")

            offices: list[Office] = []
            try:
                offices = collect_offices(page, config)
                print(f"事業所: {', '.join(o.name for o in offices) or '（0件）'}")
            except Exception as exc:
                blocked_here("事業所一覧", exc)
            snapshot("01_事業所一覧.html")

            users: list[RinUser] = []
            if offices:
                try:
                    users, users_html = collect_users(page, config, offices[0])
                    print(f"利用者: {len(users)}名（先頭: {users[0].name if users else '0件'}）")
                    snapshot("02_利用者一覧.html", users_html)
                except Exception as exc:
                    blocked_here("利用者一覧", exc)
                    snapshot("02_利用者一覧.html")
            else:
                blocked_here("利用者一覧", Exception("事業所を1件も取得できなかったため進めません"))
                snapshot("02_利用者一覧.html")

            if users:
                today = date.today()
                try:
                    open_record_page(page, config, users[0], today.year, today.month)
                except Exception as exc:
                    blocked_here("提供実績記録表", exc)
                snapshot("03_提供実績記録表.html")
                try:
                    page.screenshot(path=str(out_dir / "03_提供実績記録表.png"), full_page=True)
                    saved.append("03_提供実績記録表.png")
                except Exception as exc:
                    print(f"  スクリーンショットを保存できませんでした: {exc}", file=sys.stderr)
        finally:
            browser.close()

    print()
    print(f"保存先: {out_dir}")
    for name in saved:
        print(f"  - {name}")
    if blocked:
        print()
        print("まだたどれていない段階:")
        for message in blocked:
            print(f"  - {message}")
        print()
        print("保存された HTML を見て config.json の★を埋め、もう一度 inspect を実行してください。")
    print()
    print("※利用者の氏名など個人情報が含まれます。共有する前に必ず中身を確認してください。")
    return 0


def cmd_run(args, config) -> int:
    months = parse_months(args.months or ",".join(config.get("output", {}).get("months", [])))
    output_cfg = config.get("output", {})
    out_dir = Path(args.out_dir or output_cfg.get("dir", "out"))
    if not out_dir.is_absolute():
        out_dir = HERE / out_dir
    inject_base = output_cfg.get("inject_base_href", True)
    wait_ms = output_cfg.get("wait_ms", 800)

    print(f"対象年月: {months[0]} 〜 {months[-1]}（{len(months)}か月）")
    print(f"保存先  : {out_dir}")
    print()

    saved_count = skipped_count = 0
    errors: list[str] = []
    manifest: list[dict[str, str]] = []

    with sync_playwright() as playwright:
        browser, context = build_context(playwright, args, config)
        page = context.new_page()
        try:
            if not Path(args.state).exists():
                ensure_logged_in(page, config, args.manual)

            offices = filter_offices(
                collect_offices(page, config),
                args.offices or config.get("offices", {}).get("only", []),
            )
            if not offices:
                die("対象の事業所が0件でした。config.json の offices 設定を確認してください。")

            for office in offices:
                print(f"■ {office.name}")
                users, users_html = collect_users(page, config, office)
                if not users:
                    errors.append(f"{office.name}: 利用者一覧が0件でした")
                    print("  利用者を取得できませんでした。", file=sys.stderr)
                    continue

                office_dir = out_dir / safe_name(office.name)
                write_user_list(office_dir, users, users_html)
                print(f"  利用者 {len(users)}名の一覧を保存しました。")

                if args.limit_users:
                    users = users[: args.limit_users]

                for user in users:
                    for year_month in months:
                        year, month = int(year_month[:4]), int(year_month[5:])
                        target = (
                            office_dir
                            / year_month
                            / f"提供実績_{safe_name(user.name)}_{year_month}.html"
                        )
                        if target.exists() and not args.overwrite:
                            skipped_count += 1
                            continue
                        try:
                            open_record_page(page, config, user, year, month)
                            save_html(page, target, inject_base)
                            saved_count += 1
                            manifest.append(
                                {
                                    "事業所": office.name,
                                    "利用者名": user.name,
                                    "年月": year_month,
                                    "保存先": str(target.relative_to(out_dir)),
                                    "取得元URL": page.url,
                                }
                            )
                            print(f"  保存: {user.name} {year_month}")
                        except Exception as exc:  # 1件失敗しても残りは続行する
                            message = f"{office.name} / {user.name} / {year_month}: {exc}"
                            errors.append(message)
                            print(f"  失敗: {message}", file=sys.stderr)
                        time.sleep(wait_ms / 1000)
        finally:
            browser.close()

    if manifest:
        manifest_path = out_dir / "保存一覧.csv"
        write_manifest(manifest_path, manifest, append=not args.overwrite)
        print(f"\n保存した内容の一覧: {manifest_path}")

    print(f"\n保存 {saved_count}件 / スキップ（既存）{skipped_count}件 / 失敗 {len(errors)}件")
    if errors:
        print("\n失敗した分:", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        return 1
    return 0


def write_manifest(path: Path, rows: list[dict[str, str]], append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["事業所", "利用者名", "年月", "保存先", "取得元URL"]
    exists = path.exists()
    mode = "a" if append and exists else "w"
    with path.open(mode, encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if mode == "w" or not exists:
            writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="RIN の提供実績記録表を利用者ごと・年月ごとに HTML で保存する",
    )
    parser.add_argument("command", choices=["login", "inspect", "run"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="設定ファイルのパス")
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="ログイン状態の保存先")
    parser.add_argument("--months", help="対象年月。例: 2026-01..2026-07")
    parser.add_argument("--offices", nargs="*", help="対象の事業所名（省略時は全事業所）")
    parser.add_argument("--out-dir", help="保存先フォルダ")
    parser.add_argument("--overwrite", action="store_true", help="既に保存済みのファイルも取り直す")
    parser.add_argument("--limit-users", type=int, help="各事業所で先頭N名だけ処理する（試運転用）")
    parser.add_argument("--manual", action="store_true", help="手動でログインする（2要素認証など）")
    parser.add_argument("--headless", action="store_true", help="ブラウザを表示せずに実行する")
    parser.add_argument("--slow-mo", type=int, default=0, help="操作を遅くする（ミリ秒・デバッグ用）")
    args = parser.parse_args(argv)

    if args.manual:
        args.headless = False
    if args.command == "inspect" and not args.out_dir:
        args.out_dir = str(HERE / "out" / "inspect")

    if load_dotenv:
        load_dotenv(HERE / ".env")
        load_dotenv(HERE.parent.parent / ".env")

    config = load_config(Path(args.config))
    try:
        return {"login": cmd_login, "inspect": cmd_inspect, "run": cmd_run}[args.command](args, config)
    except NotConfigured as exc:
        die(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
