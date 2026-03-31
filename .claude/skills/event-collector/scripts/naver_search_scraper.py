#!/usr/bin/env python3
"""네이버 검색 Open API로 포켓몬 카드쇼/팝업/프로모 이벤트 수집."""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("필요 패키지: pip install requests")
    sys.exit(1)

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))

BLOG_API = "https://openapi.naver.com/v1/search/blog.json"
NEWS_API = "https://openapi.naver.com/v1/search/news.json"


def strip_html(text: str) -> str:
    """HTML 태그 제거."""
    return re.sub(r"<[^>]+>", "", text).strip()


def normalize_date(raw: str, search_type: str) -> str:
    """날짜 문자열을 ISO 형식(YYYY-MM-DD)으로 정규화."""
    if not raw:
        return ""
    try:
        if search_type == "blog":
            # YYYYMMDD 형식
            if re.match(r"^\d{8}$", raw):
                return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        elif search_type == "news":
            # RFC 822: "Mon, 31 Mar 2026 14:30:00 +0900"
            dt = parsedate_to_datetime(raw)
            return dt.astimezone(KST).date().isoformat()
    except Exception:
        pass
    return ""


def search_naver(api_url: str, query: str, client_id: str, client_secret: str,
                 search_type: str, display: int = 10) -> list:
    """네이버 검색 API 호출."""
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": query, "sort": "date", "display": display}

    try:
        resp = requests.get(api_url, headers=headers, params=params, timeout=10)
        if resp.status_code == 401:
            print(f"  [AUTH ERROR] 네이버 API 인증 실패 — NAVER_CLIENT_ID/SECRET 확인")
            return []
        if resp.status_code != 200:
            print(f"  [WARN] 네이버 API HTTP {resp.status_code} (query={query!r})")
            return []

        items = []
        for item in resp.json().get("items", []):
            title = strip_html(item.get("title", ""))
            description = strip_html(item.get("description", ""))
            link = item.get("link", "") or item.get("originallink", "")

            raw_date = item.get("postdate", "") if search_type == "blog" else item.get("pubDate", "")
            date_iso = normalize_date(raw_date, search_type)

            if not title or not link:
                continue

            items.append({
                "title": title,
                "link": link,
                "description": description,
                "date": date_iso,
                "search_type": search_type,
                "keyword": query,
            })
        return items

    except requests.RequestException as e:
        print(f"  [ERROR] 네이버 API 호출 실패 (query={query!r}): {e}")
        return []


def main():
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("[naver_search] NAVER_CLIENT_ID/SECRET 미설정, 스킵")
        sys.exit(0)

    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["event_sources"].get("naver_search", {}).get("enabled", True):
        print("[naver_search] 비활성화, 스킵")
        sys.exit(0)

    keywords = sources["event_sources"].get("naver_search", {}).get("keywords", [
        "포켓몬 카드쇼 2026",
        "포켓몬 팝업 2026",
        "포켓몬 굿즈 이벤트 2026",
        "포켓몬 프로모 카드 2026",
        "포켓몬센터 이벤트 2026",
    ])

    print(f"[naver_search] 수집 시작 ({len(keywords)}개 키워드 × 블로그/뉴스)")

    all_items = []
    seen_links = set()

    for keyword in keywords:
        for api_url, search_type in [(BLOG_API, "blog"), (NEWS_API, "news")]:
            time.sleep(0.3)  # API rate limit 준수 (4 req/min)
            items = search_naver(api_url, keyword, client_id, client_secret, search_type)
            for item in items:
                if item["link"] not in seen_links:
                    seen_links.add(item["link"])
                    all_items.append(item)

    print(f"[naver_search] {len(all_items)}개 항목 수집 (중복 제거 후)")

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "naver_search",
        "items": all_items,
    }

    out = ROOT / "data/raw/events_naver_search.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[naver_search] 완료 → {out}")


if __name__ == "__main__":
    main()
