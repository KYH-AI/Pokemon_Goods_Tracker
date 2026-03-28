#!/usr/bin/env python3
"""번개장터 모바일 웹에서 국내판 카드 매물 가격 수집."""
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
BLOCK_LOG = ROOT / "logs/block_tracker.json"

MOBILE_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
]


def log_block(source: str) -> int:
    """차단 발생 기록 및 연속 차단 일수 반환. 3일 연속 시 sources.json 자동 비활성화."""
    BLOCK_LOG.parent.mkdir(parents=True, exist_ok=True)
    tracker = json.loads(BLOCK_LOG.read_text(encoding="utf-8")) if BLOCK_LOG.exists() else {}

    today = datetime.now(KST).date().isoformat()
    yesterday = (datetime.now(KST).date() - timedelta(days=1)).isoformat()
    entry = tracker.get(source, {"consecutive_days": 0, "last_block_date": "", "dates": []})

    last_date = entry.get("last_block_date", "")
    if last_date == today:
        pass  # 이미 오늘 기록됨
    elif last_date == yesterday:
        entry["consecutive_days"] += 1
    else:
        entry["consecutive_days"] = 1

    entry["last_block_date"] = today
    entry["dates"] = (entry.get("dates", []) + [today])[-7:]
    tracker[source] = entry
    BLOCK_LOG.write_text(json.dumps(tracker, ensure_ascii=False, indent=2), encoding="utf-8")

    if entry["consecutive_days"] >= 3:
        print(f"[{source}] 3일 연속 차단 → sources.json에서 자동 비활성화")
        sources_path = ROOT / "config/sources.json"
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
        if source in sources.get("card_sources", {}):
            sources["card_sources"][source]["enabled"] = False
            sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")

    return entry["consecutive_days"]


def scrape_bunjang(keyword: str) -> list:
    url = "https://m.bunjang.co.kr/search/products"
    params = {"q": keyword, "order": "recent"}
    headers = {
        "User-Agent": random.choice(MOBILE_UAS),
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://m.bunjang.co.kr",
    }
    delay = random.uniform(3, 5)
    time.sleep(delay)

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)

        if resp.status_code in (403, 429):
            print(f"  [BLOCKED] 번개장터: HTTP {resp.status_code}")
            log_block("bunjang")
            return []

        if "captcha" in resp.text.lower() or resp.text.strip() == "":
            print("  [BLOCKED] 번개장터: CAPTCHA 또는 빈 응답")
            log_block("bunjang")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for product in soup.select(".product-item, [class*='product']")[:15]:
            name_el = product.select_one("[class*='name'], [class*='title']")
            price_el = product.select_one("[class*='price']")
            if not name_el or not price_el:
                continue
            price_text = price_el.get_text(strip=True).replace(",", "").replace("원", "").strip()
            try:
                price = int(float(price_text))
                if price <= 0:
                    continue
                items.append({
                    "title": name_el.get_text(strip=True),
                    "price_krw": price,
                    "status_note": "판매 희망가 (수수료 6%+ 별도)",
                })
            except ValueError:
                continue
        return items

    except requests.RequestException as e:
        print(f"  [ERROR] 번개장터: {e}")
        return []


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["card_sources"]["bunjang"].get("enabled", True):
        print("[bunjang] 비활성화, 스킵")
        sys.exit(0)

    cards_kr = [c for c in watchlist["cards"] if "kr" in c.get("editions", [])]
    results = []

    for card in cards_kr:
        keywords = card.get("domestic_search_keywords", [card.get("name_ko", card["id"])])
        all_listings = []
        for kw in keywords[:2]:
            listings = scrape_bunjang(kw)
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
        "source": "bunjang",
        "edition": "kr",
        "cards": results,
    }

    out = ROOT / "data/raw/cards_bunjang.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[bunjang] 완료 → {out}")


if __name__ == "__main__":
    main()
