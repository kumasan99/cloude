import os
from contextlib import asynccontextmanager

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

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
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )

    return {
        "role": "assistant",
        "content": response.content[0].text,
    }
