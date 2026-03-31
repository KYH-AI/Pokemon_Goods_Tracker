#!/usr/bin/env python3
"""포켓몬카드 공식 사이트(pokemoncard.co.kr) 이벤트 수집."""
import json
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
    "Referer": "https://pokemoncard.co.kr",
}

BASE_URL = "https://pokemoncard.co.kr"
EVENTS_URL = "https://pokemoncard.co.kr/card/category/event"


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text[:40]


def make_event_id(date_str: str, title: str) -> str:
    date_clean = re.sub(r"[^0-9]", "", date_str)[:8]
    if not date_clean or len(date_clean) < 8:
        date_clean = datetime.now(KST).strftime("%Y%m%d")
    return f"evt-{date_clean}-{slugify(title)}"


def parse_date_range(text: str) -> tuple:
    date_pattern = r"(\d{4}[.\-]\d{2}[.\-]\d{2})"
    dates = re.findall(date_pattern, text)
    if len(dates) >= 2:
        return dates[0].replace(".", "-"), dates[1].replace(".", "-")
    elif len(dates) == 1:
        start = dates[0].replace(".", "-")
        return start, start
    return "", ""


def fetch_detail_dates(url: str) -> tuple:
    """상세 페이지에서 날짜 정보 추출."""
    try:
        time.sleep(0.5)
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return "", ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for sel in (".date", ".period", "[class*='date']", "time", ".info"):
            el = soup.select_one(sel)
            if el:
                start, end = parse_date_range(el.get_text())
                if start:
                    return start, end
        # 본문 전체에서 날짜 패턴 탐색
        body_text = soup.get_text()
        return parse_date_range(body_text)
    except Exception:
        return "", ""


def scrape_events() -> list:
    """pokemoncard.co.kr 이벤트 목록 크롤링."""
    try:
        resp = requests.get(EVENTS_URL, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"  [ERROR] HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        events = []

        # pokemoncard.co.kr 구조: <a href="..."> 안에 <img>, <h4>
        # /card/event/view/ 또는 /card/category/ 하위 링크
        event_links = soup.select(
            "a[href*='/card/event'], a[href*='/card/view'], a[href*='/event/view']"
        )

        # 링크가 없으면 더 넓은 범위로 탐색 (이미지+h4 포함 링크)
        if not event_links:
            event_links = [
                a for a in soup.select("a[href]")
                if a.select_one("h4, h3") and a.select_one("img")
            ]

        seen_hrefs = set()
        unique_links = []
        for link in event_links:
            href = link.get("href", "")
            if href and href not in seen_hrefs:
                seen_hrefs.add(href)
                unique_links.append(link)

        for link in unique_links:
            href = link.get("href", "")
            detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)

            title_el = link.select_one("h4, h3, .title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            img_el = link.select_one("img")
            thumbnail = ""
            if img_el:
                src = img_el.get("src", "") or img_el.get("data-src", "")
                if src:
                    thumbnail = src if src.startswith("http") else urljoin(BASE_URL, src)

            # 목록에서 날짜 탐색
            date_el = link.select_one(".date, .period, [class*='date'], time")
            date_text = date_el.get_text(strip=True) if date_el else ""
            start_date, end_date = parse_date_range(date_text)

            # 날짜 없으면 상세 페이지 방문
            if not start_date and detail_url:
                start_date, end_date = fetch_detail_dates(detail_url)

            today = datetime.now(KST).date().isoformat()
            if end_date and end_date < today:
                event_status = "ended"
            elif start_date and start_date > today:
                event_status = "upcoming"
            else:
                event_status = "ongoing"

            event_id = make_event_id(start_date or datetime.now(KST).strftime("%Y%m%d"), title)

            event = {
                "id": event_id,
                "title": title,
                "source": "pokemoncard_official",
                "event_status": event_status,
            }
            if start_date:
                event["start_date"] = start_date
            if end_date and end_date != start_date:
                event["end_date"] = end_date
            if detail_url:
                event["url"] = detail_url
            if thumbnail:
                event["thumbnail_url"] = thumbnail

            events.append(event)

        return events

    except requests.RequestException as e:
        print(f"  [ERROR] pokemoncard 크롤링 실패: {e}")
        return []


def main():
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["event_sources"].get("pokemoncard", {}).get("enabled", True):
        print("[pokemoncard] 비활성화, 스킵")
        sys.exit(0)

    delay = sources["event_sources"].get("pokemoncard", {}).get("request_delay_sec", 2)
    time.sleep(delay)

    print("[pokemoncard] 이벤트 수집 시작")
    events = scrape_events()
    print(f"[pokemoncard] {len(events)}개 이벤트 수집")

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "pokemoncard_official",
        "events": events,
    }

    out = ROOT / "data/raw/events_pokemoncard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[pokemoncard] 완료 → {out}")


if __name__ == "__main__":
    main()
