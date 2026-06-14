#!/usr/bin/env python3
"""FastAPI web server for the paper research support bot.

Run:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import os
from typing import AsyncGenerator

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

MODEL = "claude-opus-4-8"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """당신은 논문 작성을 돕는 전문 학술 연구 어시스턴트입니다.

## 주요 기능
- **학술 논문 검색**: Semantic Scholar 및 arXiv API를 활용하여 관련 논문을 검색합니다
- **인용 검증**: CrossRef API로 DOI를 통해 논문의 실재 여부와 정확한 서지 정보를 확인합니다
- **내용 요약**: 논문의 핵심 내용을 명확하고 간결하게 요약합니다
- **초안 작성 지원**: 논문 섹션(서론, 방법론, 결과, 결론 등) 작성을 도와드립니다

## 행동 지침
1. 사용자의 연구 주제를 파악하고 관련성 높은 논문을 적극적으로 검색하세요
2. 인용할 논문이 있다면 반드시 DOI를 통해 검증 후 정확한 서지 정보를 제공하세요
3. 논문 요약 시 핵심 기여(contribution), 방법론, 주요 결과를 포함하세요
4. 초안 작성 시 학술적 문체와 논리적 흐름을 유지하세요
5. 한국어로 소통하되, 학술 용어는 영어 원어와 병기하세요

## 응답 형식
- 검색 결과는 번호를 붙여 목록으로 정리하세요
- 논문 정보는 저자, 연도, 제목, 저널/학회 순으로 표시하세요
- 인용 검증 결과는 APA 형식으로 제공하세요
"""

app = FastAPI(title="논문 서포팅 봇")

async_client = anthropic.AsyncAnthropic()

# session_id → full conversation message list (includes tool use/result blocks)
sessions: dict[str, list] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


def _sse(event_type: str, **kwargs) -> str:
    payload = json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def agentic_stream(session_id: str, user_message: str) -> AsyncGenerator[str, None]:
    if session_id not in sessions:
        sessions[session_id] = []

    sessions[session_id].append({"role": "user", "content": user_message})

    while True:
        try:
            async with async_client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                thinking={"type": "adaptive"},
                messages=sessions[session_id],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    yield _sse("text", content=text_chunk)
                final_msg = await stream.get_final_message()

        except anthropic.APIConnectionError as e:
            yield _sse("error", message=f"API 연결 실패: {str(e)}")
            sessions[session_id].pop()  # remove the user message
            return
        except anthropic.APIStatusError as e:
            yield _sse("error", message=f"API 오류 {e.status_code}: {e.message}")
            sessions[session_id].pop()
            return

        stop_reason = final_msg.stop_reason
        full_content = final_msg.content

        if stop_reason == "end_turn":
            sessions[session_id].append({"role": "assistant", "content": full_content})
            yield _sse("done")
            return

        if stop_reason == "tool_use":
            sessions[session_id].append({"role": "assistant", "content": full_content})

            tool_results = []
            for block in full_content:
                if block.type != "tool_use":
                    continue

                input_dict = dict(block.input) if block.input else {}
                yield _sse("tool_start", name=block.name, args=input_dict)

                func = TOOL_FUNCTIONS.get(block.name)
                if func:
                    try:
                        result = await asyncio.to_thread(func, **input_dict)
                        yield _sse("tool_end", name=block.name, status="ok")
                    except Exception as e:
                        result = json.dumps({"error": str(e), "is_error": True})
                        yield _sse("tool_end", name=block.name, status="error")
                else:
                    result = json.dumps({"error": f"알 수 없는 도구: {block.name}"})
                    yield _sse("tool_end", name=block.name, status="error")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            sessions[session_id].append({"role": "user", "content": tool_results})
            yield _sse("thinking")
            continue

        if stop_reason == "pause_turn":
            sessions[session_id].append({"role": "assistant", "content": full_content})
            continue

        yield _sse("done")
        return


@app.get("/")
async def index():
    return FileResponse("templates/index.html")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="메시지를 입력하세요")

    return StreamingResponse(
        agentic_stream(request.session_id, request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    sessions.pop(session_id, None)
    return {"status": "cleared"}
