#!/usr/bin/env python3
"""Paper research support bot powered by Claude API with tool use."""

import json
import os
import sys

import anthropic

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


def execute_tool(name: str, tool_input: dict) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return json.dumps({"error": f"알 수 없는 도구: {name}", "is_error": True})
    try:
        return func(**tool_input)
    except TypeError as e:
        return json.dumps({"error": f"도구 호출 오류: {str(e)}", "is_error": True})


def stream_and_collect(client: anthropic.Anthropic, messages: list) -> anthropic.types.Message:
    """Stream response to stdout and return the final message."""
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOL_DEFINITIONS,
        thinking={"type": "adaptive"},
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        return stream.get_final_message()


def run_agentic_loop(client: anthropic.Anthropic, messages: list) -> str:
    """Run the agentic loop until Claude stops calling tools, return final text."""
    final_text = ""

    while True:
        response = stream_and_collect(client, messages)

        if response.stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            final_text = "\n".join(text_blocks)
            break

        # Tool use: execute each tool and feed results back
        if response.stop_reason == "tool_use":
            print()  # newline after streamed text
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n[도구 호출: {block.name}({json.dumps(block.input, ensure_ascii=False)})]")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
                    # Show a brief preview of the result
                    try:
                        parsed = json.loads(result)
                        if "error" in parsed:
                            print(f"[오류: {parsed['error']}]")
                        elif "results" in parsed:
                            count = len(parsed["results"])
                            print(f"[{count}개 결과 반환됨]")
                        else:
                            print("[결과 수신 완료]")
                    except Exception:
                        print("[결과 수신 완료]")

            messages.append({"role": "user", "content": tool_results})
            print("\n[분석 중...]\n")
            continue

        # pause_turn: hit iteration limit, continue
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        # Unexpected stop reason — break to avoid infinite loop
        break

    return final_text


def print_welcome():
    print("=" * 60)
    print("  논문작성 서포팅 봇 (Paper Research Support Bot)")
    print("=" * 60)
    print("기능: 학술 논문 검색 | 인용 검증 | 내용 요약 | 초안 작성")
    print("종료: 'quit', 'exit', 또는 Ctrl+C")
    print("=" * 60)
    print()


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("오류: ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("export ANTHROPIC_API_KEY=your_api_key_here")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    conversation_messages: list = []

    print_welcome()

    while True:
        try:
            user_input = input("사용자: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n봇을 종료합니다. 좋은 논문 쓰세요!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "종료", "q"):
            print("봇을 종료합니다. 좋은 논문 쓰세요!")
            break

        conversation_messages.append({"role": "user", "content": user_input})

        print("\n봇: ", end="", flush=True)
        try:
            run_agentic_loop(client, conversation_messages)
            print("\n")

            # Keep only the last assistant message to avoid re-adding tool results
            # Find the last complete exchange and update conversation history
            # (The messages list already has the full history from run_agentic_loop)
        except anthropic.APIConnectionError:
            print("\n[오류: API 연결 실패. 네트워크를 확인해주세요.]")
            conversation_messages.pop()  # remove the user message we just added
        except anthropic.RateLimitError:
            print("\n[오류: API 요청 한도 초과. 잠시 후 다시 시도해주세요.]")
            conversation_messages.pop()
        except anthropic.APIStatusError as e:
            print(f"\n[API 오류: {e.status_code} - {e.message}]")
            conversation_messages.pop()


if __name__ == "__main__":
    main()
