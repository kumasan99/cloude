"""パス・設定ファイルの読み込みを一箇所にまとめる。"""

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
INBOX_DIR = DATA_DIR / "inbox"
ARCHIVE_DIR = DATA_DIR / "archive"
REPORTS_DIR = ROOT / "reports"
CONFIG_DIR = ROOT / "config"

SAMPLE_REPORT_PATH = REPORTS_DIR / "sample" / "sample-report.json"
DECISION_LOG_PATH = REPORTS_DIR / "decision_log.json"

# レポート生成に使うモデル。環境変数で差し替え可能。
COO_MODEL = os.getenv("COO_MODEL", "claude-opus-5")

# data/inbox 直下のカテゴリ（=CEOが資料を置く場所）
CATEGORIES = {
    "finance": "財務・資金繰り（試算表、資金繰り表、売上台帳、請求・入金）",
    "sales": "売上・案件（パイプライン、受注一覧、見積、顧客別売上）",
    "people": "人・組織（人員名簿、稼働工数、採用状況、離職）",
    "ops": "業務・現場（議事録、日報、問い合わせ、トラブル記録）",
    "strategy": "戦略・計画（事業計画、予算、中期計画、競合情報）",
}


def _load_yaml(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or default


def company_profile() -> dict:
    """会社の前提情報（config/company.yaml）。"""
    return _load_yaml(CONFIG_DIR / "company.yaml", {})


def kpi_definitions() -> list:
    """CEOが見るKPIの定義（config/kpi.yaml）。"""
    data = _load_yaml(CONFIG_DIR / "kpi.yaml", {})
    return data.get("kpis", [])


def data_requirements() -> list:
    """クロが必要としている資料のチェックリスト（config/data_requirements.yaml）。"""
    data = _load_yaml(CONFIG_DIR / "data_requirements.yaml", {})
    return data.get("requirements", [])
