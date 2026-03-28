#!/usr/bin/env python3
"""포켓몬코리아 공식 웹사이트 이벤트 페이지 크롤링."""
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
    "Referer": "https://www.pokemon.co.kr",
}

BASE_URL = "https://www.pokemon.co.kr"
EVENTS_URL = "https://www.pokemon.co.kr/event/"


def slugify(text: str) -> str:
    """텍스트를 URL-안전 슬러그로 변환."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text[:40]


def make_event_id(date_str: str, title: str) -> str:
    """evt-{YYYYMMDD}-{slug} 형식 ID 생성."""
    date_clean = re.sub(r"[^0-9]", "", date_str)[:8]
    if not date_clean or len(date_clean) < 8:
        date_clean = datetime.now(KST).strftime("%Y%m%d")
    return f"evt-{date_clean}-{slugify(title)}"


def parse_date_range(text: str) -> tuple:
    """날짜 범위 텍스트 파싱 → (start_date, end_date) 반환."""
    # 패턴: "2026.03.01 ~ 2026.03.31" 또는 "2026-03-01 ~ 2026-03-31"
    date_pattern = r"(\d{4}[.\-]\d{2}[.\-]\d{2})"
    dates = re.findall(date_pattern, text)
    if len(dates) >= 2:
        start = dates[0].replace(".", "-")
        end = dates[1].replace(".", "-")
        return start, end
    elif len(dates) == 1:
        start = dates[0].replace(".", "-")
        return start, start
    return "", ""


def scrape_events() -> list:
    """포켓몬코리아 이벤트 목록 크롤링."""
    try:
        resp = requests.get(EVENTS_URL, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"  [ERROR] HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        events = []

        # 이벤트 목록 항목 선택 (포켓몬코리아 페이지 구조에 맞게 조정)
        event_items = soup.select(
            ".event-list li, .event-item, [class*='event'] li, .board-list li"
        )

        for item in event_items:
            title_el = item.select_one("a, .title, h3, h4")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # 링크
            link_el = item.select_one("a[href]")
            detail_url = ""
            if link_el:
                href = link_el.get("href", "")
                detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)

            # 날짜 파싱
            date_el = item.select_one(".date, .period, [class*='date'], time")
            date_text = date_el.get_text(strip=True) if date_el else ""
            start_date, end_date = parse_date_range(date_text)

            # 상태 판단 (진행중/예정/종료)
            today = datetime.now(KST).date().isoformat()
            if end_date and end_date < today:
                event_status = "ended"
            elif start_date and start_date > today:
                event_status = "upcoming"
            else:
                event_status = "ongoing"

            # 썸네일
            img_el = item.select_one("img")
            thumbnail = ""
            if img_el:
                src = img_el.get("src", "") or img_el.get("data-src", "")
                thumbnail = src if src.startswith("http") else urljoin(BASE_URL, src)

            event_id = make_event_id(start_date or datetime.now(KST).strftime("%Y%m%d"), title)

            event = {
                "id": event_id,
                "title": title,
                "source": "pokemon_korea_official",
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
        print(f"  [ERROR] 포켓몬코리아 크롤링 실패: {e}")
        return []


def main():
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["event_sources"]["pokemon_korea"].get("enabled", True):
        print("[pokemon_korea] 비활성화, 스킵")
        sys.exit(0)

    delay = sources["event_sources"]["pokemon_korea"].get("request_delay_sec", 2)
    time.sleep(delay)

    print("[pokemon_korea] 이벤트 수집 시작")
    events = scrape_events()
    print(f"[pokemon_korea] {len(events)}개 이벤트 수집")

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "pokemon_korea_official",
        "events": events,
    }

    out = ROOT / "data/raw/events_official.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[pokemon_korea] 완료 → {out}")


if __name__ == "__main__":
    main()
