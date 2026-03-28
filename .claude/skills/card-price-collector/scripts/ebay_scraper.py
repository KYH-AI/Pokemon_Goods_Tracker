#!/usr/bin/env python3
"""eBay Sold listings에서 영어판 카드 실거래가(낙찰가) 수집."""
import json
import sys
import time
import re
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
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_ebay_sold(keyword: str, max_results: int = 10) -> list:
    """eBay 낙찰 완료 리스팅 크롤링."""
    url = "https://www.ebay.com/sch/i.html"
    params = {
        "_nkw": keyword,
        "LH_Complete": "1",
        "LH_Sold": "1",
        "_sacat": "0",
        "_ipg": "50",
    }
    time.sleep(1)
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for listing in soup.select(".s-item")[:max_results]:
            title_el = listing.select_one(".s-item__title")
            price_el = listing.select_one(".s-item__price")
            date_el = listing.select_one(".s-item__endedDate")
            if not title_el or not price_el:
                continue
            price_text = price_el.get_text(strip=True).replace(",", "")
            price_match = re.search(r"\$?([\d]+\.?\d*)", price_text)
            if not price_match:
                continue
            items.append({
                "title": title_el.get_text(strip=True),
                "sold_price_usd": round(float(price_match.group(1)), 2),
                "sold_date": date_el.get_text(strip=True) if date_el else "",
            })
        return items
    except Exception:
        return []


def collect_card(card: dict, ebay_config: dict) -> dict:
    result = {
        "id": card["id"],
        "status": "ok",
        "sold_listings": [],
        "graded_sold": [],
    }
    keywords = card.get("ebay_search_keywords", [card.get("name_en", card["id"])])

    # 미그레이딩 수집
    for kw in keywords[:2]:
        listings = scrape_ebay_sold(kw, ebay_config.get("max_results_per_card", 10))
        result["sold_listings"].extend(listings)
        if listings:
            break

    # 등급별 수집
    grading_patterns = ebay_config.get("grading_search_patterns", {})
    for company, grades in grading_patterns.items():
        for grade, search_terms in grades.items():
            for base_kw in keywords[:1]:
                combined_kw = f"{base_kw} {search_terms[0]}"
                listings = scrape_ebay_sold(combined_kw, 5)
                if listings:
                    prices = [li["sold_price_usd"] for li in listings]
                    result["graded_sold"].append({
                        "company": company,
                        "grade": grade,
                        "recent_sold_count": len(listings),
                        "avg_sold_usd": round(sum(prices) / len(prices), 2),
                        "last_sold_date": listings[0].get("sold_date", ""),
                    })
                    break

    if result["sold_listings"]:
        prices = [li["sold_price_usd"] for li in result["sold_listings"]]
        result["avg_sold_usd"] = round(sum(prices) / len(prices), 2)
        result["recent_sold_count"] = len(prices)

    return result


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    ebay_config = json.loads((ROOT / "config/ebay_config.json").read_text(encoding="utf-8"))

    if not sources["card_sources"]["ebay"].get("enabled", True):
        print("[ebay] 비활성화, 스킵")
        sys.exit(0)

    # en 에디션 카드만
    cards = [c for c in watchlist["cards"] if "en" in c.get("editions", [])]
    print(f"[ebay] {len(cards)}개 카드 수집")

    results = [collect_card(c, ebay_config) for c in cards]

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "ebay",
        "edition": "en",
        "cards": results,
    }

    out = ROOT / "data/raw/cards_ebay.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ebay] 완료 → {out}")


if __name__ == "__main__":
    main()
