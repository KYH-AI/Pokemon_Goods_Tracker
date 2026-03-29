#!/usr/bin/env python3
"""LEGO 공식 한국 사이트에서 정가와 재고 상태 수집."""
import json
import sys
import time
import random
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
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def parse_krw(text: str):
    """한국어 가격 텍스트에서 원화 정수 추출."""
    if not text:
        return None
    clean = text.replace(",", "").replace("원", "").replace("₩", "").strip()
    match = re.search(r"[\d]+", clean)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


def scrape_lego_official(lego_item: dict) -> dict:
    set_number = lego_item.get("set_number", "")
    if not set_number:
        return {"id": lego_item["id"], "status": "no_set_number"}

    # watchlist에 하드코딩된 정가 / 썸네일 (scraping 실패 시 fallback)
    watchlist_price = lego_item.get("official_price_krw")
    watchlist_thumb = lego_item.get("thumbnail_url", "")
    lego_url = lego_item.get("lego_official_url", f"https://www.lego.com/ko-kr/product/{set_number}")

    time.sleep(2 + random.uniform(0, 0.5))

    try:
        resp = requests.get(lego_url, headers=HEADERS, timeout=20, allow_redirects=True)
        if resp.status_code == 404:
            return {"id": lego_item["id"], "status": "not_found", "set_number": set_number}
        if resp.status_code == 403:
            print(f"  [BLOCKED] LEGO 공식 {lego_item['id']}: HTTP 403 → watchlist 정가 사용")
            result = {"id": lego_item["id"], "set_number": set_number, "status": "ok", "price_source": "watchlist"}
            if watchlist_price:
                result["retail_price_krw"] = watchlist_price
            if watchlist_thumb:
                result["thumbnail_url"] = watchlist_thumb
            return result
        if resp.status_code != 200:
            return {"id": lego_item["id"], "status": f"http_{resp.status_code}"}

        soup = BeautifulSoup(resp.text, "html.parser")
        result = {
            "id": lego_item["id"],
            "set_number": set_number,
            "name_ko": lego_item.get("name_ko", ""),
            "status": "ok",
            "url": lego_url,
            "price_source": "scraped",
        }

        # 정가 추출
        price_el = (
            soup.select_one("[data-test='product-price']")
            or soup.select_one(".ProductPrice_priceValue__")
            or soup.select_one("[class*='price']")
        )
        if price_el:
            price = parse_krw(price_el.get_text())
            if price:
                result["retail_price_krw"] = price
        if "retail_price_krw" not in result and watchlist_price:
            result["retail_price_krw"] = watchlist_price
            result["price_source"] = "watchlist"

        # 재고 상태
        stock_el = (
            soup.select_one("[data-test='product-availability']")
            or soup.select_one("[class*='availability']")
            or soup.select_one("[class*='stock']")
        )
        if stock_el:
            stock_text = stock_el.get_text(strip=True).lower()
            if any(word in stock_text for word in ["품절", "out of stock", "sold out", "unavailable"]):
                result["in_stock"] = False
            elif any(word in stock_text for word in ["구매", "add to", "장바구니", "available"]):
                result["in_stock"] = True

        # 썸네일 (scraped 우선, 없으면 watchlist)
        img = (
            soup.select_one("[data-test='product-image'] img")
            or soup.select_one(".ProductImage_image__ img")
            or soup.select_one("img[alt*='LEGO']")
        )
        if img:
            src = img.get("src", "") or img.get("data-src", "")
            if src:
                result["thumbnail_url"] = src
        if "thumbnail_url" not in result and watchlist_thumb:
            result["thumbnail_url"] = watchlist_thumb

        return result

    except requests.RequestException as e:
        print(f"  [ERROR] LEGO 공식 {lego_item['id']}: {e}")
        result = {"id": lego_item["id"], "status": "error", "error": str(e), "price_source": "watchlist"}
        if watchlist_price:
            result["retail_price_krw"] = watchlist_price
        if watchlist_thumb:
            result["thumbnail_url"] = watchlist_thumb
        return result


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["lego_sources"]["lego_official"].get("enabled", True):
        print("[lego_official] 비활성화, 스킵")
        sys.exit(0)

    lego_items = watchlist.get("lego", [])
    print(f"[lego_official] {len(lego_items)}개 세트 수집")

    results = []
    for item in lego_items:
        print(f"  → {item['id']} (세트번호: {item.get('set_number', '?')})")
        result = scrape_lego_official(item)
        results.append(result)

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "lego_official",
        "region": "ko-kr",
        "sets": results,
    }

    out = ROOT / "data/raw/lego_official.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[lego_official] 완료 → {out}")


if __name__ == "__main__":
    main()
