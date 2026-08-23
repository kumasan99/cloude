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
    "kodama": (
        "あなたは「AI参謀」の音声記録部「コダマ」です。\n"
        "経営者が音声で吹き込んだ内容（会議、商談、アイデアメモ、日報など）を、整理された記録に変換します。\n"
        "以下のルールに従ってください：\n"
        "- 話し言葉の文字起こしから、フィラー（えー、あのー等）や言い直し・重複を取り除いて要点を整理する\n"
        "- 会議・商談の内容は議事録形式に整理する（日時・参加者・議題・討議内容・決定事項・TODO）\n"
        "- 決定事項とアクションアイテムは、担当者と期限が分かる形で明確に抽出する\n"
        "- アイデアメモや日報は見出し付きで構造化し、必要に応じて深掘りの質問を添える\n"
        "- 元の発言の意図・事実関係を変えない。要約で情報を落としすぎない\n"
        "- 聞き取りが不明瞭・情報が不足している箇所は推測で補わず【要確認】と明記する\n"
        "- 日時・参加者などが不明な場合は、記録の冒頭で確認事項として挙げる"
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
