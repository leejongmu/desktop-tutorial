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

### 웹 앱 (아이패드 / 브라우저)

```bash
export ANTHROPIC_API_KEY=your_api_key_here
uvicorn app:app --host 0.0.0.0 --port 8000
```

브라우저 또는 아이패드 Safari에서 `http://서버IP:8000` 접속

### CLI (터미널)

```bash
export ANTHROPIC_API_KEY=your_api_key_here
python research_bot.py
```

### GitHub Pages (서버 없이 아이패드에서 바로 사용)

1. GitHub 저장소 → **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / Folder: `/web` 선택 → Save
4. 몇 분 후 생성된 URL을 iPad Safari에서 접속
5. 처음 실행 시 Anthropic API 키 입력 (기기에만 저장됨)

> API 키: [console.anthropic.com](https://console.anthropic.com) → API Keys

## 파일 구성

```
web/index.html         # 순수 브라우저 앱 (서버 불필요, GitHub Pages 배포용)
app.py                 # FastAPI 웹 서버 (로컬 실행용, SSE 스트리밍)
research_bot.py        # CLI 챗 인터페이스
tools.py               # Python 도구 구현체 (Semantic Scholar, arXiv, CrossRef)
templates/index.html   # FastAPI 서버용 채팅 UI
requirements.txt       # Python 의존성
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
