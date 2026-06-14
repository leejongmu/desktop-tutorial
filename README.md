# 논문작성 서포팅 봇 (Paper Research Support Bot)

Claude API 기반의 학술 논문 작성 지원 에이전트입니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| 학술 논문 검색 | Semantic Scholar, arXiv API를 통한 관련 논문 탐색 |
| 인용 검증 | CrossRef API로 DOI 기반 서지 정보 검증 및 APA 형식 인용 생성 |
| 내용 요약 | 논문 핵심 기여·방법론·결과 요약 |
| 초안 작성 지원 | 서론·방법론·결과·결론 등 섹션별 학술 문체 초안 작성 |

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

```bash
export ANTHROPIC_API_KEY=your_api_key_here
python research_bot.py
```

## 파일 구성

```
research_bot.py   # 메인 CLI 챗 인터페이스 (Claude API 에이전틱 루프)
tools.py          # 도구 구현체 (Semantic Scholar, arXiv, CrossRef API)
requirements.txt  # Python 의존성
```

## 사용 예시

```
사용자: transformer 모델의 attention mechanism 관련 논문 찾아줘
사용자: DOI 10.48550/arXiv.1706.03762 인용 정보 검증해줘
사용자: 딥러닝 기반 자연어처리 서론 초안 작성 도와줘
```

## 기술 스택

- **LLM**: Claude Opus 4.8 with adaptive thinking
- **패턴**: Manual agentic loop with streaming
- **학술 API**: Semantic Scholar · arXiv · CrossRef (모두 무료, API 키 불필요)
