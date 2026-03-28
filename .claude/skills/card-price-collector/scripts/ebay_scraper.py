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


def extract_usd_price(text: str):
    """USD 가격 추출. 'US $30.00', '$30.00', '30.00' 등 처리."""
    if not text:
        return None
    clean = text.strip().replace(",", "")
    # USD 가격만 추출 ($기호 앞에 통화코드 없는 것, 또는 US $)
    match = re.search(r"(?:US\s*)?\$\s*([\d]+\.?\d*)", clean)
    if match:
        try:
            return round(float(match.group(1)), 2)
        except ValueError:
            return None
    return None


def scrape_ebay_sold(keyword: str, max_results: int = 10) -> list:
    """eBay 낙찰 완료 리스팅 크롤링."""
    url = "https://www.ebay.com/sch/i.html"
    params = {
        "_nkw": keyword,
        "LH_Complete": "1",
        "LH_Sold": "1",
        "_sacat": "183454",  # Trading Cards 카테고리
        "_ipg": "50",
        "LH_PrefLoc": "1",  # 미국 판매자 우선
    }
    time.sleep(1)
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if resp.status_code == 403:
            print(f"  [BLOCKED] eBay: HTTP 403 (keyword={keyword!r})")
            return []
        if resp.status_code != 200:
            print(f"  [WARN] eBay HTTP {resp.status_code} (keyword={keyword!r})")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for listing in soup.select(".s-item")[:max_results + 5]:
            title_el = listing.select_one(".s-item__title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            # eBay가 삽입하는 placeholder 아이템 스킵
            if "Shop on eBay" in title or not title:
                continue

            # 가격 추출: 다중 선택자 fallback
            price = None
            for sel in (".s-item__price", ".POSITIVE", "span[class*='price']"):
                el = listing.select_one(sel)
                if el:
                    price = extract_usd_price(el.get_text(strip=True))
                    if price:
                        break
            if not price:
                continue

            # 날짜: 다중 선택자 fallback
            sold_date = ""
            for sel in (".s-item__endedDate", ".s-item__listingDate",
                        "[class*='ended']", "[class*='sold-date']"):
                el = listing.select_one(sel)
                if el:
                    sold_date = el.get_text(strip=True)
                    break

            if len(items) >= max_results:
                break
            items.append({
                "title": title,
                "sold_price_usd": price,
                "sold_date": sold_date,
            })
        return items
    except Exception as e:
        print(f"  [ERROR] eBay 파싱 실패: {e}")
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
