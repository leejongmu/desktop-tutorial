"""Tool implementations for the paper research support bot."""

import json
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import httpx

_HTTP_TIMEOUT = 15.0


def search_papers(query: str, max_results: int = 10) -> str:
    """Search for academic papers using Semantic Scholar API.

    Args:
        query: Search query string (keywords, title, author, etc.)
        max_results: Maximum number of results to return (1-20)
    """
    max_results = min(max(1, max_results), 20)
    fields = "title,abstract,authors,year,citationCount,externalIds,openAccessPdf,url"
    params = {"query": query, "limit": max_results, "fields": fields}
    url = "https://api.semanticscholar.org/graph/v1/paper/search"

    try:
        response = httpx.get(url, params=params, timeout=_HTTP_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        papers = data.get("data", [])
        if not papers:
            return json.dumps({"results": [], "message": "검색 결과가 없습니다."})

        results = []
        for p in papers:
            authors = [a.get("name", "") for a in (p.get("authors") or [])]
            doi = (p.get("externalIds") or {}).get("DOI", "")
            pdf_url = (p.get("openAccessPdf") or {}).get("url", "")
            results.append({
                "title": p.get("title", ""),
                "authors": authors,
                "year": p.get("year"),
                "citation_count": p.get("citationCount"),
                "abstract": (p.get("abstract") or "")[:500],
                "doi": doi,
                "open_access_pdf": pdf_url,
                "semantic_scholar_url": p.get("url", ""),
            })
        return json.dumps({"results": results, "total_found": data.get("total", len(results))}, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"API 오류: {e.response.status_code}", "is_error": True})
    except Exception as e:
        return json.dumps({"error": f"검색 중 오류 발생: {str(e)}", "is_error": True})


def search_arxiv(query: str, max_results: int = 10) -> str:
    """Search for preprint papers on arXiv.

    Args:
        query: Search query (supports arXiv search syntax)
        max_results: Maximum number of results to return (1-20)
    """
    max_results = min(max(1, max_results), 20)
    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)

    try:
        response = httpx.get(url, timeout=_HTTP_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        entries = root.findall("atom:entry", ns)
        if not entries:
            return json.dumps({"results": [], "message": "arXiv에서 검색 결과가 없습니다."})

        results = []
        for entry in entries:
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            abstract = (entry.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")[:500]
            published = entry.findtext("atom:published", "", ns)
            year = published[:4] if published else None
            authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
            arxiv_id_raw = entry.findtext("atom:id", "", ns)
            arxiv_id = arxiv_id_raw.split("/abs/")[-1] if arxiv_id_raw else ""
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else ""
            results.append({
                "title": title,
                "authors": authors,
                "year": year,
                "arxiv_id": arxiv_id,
                "abstract": abstract,
                "arxiv_url": arxiv_id_raw,
                "pdf_url": pdf_url,
            })
        return json.dumps({"results": results}, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"arXiv API 오류: {e.response.status_code}", "is_error": True})
    except Exception as e:
        return json.dumps({"error": f"arXiv 검색 중 오류 발생: {str(e)}", "is_error": True})


def verify_citation(doi: str) -> str:
    """Verify a citation and retrieve metadata using CrossRef API.

    Args:
        doi: The DOI (Digital Object Identifier) of the paper, e.g. '10.1038/nature12345'
    """
    doi_clean = doi.strip().lstrip("https://doi.org/").lstrip("http://doi.org/").lstrip("doi:")
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi_clean, safe='/')}"

    try:
        headers = {"User-Agent": "PaperResearchBot/1.0 (mailto:bot@example.com)"}
        response = httpx.get(url, headers=headers, timeout=_HTTP_TIMEOUT)
        if response.status_code == 404:
            return json.dumps({"valid": False, "message": f"DOI를 찾을 수 없습니다: {doi_clean}"})
        response.raise_for_status()
        data = response.json().get("message", {})

        authors = []
        for a in data.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            authors.append(f"{given} {family}".strip())

        issued = data.get("issued", {}).get("date-parts", [[]])[0]
        year = issued[0] if issued else None

        container = (data.get("container-title") or [""])[0]
        citation = _format_citation(data, authors, year, container)

        return json.dumps({
            "valid": True,
            "doi": doi_clean,
            "title": (data.get("title") or [""])[0],
            "authors": authors,
            "year": year,
            "journal": container,
            "volume": data.get("volume"),
            "issue": data.get("issue"),
            "pages": data.get("page"),
            "publisher": data.get("publisher"),
            "type": data.get("type"),
            "url": data.get("URL"),
            "formatted_citation": citation,
        }, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"CrossRef API 오류: {e.response.status_code}", "is_error": True})
    except Exception as e:
        return json.dumps({"error": f"인용 검증 중 오류 발생: {str(e)}", "is_error": True})


