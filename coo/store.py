"""レポートと判断ログの保存・読み出し。

- reports/report-YYYY-MM-DD-HHMM.json : クロが生成したレポート本体
- reports/decision_log.json           : CEOの決裁記録（承認/却下/保留）
どちらも実データを含むため .gitignore 済み。共有したいときだけ明示的に扱う。
"""

import json
from datetime import datetime
from pathlib import Path

from .config import DECISION_LOG_PATH, REPORTS_DIR, SAMPLE_REPORT_PATH

VALID_STATUSES = {"pending", "approved", "rejected", "deferred"}


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_report(report: dict) -> str:
    """レポートを保存し、report_id を返す。"""
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    report_id = f"report-{stamp}"
    report["report_id"] = report_id
    report["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _write_json(REPORTS_DIR / f"{report_id}.json", report)
    return report_id


def list_reports() -> list[dict]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(REPORTS_DIR.glob("report-*.json"), reverse=True):
        data = _read_json(path, {})
        items.append(
            {
                "report_id": data.get("report_id", path.stem),
                "report_date": data.get("report_date", ""),
                "headline": data.get("headline", ""),
                "overall_status": data.get("overall_status", "unknown"),
                "generated_at": data.get("generated_at", ""),
            }
        )
    return items


def get_report(report_id: str) -> dict | None:
    """report_id 指定でレポートを取得（パストラバーサル対策込み）。"""
    if not report_id.startswith("report-") or "/" in report_id or "\\" in report_id:
        return None
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return None
    return with_decisions(_read_json(path, {}))


def latest_report() -> dict | None:
    """最新レポート。1件も無ければサンプルを is_sample つきで返す。"""
    reports = sorted(REPORTS_DIR.glob("report-*.json"), reverse=True)
    if reports:
        return with_decisions(_read_json(reports[0], {}))
    sample = _read_json(SAMPLE_REPORT_PATH, None)
    if sample is None:
        return None
    sample["is_sample"] = True
    return with_decisions(sample)


# --- 判断ログ ---------------------------------------------------------------

def decision_log() -> dict:
    return _read_json(DECISION_LOG_PATH, {})


def record_decision(report_id: str, decision_id: str, status: str, note: str = "") -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"未知のステータス: {status}")
    log = decision_log()
    key = f"{report_id}::{decision_id}"
    entry = {
        "report_id": report_id,
        "decision_id": decision_id,
        "status": status,
        "note": note,
        "decided_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    log[key] = entry
    _write_json(DECISION_LOG_PATH, log)
    return entry


def with_decisions(report: dict) -> dict:
    """レポートの decisions に、記録済みの決裁ステータスを付与する。"""
    if not report:
        return report
    log = decision_log()
    report_id = report.get("report_id", "")
    for decision in report.get("decisions", []):
        entry = log.get(f"{report_id}::{decision.get('id')}")
        decision["status"] = entry["status"] if entry else "pending"
        decision["decision_note"] = entry["note"] if entry else ""
        decision["decided_at"] = entry["decided_at"] if entry else ""
    return report


def decision_history() -> list[dict]:
    """決裁の履歴を新しい順で返す。"""
    return sorted(decision_log().values(), key=lambda e: e["decided_at"], reverse=True)
