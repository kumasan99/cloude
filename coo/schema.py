"""COOレポートの構造定義。

Claude には JSON Schema による構造化出力（output_config.format）で
この形を守らせる。判断ステータス（承認/却下/保留）はモデルではなく
アプリ側が持つため、スキーマには含めず生成後に付与する。
"""

def _obj(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }


def _arr(item: dict) -> dict:
    return {"type": "array", "items": item}


_STR = {"type": "string"}


REPORT_SCHEMA = _obj(
    {
        "report_date": {**_STR, "description": "レポート基準日 YYYY-MM-DD"},
        "period_label": {**_STR, "description": "対象期間の表示名（例: 2026年8月 第3週）"},
        "headline": {**_STR, "description": "CEOがこの1行だけ読めば状況が分かる要約（80字以内）"},
        "overall_status": {
            "type": "string",
            "enum": ["green", "yellow", "red"],
            "description": "全体の健全性",
        },
        "status_reason": {**_STR, "description": "その色にした根拠を2〜3文で"},
        "kpis": _arr(
            _obj(
                {
                    "id": _STR,
                    "label": {**_STR, "description": "KPI名"},
                    "value": {**_STR, "description": "実績値。単位込みの文字列。不明なら「不明」"},
                    "unit": _STR,
                    "target": {**_STR, "description": "目標値。未設定なら「未設定」"},
                    "status": {"type": "string", "enum": ["good", "watch", "bad", "unknown"]},
                    "trend": {"type": "string", "enum": ["up", "down", "flat", "unknown"]},
                    "comment": {**_STR, "description": "経営者向けの一言解釈"},
                    "source": {**_STR, "description": "根拠にしたファイル名。推測なら「推定」"},
                }
            )
        ),
        "decisions": _arr(
            _obj(
                {
                    "id": _STR,
                    "title": {**_STR, "description": "CEOに判断してほしいこと"},
                    "context": {**_STR, "description": "なぜ今この判断が必要か"},
                    "options": _arr(
                        _obj({"label": _STR, "pros": _STR, "cons": _STR})
                    ),
                    "recommendation": {**_STR, "description": "COOとしての推奨と理由"},
                    "impact": {**_STR, "description": "金額・時間・人への影響"},
                    "deadline": {**_STR, "description": "いつまでに判断が必要か"},
                    "urgency": {"type": "string", "enum": ["high", "medium", "low"]},
                    "required_from_ceo": {**_STR, "description": "CEOに具体的に何をしてほしいか（決裁・面談・承認など）"},
                }
            )
        ),
        "improvements": _arr(
            _obj(
                {
                    "id": _STR,
                    "title": _STR,
                    "problem": {**_STR, "description": "観測された課題と、そう判断した根拠"},
                    "action": {**_STR, "description": "具体的な打ち手"},
                    "expected_effect": {**_STR, "description": "期待効果（できれば定量）"},
                    "effort": {"type": "string", "enum": ["small", "medium", "large"]},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "owner": {**_STR, "description": "誰がやるべきか（役割名）"},
                    "first_step": {**_STR, "description": "明日から始められる最初の一歩"},
                }
            )
        ),
        "risks": _arr(
            _obj(
                {
                    "id": _STR,
                    "title": _STR,
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "detail": _STR,
                    "mitigation": {**_STR, "description": "打てる手"},
                }
            )
        ),
        "data_gaps": _arr(
            _obj(
                {
                    "id": _STR,
                    "title": {**_STR, "description": "次にCEOに出してほしい資料"},
                    "why": {**_STR, "description": "それが無いと何が判断できないか"},
                    "how_to_provide": {**_STR, "description": "どの形式で data/inbox のどこに置けばよいか"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                }
            )
        ),
        "notes_for_ceo": {**_STR, "description": "前提・推測した点・読み取れなかった点の断り書き"},
    }
)


def empty_report(report_date: str) -> dict:
    """資料が1つも無いときのプレースホルダ。"""
    return {
        "report_date": report_date,
        "period_label": "データ未提供",
        "headline": "まだ資料が届いていないため、判断材料を作れていません。",
        "overall_status": "yellow",
        "status_reason": "data/inbox に資料が置かれていないため、実績にもとづく評価ができません。",
        "kpis": [],
        "decisions": [],
        "improvements": [],
        "risks": [],
        "data_gaps": [],
        "notes_for_ceo": "docs/DATA_INTAKE.md の優先度Aの資料からご提供ください。",
    }
