#!/usr/bin/env python3
"""検証用のダミー RIN。本物と同じ画面遷移だけを模したもの。

  /login
  /offices                                        事業所一覧
  /office?officeId=..                             利用者一覧
  /userDetail?userId=..                           利用者詳細（タブあり）
  /userDetail/performance?userId=..               提供実績タブ
  /userDetail/supportRecordMonthly?userId=..&year=..&month=..   提供実績記録表

save_support_records.py の「ログイン →事業所 →利用者 →提供実績 →記録表HTML保存」
の流れを、本物に触らずに通しで確認するために使う。
"""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

USER = "demo"
PASSWORD = "demo-password"

OFFICES = {
    "1": "さくら生活介護センター",
    "2": "みどり就労支援センター",
}

USERS = {
    "1": [("101", "岩村  伸一"), ("102", "山田 太郎"), ("103", "鈴木 花子")],
    "2": [("201", "高橋 一郎")],
}

LOGIN_PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>RIN ログイン</title></head>
<body>
  <h1>RIN ログイン</h1>
  <form method="post" action="/login">
    <input type="text" id="userId" name="userId">
    <input type="password" id="password" name="password">
    <button type="submit" id="loginButton">ログイン</button>
  </form>
</body></html>"""


def page(title: str, body: str) -> str:
    return (
        f'<!doctype html>\n<html lang="ja"><head><meta charset="utf-8">'
        f"<title>{title}</title></head><body>{body}</body></html>"
    )


def offices_page() -> str:
    rows = "".join(
        f'<tr><td><a class="officeLink" href="/office?officeId={oid}">{name}</a></td></tr>'
        for oid, name in OFFICES.items()
    )
    return page("事業所一覧", f'<h1>事業所一覧</h1><table id="officeTable"><tbody>{rows}</tbody></table>')


def users_page(office_id: str) -> str:
    name = OFFICES[office_id]
    rows = "".join(
        f'<tr><td><a class="userLink" href="/userDetail?userId={uid}">{uname}</a></td>'
        f"<td>{uid}</td><td>生活介護</td></tr>"
        for uid, uname in USERS[office_id]
    )
    return page(
        f"{name} 利用者一覧",
        f"<h1>{name} 利用者一覧</h1>"
        f'<table id="userTable"><thead><tr><th>利用者名</th><th>受給者番号</th><th>サービス</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>",
    )


def find_user(user_id: str) -> tuple[str, str] | None:
    for office_id, members in USERS.items():
        for uid, uname in members:
            if uid == user_id:
                return office_id, uname
    return None


def user_detail_page(user_id: str) -> str:
    found = find_user(user_id)
    if not found:
        return page("該当なし", "<h1>該当なし</h1>")
    _, uname = found
    return page(
        f"{uname} 詳細",
        f"<h1>{uname}</h1>"
        f'<ul id="detailTabs">'
        f'<li><a href="/userDetail?userId={user_id}">基本情報</a></li>'
        f'<li><a id="performanceTab" href="/userDetail/performance?userId={user_id}">提供実績</a></li>'
        f"</ul>",
    )


def performance_page(user_id: str) -> str:
    found = find_user(user_id)
    if not found:
        return page("該当なし", "<h1>該当なし</h1>")
    _, uname = found
    return page(
        f"{uname} 提供実績",
        f"<h1>{uname} 提供実績</h1>"
        f'<a id="supportRecordMonthlyLink" '
        f'href="/userDetail/supportRecordMonthly?userId={user_id}&year=2026&month=7">提供実績記録表</a>',
    )


def support_record_page(user_id: str, year: str, month: str) -> str:
    found = find_user(user_id)
    if not found:
        return page("該当なし", "<h1>該当なし</h1>")
    _, uname = found
    days = "".join(
        f"<tr><td>{day}</td><td>生活介護</td><td>09:30</td><td>15:30</td><td>通所。特変なし。</td></tr>"
        for day in range(1, 4)
    )
    year_options = "".join(
        f'<option value="{y}"{" selected" if str(y) == year else ""}>{y}</option>'
        for y in (2025, 2026)
    )
    month_options = "".join(
        f'<option value="{m}"{" selected" if str(m) == month else ""}>{m}</option>'
        for m in range(1, 13)
    )
    return page(
        f"提供実績記録表 {uname} {year}年{month}月",
        f"<h1>提供実績記録表</h1>"
        f'<p id="targetUser">{uname}</p>'
        f'<form id="periodForm" method="get" action="/userDetail/supportRecordMonthly">'
        f'<input type="hidden" name="userId" value="{user_id}">'
        f'<select id="year" name="year">{year_options}</select>'
        f'<select id="month" name="month">{month_options}</select>'
        f'<button type="submit" id="applyPeriod">表示</button>'
        f"</form>"
        f'<p id="period">{year}年{month}月</p>'
        f'<table id="supportRecordTable"><thead><tr>'
        f"<th>日</th><th>サービス内容</th><th>開始</th><th>終了</th><th>記録</th>"
        f"</tr></thead><tbody>{days}</tbody></table>",
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _logged_in(self) -> bool:
        return "rin_session=ok" in self.headers.get("Cookie", "")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/login":
            self._send(200, LOGIN_PAGE)
            return
        if not self._logged_in():
            self._send(302, "", {"Location": "/login"})
            return

        if parsed.path == "/offices":
            self._send(200, offices_page())
        elif parsed.path == "/office":
            office_id = query.get("officeId", ["1"])[0]
            self._send(200, users_page(office_id) if office_id in USERS else page("該当なし", ""))
        elif parsed.path == "/userDetail":
            self._send(200, user_detail_page(query.get("userId", [""])[0]))
        elif parsed.path == "/userDetail/performance":
            self._send(200, performance_page(query.get("userId", [""])[0]))
        elif parsed.path == "/userDetail/supportRecordMonthly":
            self._send(
                200,
                support_record_page(
                    query.get("userId", [""])[0],
                    query.get("year", ["2026"])[0],
                    query.get("month", ["7"])[0],
                ),
            )
        else:
            self._send(404, "not found")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/login":
            self._send(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        if form.get("userId", [""])[0] == USER and form.get("password", [""])[0] == PASSWORD:
            self._send(302, "", {"Location": "/offices", "Set-Cookie": "rin_session=ok; Path=/"})
        else:
            self._send(200, LOGIN_PAGE.replace("<h1>", "<h1>ログイン失敗 "))


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8799), Handler).serve_forever()
