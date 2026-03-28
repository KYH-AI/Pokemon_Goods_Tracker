#!/usr/bin/env python3
"""당근마켓 검색 페이지에서 국내판 카드 매물 가격 수집."""
import json
import sys
import time
import random
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

# bunjang_scraper의 log_block 재사용
sys.path.insert(0, str(Path(__file__).parent))
from bunjang_scraper import log_block  # noqa: E402

MOBILE_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
]


def scrape_daangn(keyword: str) -> list:
    url = "https://www.daangn.com/search"
    params = {"q": keyword}
    headers = {
        "User-Agent": random.choice(MOBILE_UAS),
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.daangn.com",
    }
    delay = random.uniform(5, 8)
    time.sleep(delay)

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15, allow_redirects=True)

        if resp.status_code in (403, 429):
            print(f"  [BLOCKED] 당근마켓: HTTP {resp.status_code}")
            log_block("daangn")
            return []

        if "login" in resp.url.lower() or resp.text.strip() == "":
            print("  [BLOCKED] 당근마켓: 리다이렉트 또는 빈 응답")
            log_block("daangn")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []

        for article in soup.select("article, [class*='article'], [class*='item']")[:10]:
            title_el = article.select_one("[class*='title'], h3, h4")
            price_el = article.select_one("[class*='price']")
            if not title_el or not price_el:
                continue
            price_text = price_el.get_text(strip=True).replace(",", "").replace("원", "").strip()
            try:
                price = int(float(price_text))
                if price <= 0:
                    continue
                items.append({
                    "title": title_el.get_text(strip=True),
                    "price_krw": price,
                    "status_note": "판매 희망가 (직거래 기반)",
                })
            except ValueError:
                continue
        return items

    except requests.RequestException as e:
        print(f"  [ERROR] 당근마켓: {e}")
        return []


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["card_sources"]["daangn"].get("enabled", True):
        print("[daangn] 비활성화, 스킵")
        sys.exit(0)

    cards_kr = [c for c in watchlist["cards"] if "kr" in c.get("editions", [])]
    results = []

    for card in cards_kr:
        keywords = card.get("domestic_search_keywords", [card.get("name_ko", card["id"])])
        all_listings = []
        for kw in keywords[:2]:
            listings = scrape_daangn(kw)
            all_listings.extend(listings)
            if listings:
                break

        if all_listings:
            prices = [li["price_krw"] for li in all_listings]
            results.append({
                "id": card["id"],
                "active_count": len(all_listings),
                "price_range_krw": [min(prices), max(prices)],
                "avg_krw": int(sum(prices) / len(prices)),
                "listings": all_listings[:5],
                "status": "ok",
            })
        else:
            results.append({"id": card["id"], "active_count": 0, "status": "no_results"})

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "daangn",
        "edition": "kr",
        "cards": results,
    }

    out = ROOT / "data/raw/cards_daangn.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[daangn] 완료 → {out}")


if __name__ == "__main__":
    main()
