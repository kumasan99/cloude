"""クロ（COO）としてのレポート生成。"""

import json
from datetime import date

import anthropic

from .config import COO_MODEL, company_profile, kpi_definitions
from .intake import documents_as_prompt, load_documents, requirement_status
from .schema import REPORT_SCHEMA, empty_report

SYSTEM_PROMPT = """あなたは「クロ」、この会社のCOO（最高執行責任者）です。
報告相手はCEO（社長）ひとりです。社内に散在する資料を読み込み、CEOが
「読むだけで意思決定できる」状態に整理して報告するのがあなたの仕事です。

守るべき原則：
1. 事実と推測を必ず分ける。資料から読み取れた数字には出典ファイル名を書き、
   推測・補完した数字には「推定」と明記する。数字をでっち上げない。
2. 資料が足りずに判断できないことは、隠さず data_gaps に書く。
   「何が無いせいで、どの判断ができないのか」まで書く。
3. decisions（要判断事項）はCEOにしか決められないものだけを挙げる。
   現場で決められることは improvements に回す。
4. decisions には必ず選択肢と、COOとしての推奨を添える。
   「どうしますか？」ではなく「私はAを推奨します。理由は〜」と言い切る。
5. improvements は「明日から始められる最初の一歩」まで具体化する。
6. 中小企業の現実（人手・資金・時間が限られる）を前提に、
   実行不可能な理想論を書かない。
7. 日本語で、経営者が3分で読める密度にする。専門用語には短い補足をつける。
8. 資料が少ないときは、無理に項目を埋めず、少数の確かな指摘に絞る。"""


def _context_block() -> str:
    profile = company_profile()
    kpis = kpi_definitions()
    parts = []
    if profile:
        parts.append("## 会社の前提\n```yaml\n" + json.dumps(profile, ensure_ascii=False, indent=2) + "\n```")
    if kpis:
        parts.append("## CEOが見たいKPIの定義\n```json\n" + json.dumps(kpis, ensure_ascii=False, indent=2) + "\n```")
    return "\n\n".join(parts) if parts else "（会社の前提情報は未設定です）"


def _requirements_block() -> str:
    reqs = requirement_status()
    if not reqs:
        return ""
    missing = [r for r in reqs if not r["satisfied"]]
    if not missing:
        return "## 資料チェックリスト\nチェックリスト上の資料はすべて提供済みです。"
    lines = [f"- {r['title']}（優先度: {r['priority']}） — {r['why']}" for r in missing]
    return "## まだ提供されていない資料（チェックリスト）\n" + "\n".join(lines)


def build_user_prompt(documents: list[dict], today: str, focus: str = "") -> str:
    sections = [
        f"本日は {today} です。この日付を report_date にしてください。",
        _context_block(),
        _requirements_block(),
        "## 提供された社内資料\n" + documents_as_prompt(documents),
    ]
    if focus:
        sections.append(f"## CEOからの今回の指定\n{focus}")
    sections.append(
        "上記をもとに、CEO向けの経営レポートを作成してください。\n"
        "特に decisions（CEOの判断が必要なもの）と data_gaps（次に出してほしい資料）は、\n"
        "CEOがそのまま行動できる粒度まで具体的に書いてください。"
    )
    return "\n\n".join(s for s in sections if s)


def generate_report(focus: str = "", client: anthropic.Anthropic | None = None) -> dict:
    """inbox の資料を読み、COOレポート(dict)を返す。"""
    today = date.today().isoformat()
    documents = load_documents()
    readable = [d for d in documents if d["status"] == "ok" and d["text"].strip()]

    if not readable and not focus:
        report = empty_report(today)
        report["data_gaps"] = [
            {
                "id": f"gap-{r['id']}",
                "title": r["title"],
                "why": r["why"],
                "how_to_provide": f"{r['format']}　→　data/inbox/{r['category']}/ に配置",
                "priority": r["priority"],
            }
            for r in requirement_status()
            if not r["satisfied"]
        ]
        report["_meta"] = {"source_files": [], "model": None, "generated_from": "empty"}
        return report

    client = client or anthropic.Anthropic()

    with client.messages.stream(
        model=COO_MODEL,
        max_tokens=32000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": REPORT_SCHEMA},
        },
        messages=[{"role": "user", "content": build_user_prompt(documents, today, focus)}],
    ) as stream:
        message = stream.get_final_message()

    text = next((b.text for b in message.content if b.type == "text"), "")
    report = json.loads(text)
    report["_meta"] = {
        "model": message.model,
        "generated_from": "documents",
        "source_files": [d["path"] for d in readable],
        "unreadable_files": [d["path"] for d in documents if d["status"] != "ok"],
        "focus": focus,
        "usage": {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        },
    }
    return report
