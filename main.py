import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from coo import analyst, intake, store
from coo.config import CATEGORIES

load_dotenv()

client = anthropic.Anthropic()

SYSTEM_PROMPTS = {
    "chat": (
        "あなたは「AI参謀」です。中小企業の経営者を支援する優秀な経営コンサルタントとして振る舞ってください。\n"
        "以下のルールに従ってください：\n"
        "- 経営課題に対して、具体的かつ実行可能なアドバイスを提供する\n"
        "- 専門用語を使う場合は分かりやすく説明を添える\n"
        "- 質問を通じて経営者の状況を深く理解してからアドバイスする\n"
        "- 回答は構造的に整理し、箇条書きや見出しを活用する\n"
        "- 日本のビジネス環境・商慣習を考慮する\n"
        "- 必要に応じてフレームワーク（3C分析、5Forces等）を活用する"
    ),
    "financial": (
        "あなたは「AI参謀」の財務アドバイザーモードです。\n"
        "以下のルールに従ってください：\n"
        "- 売上・コスト・利益率などの数値を基にした分析を行う\n"
        "- 資金繰り、キャッシュフロー改善のアドバイスを提供する\n"
        "- 損益分岐点や投資回収期間などの計算を支援する\n"
        "- 財務指標の読み方を分かりやすく説明する\n"
        "- 具体的な数字が提示された場合は計算結果を示す\n"
        "- 日本の税制・会計基準を考慮する\n"
        "- まず経営者に必要な数値情報を質問してから分析する"
    ),
    "plan": (
        "あなたは「AI参謀」の事業計画作成モードです。\n"
        "以下のルールに従ってください：\n"
        "- 事業計画書の各セクションを段階的に作成する\n"
        "  （事業概要、市場分析、競合分析、マーケティング戦略、収支計画、リスク分析）\n"
        "- まず事業の概要や目的をヒアリングしてから計画を作成する\n"
        "- 実現可能性を重視した現実的な計画を提案する\n"
        "- 日本政策金融公庫などの融資申請にも使える形式を意識する\n"
        "- 数値目標は根拠とともに提示する\n"
        "- 必要に応じてSWOT分析を組み込む"
    ),
}


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        return f.read()


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    mode = body.get("mode", "chat")
    messages = body.get("messages", [])

    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["chat"])

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=16000,
        system=system_prompt,
        messages=messages,
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    return {"role": "assistant", "content": text}


# --- 経営ダッシュボード（クロ = COO → CEO への報告） ------------------------


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    with open("static/dashboard.html") as f:
        return f.read()


@app.get("/api/dashboard/latest")
async def dashboard_latest():
    report = store.latest_report()
    if report is None:
        raise HTTPException(status_code=404, detail="レポートがまだありません")
    return report


@app.get("/api/dashboard/reports")
async def dashboard_reports():
    return {"reports": store.list_reports()}


@app.get("/api/dashboard/reports/{report_id}")
async def dashboard_report(report_id: str):
    report = store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="該当するレポートがありません")
    return report


@app.get("/api/dashboard/inbox")
async def dashboard_inbox():
    """提供済みの資料と、クロがまだ待っている資料の一覧。"""
    return intake.inbox_summary()


@app.post("/api/dashboard/generate")
async def dashboard_generate(request: Request):
    """data/inbox の資料を読み、新しいレポートを生成して保存する。"""
    body = await request.json() if await request.body() else {}
    focus = (body or {}).get("focus", "")
    try:
        report = analyst.generate_report(focus=focus, client=client)
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API エラー: {exc.message}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"レポートの解析に失敗しました: {exc}") from exc
    report_id = store.save_report(report)
    return store.get_report(report_id)


@app.post("/api/dashboard/decisions/{decision_id}")
async def dashboard_decide(decision_id: str, request: Request):
    """CEOの決裁（承認 / 却下 / 保留）を記録する。"""
    body = await request.json()
    report_id = body.get("report_id")
    status = body.get("status", "")
    if not report_id:
        raise HTTPException(status_code=400, detail="report_id が必要です")
    try:
        entry = store.record_decision(report_id, decision_id, status, body.get("note", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry


@app.get("/api/dashboard/decisions")
async def dashboard_decision_history():
    return {"history": store.decision_history(), "categories": CATEGORIES}
