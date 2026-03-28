#!/usr/bin/env python3
"""
네이버 카페 공개 게시판에서 이벤트/행사 게시글 수집.
구글시트 폴백 지원 (GOOGLE_SHEET_ID 환경변수 필요).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("필요 패키지: pip install requests beautifulsoup4")
    sys.exit(1)

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://cafe.naver.com",
}


def is_login_redirect(resp) -> bool:
    return "login.naver.com" in resp.url or "nidlogin" in resp.text


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text[:40]


def search_cafe_events(cafe_id: str, keyword: str) -> list:
    """네이버 카페에서 이벤트 관련 게시글 검색."""
    url = "https://cafe.naver.com/ArticleSearchList.nhn"
    params = {
        "query": keyword,
        "search.clubid": cafe_id,
        "search.searchBy": "0",
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10, allow_redirects=True)
        if is_login_redirect(resp):
            print(f"  [SKIP] 카페 {cafe_id}: 로그인 필요 게시글")
            return []
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        today_str = datetime.now(KST).strftime("%Y%m%d")

        for item in soup.select(".article-item, .list-item, .article")[:10]:
            title_el = item.select_one(".article-title, .item-title, a[href*='ArticleRead']")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if not link or ("ArticleRead" not in link and "cafearticle" not in link):
                continue

            full_url = f"https://cafe.naver.com{link}" if link.startswith("/") else link
            event_id = f"evt-{today_str}-{slugify(title)}"

            articles.append({
                "id": event_id,
                "title": title,
                "url": full_url,
                "source": f"naver_cafe_{cafe_id}",
                "keyword": keyword,
                "scraped_at": datetime.now(KST).isoformat(),
            })
        return articles

    except requests.RequestException as e:
        print(f"  [ERROR] 카페 이벤트 검색 실패: {e}")
        return []


def fetch_google_sheet_events(sheet_id: str) -> list:
    """구글시트 공개 CSV 폴백 수집."""
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        resp = requests.get(csv_url, timeout=15)
        if resp.status_code != 200:
            return []
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return []

        header = [h.strip().strip('"') for h in lines[0].split(",")]
        events = []
        today_str = datetime.now(KST).strftime("%Y%m%d")

        for line in lines[1:]:
            values = [v.strip().strip('"') for v in line.split(",")]
            row = dict(zip(header, values))
            title = row.get("title", row.get("이벤트명", "")).strip()
            if not title:
                continue

            event_id = f"evt-{today_str}-{slugify(title)}"
            event = {
                "id": event_id,
                "title": title,
                "source": "google_sheet_manual",
                "scraped_at": datetime.now(KST).isoformat(),
            }
            # 선택 필드 처리
            for field in ("start_date", "end_date", "url", "description", "category"):
                val = row.get(field, "").strip()
                if val:
                    event[field] = val
            events.append(event)

        print(f"[naver_cafe_events] 구글시트 폴백: {len(events)}개 이벤트 로드")
        return events

    except Exception as e:
        print(f"  [ERROR] 구글시트 폴백 실패: {e}")
        return []


def main():
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["event_sources"]["naver_cafe_events"].get("enabled", True):
        print("[naver_cafe_events] 비활성화, 스킵")
        sys.exit(0)

    event_config = sources["event_sources"]["naver_cafe_events"]
    target_cafes = event_config.get("target_cafes", [])
    delay = sources.get("card_sources", {}).get("naver_cafe", {}).get("request_delay_sec", 1)

    all_events = []
    crawl_success = False

    for cafe in target_cafes:
        cafe_id = cafe["name"] if isinstance(cafe, dict) else cafe
        keywords = cafe.get("event_category_keywords", ["이벤트", "행사"]) if isinstance(cafe, dict) else ["이벤트"]

        for kw in keywords[:3]:
            time.sleep(delay)
            articles = search_cafe_events(cafe_id, kw)
            all_events.extend(articles)
            if articles:
                crawl_success = True

    # 구글시트 폴백
    if not crawl_success:
        sheet_env = event_config.get("google_sheet_fallback_env", "GOOGLE_SHEET_ID")
        sheet_id = os.environ.get(sheet_env, "")
        if sheet_id:
            print("[naver_cafe_events] 카페 크롤링 실패 → 구글시트 폴백 시도")
            all_events = fetch_google_sheet_events(sheet_id)
        else:
            print("[naver_cafe_events] 카페 크롤링 실패, 구글시트 미설정 → 커뮤니티 데이터 없음")

    # 중복 제거 (ID 기준)
    seen_ids = set()
    unique_events = []
    for e in all_events:
        eid = e.get("id", "")
        if eid not in seen_ids:
            seen_ids.add(eid)
            unique_events.append(e)

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "naver_cafe_community",
        "events": unique_events,
        "crawl_success": crawl_success,
    }

    out = ROOT / "data/raw/events_community.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[naver_cafe_events] {len(unique_events)}개 이벤트 → {out}")


if __name__ == "__main__":
    main()