def _format_citation(data: dict, authors: list, year: Any, journal: str) -> str:
    author_str = ", ".join(authors[:6])
    if len(authors) > 6:
        author_str += " et al."
    title = (data.get("title") or [""])[0]
    doi = data.get("DOI", "")
    volume = data.get("volume", "")
    issue = data.get("issue", "")
    pages = data.get("page", "")

    parts = [f"{author_str} ({year})." if year else f"{author_str}."]
    parts.append(f'"{title}".')
    if journal:
        journal_part = journal
        if volume:
            journal_part += f" {volume}"
        if issue:
            journal_part += f"({issue})"
        if pages:
            journal_part += f": {pages}"
        parts.append(journal_part + ".")
    if doi:
        parts.append(f"https://doi.org/{doi}")
    return " ".join(parts)


def get_paper_details(paper_id: str) -> str:
    """Retrieve detailed information about a specific paper from Semantic Scholar.

    Args:
        paper_id: Semantic Scholar paper ID, DOI (prefix with 'DOI:'), or arXiv ID (prefix with 'ARXIV:')
                  Examples: '649def34f8be52c8b66281af98ae884c09aef38b', 'DOI:10.18653/v1/N18-3011', 'ARXIV:2301.07041'
    """
    fields = "title,abstract,authors,year,citationCount,referenceCount,citations,references,externalIds,openAccessPdf,url,venue,publicationDate,tldr"
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"

    try:
        response = httpx.get(url, params={"fields": fields}, timeout=_HTTP_TIMEOUT)
        if response.status_code == 404:
            return json.dumps({"error": f"논문을 찾을 수 없습니다: {paper_id}", "is_error": True})
        response.raise_for_status()
        p = response.json()

        authors = [a.get("name", "") for a in (p.get("authors") or [])]
        doi = (p.get("externalIds") or {}).get("DOI", "")
        pdf_url = (p.get("openAccessPdf") or {}).get("url", "")
        tldr = (p.get("tldr") or {}).get("text", "")

        top_citations = []
        for c in (p.get("citations") or [])[:5]:
            top_citations.append({"title": c.get("title", ""), "year": c.get("year")})

        top_references = []
        for r in (p.get("references") or [])[:10]:
            top_references.append({"title": r.get("title", ""), "year": r.get("year")})

        return json.dumps({
            "title": p.get("title", ""),
            "authors": authors,
            "year": p.get("year"),
            "venue": p.get("venue", ""),
            "publication_date": p.get("publicationDate"),
            "citation_count": p.get("citationCount"),
            "reference_count": p.get("referenceCount"),
            "abstract": p.get("abstract", ""),
            "tldr": tldr,
            "doi": doi,
            "open_access_pdf": pdf_url,
            "semantic_scholar_url": p.get("url", ""),
            "top_citations": top_citations,
            "key_references": top_references,
        }, ensure_ascii=False)

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"API 오류: {e.response.status_code}", "is_error": True})
    except Exception as e:
        return json.dumps({"error": f"논문 정보 조회 중 오류 발생: {str(e)}", "is_error": True})


TOOL_DEFINITIONS = [
    {
        "name": "search_papers",
        "description": (
            "Semantic Scholar API를 사용하여 학술 논문을 검색합니다. "
            "키워드, 저자, 주제 등으로 검색할 수 있으며 제목, 초록, 인용 수, DOI 등의 정보를 반환합니다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 쿼리 (키워드, 저자명, 논문 제목 등)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "반환할 최대 결과 수 (기본값 10, 최대 20)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_arxiv",
        "description": (
            "arXiv에서 프리프린트 논문을 검색합니다. "
            "컴퓨터 과학, 물리학, 수학, 통계학 등 분야의 최신 연구를 찾는 데 유용합니다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 쿼리",
                },
                "max_results": {
                    "type": "integer",
                    "description": "반환할 최대 결과 수 (기본값 10, 최대 20)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_citation",
        "description": (
            "CrossRef API를 사용하여 DOI로 인용 정보를 검증합니다. "
            "논문의 실제 존재 여부를 확인하고 정확한 서지 정보(저자, 출판연도, 저널명, 권호 등)를 가져옵니다. "
            "APA 형식의 인용 문자열도 생성합니다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "doi": {
                    "type": "string",
                    "description": "논문의 DOI (예: '10.1038/nature12345' 또는 'https://doi.org/10.1038/nature12345')",
                },
            },
            "required": ["doi"],
        },
    },
    {
        "name": "get_paper_details",
        "description": (
            "Semantic Scholar에서 특정 논문의 상세 정보를 가져옵니다. "
            "전체 초록, 인용 논문 목록, 참고 문헌, TL;DR 요약 등을 포함합니다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": (
                        "논문 식별자. Semantic Scholar ID, DOI (앞에 'DOI:' 붙임), "
                        "arXiv ID (앞에 'ARXIV:' 붙임) 형식 지원. "
                        "예: 'DOI:10.18653/v1/N18-3011', 'ARXIV:2301.07041'"
                    ),
                },
            },
            "required": ["paper_id"],
        },
    },
]

TOOL_FUNCTIONS = {
    "search_papers": search_papers,
    "search_arxiv": search_arxiv,
    "verify_citation": verify_citation,
    "get_paper_details": get_paper_details,
}
