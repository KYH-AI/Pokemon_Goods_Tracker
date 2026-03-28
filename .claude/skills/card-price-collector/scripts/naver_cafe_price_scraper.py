#!/usr/bin/env python3
"""네이버 카페 공개 게시판에서 국내판 카드 시세글 원문 수집."""
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

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
    """로그인 페이지로 리다이렉트됐는지 확인."""
    return "login.naver.com" in resp.url or "nidlogin" in resp.text


def search_cafe(cafe_id: str, keyword: str) -> list:
    """네이버 카페 검색 (공개 게시글만)."""
    url = "https://cafe.naver.com/ArticleSearchList.nhn"
    params = {
        "query": keyword,
        "search.clubid": cafe_id,
        "search.searchBy": "0",
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10, allow_redirects=True)
        if is_login_redirect(resp):
            print(f"  [SKIP] 카페 {cafe_id}: 로그인 필요 감지")
            return []
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        for item in soup.select(".article-item, .list-item, .article")[:10]:
            title_el = item.select_one(".article-title, .item-title, a[href*='ArticleRead']")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if not link or ("ArticleRead" not in link and "cafearticle" not in link):
                continue
            articles.append({
                "title": title,
                "url": f"https://cafe.naver.com{link}" if link.startswith("/") else link,
                "content_preview": "",
                "date": "",
                "cafe_id": cafe_id,
                "keyword": keyword,
            })
        return articles

    except requests.RequestException as e:
        print(f"  [ERROR] 카페 {cafe_id} 검색 실패: {e}")
        return []


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["card_sources"]["naver_cafe"].get("enabled", True):
        print("[naver_cafe_price] 비활성화, 스킵")
        sys.exit(0)

    target_cafes = sources["card_sources"]["naver_cafe"]["target_cafes"]
    cards_kr = [c for c in watchlist["cards"] if "kr" in c.get("editions", [])]
    delay = sources["card_sources"]["naver_cafe"].get("request_delay_sec", 1)

    all_articles = []
    for card in cards_kr:
        keywords = card.get("naver_cafe_keywords", [card.get("name_ko", card["id"])])
        for cafe in target_cafes:
            for kw in keywords[:2]:
                time.sleep(delay)
                articles = search_cafe(cafe["id"], kw)
                for a in articles:
                    a["card_id"] = card["id"]
                all_articles.extend(articles)
                if articles:
                    break

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "naver_cafe",
        "edition": "kr",
        "articles": all_articles,
        "note": "원문 텍스트만 수집. 시세 파싱은 data-enrichment-agent가 처리.",
    }

    out = ROOT / "data/raw/cards_kr_naver.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[naver_cafe_price] {len(all_articles)}개 게시글 수집 → {out}")


if __name__ == "__main__":
    main()
