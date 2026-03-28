#!/usr/bin/env python3
"""BrickEconomy에서 레고 중고 시세, 프리미엄%, 재고 상태 수집."""
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
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def load_exchange_rate() -> float:
    """환율 캐시에서 USD→KRW 환율 로드."""
    rate_path = ROOT / "config/exchange_rate.json"
    if rate_path.exists():
        data = json.loads(rate_path.read_text(encoding="utf-8"))
        return float(data.get("rate", 1340.0))
    return 1340.0


def parse_price_usd(text: str):
    if not text:
        return None
    clean = text.strip().replace("$", "").replace(",", "")
    match = re.search(r"[\d]+\.?\d*", clean)
    if match:
        try:
            return round(float(match.group()), 2)
        except ValueError:
            return None
    return None


def parse_percent(text: str):
    if not text:
        return None
    match = re.search(r"([+-]?[\d.]+)%", text)
    if match:
        try:
            return round(float(match.group(1)), 1)
        except ValueError:
            return None
    return None


def scrape_brickeconomy(lego_item: dict, rate: float) -> dict:
    url = lego_item.get("brickeconomy_url", "")
    if not url:
        return {"id": lego_item["id"], "status": "no_url"}

    time.sleep(3 + random.uniform(0, 1))

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 403:
            print(f"  [BLOCKED] BrickEconomy {lego_item['id']}: HTTP 403")
            return {"id": lego_item["id"], "status": "blocked"}
        if resp.status_code != 200:
            return {"id": lego_item["id"], "status": f"http_{resp.status_code}"}

        soup = BeautifulSoup(resp.text, "html.parser")
        result = {
            "id": lego_item["id"],
            "set_number": lego_item.get("set_number", ""),
            "status": "ok",
        }

        # 현재가(Used/New) 파싱
        price_rows = soup.select(".table-price tr, .price-table tr")
        for row in price_rows:
            cells = row.select("td")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            price_text = cells[1].get_text(strip=True)
            price = parse_price_usd(price_text)
            if not price:
                continue
            if "new" in label:
                result["new_usd"] = price
                result["new_krw"] = int(price * rate)
            elif "used" in label:
                result["used_usd"] = price
                result["used_krw"] = int(price * rate)

        # 프리미엄% (소매가 대비 상승률)
        premium_el = soup.select_one("[class*='premium'], [class*='price-premium']")
        if premium_el:
            pct = parse_percent(premium_el.get_text())
            if pct is not None:
                result["premium_pct"] = pct

        # 재고 상태 (단종 여부)
        availability_el = soup.select_one("[class*='availability'], [class*='retired']")
        if availability_el:
            avail_text = availability_el.get_text(strip=True).lower()
            if "retired" in avail_text or "단종" in avail_text:
                result["retired"] = True
            else:
                result["retired"] = False

        # 썸네일
        img = soup.select_one(".set-image img, .product-image img")
        if img:
            src = img.get("src", "") or img.get("data-src", "")
            if src:
                result["thumbnail_url"] = src

        return result

    except requests.RequestException as e:
        print(f"  [ERROR] BrickEconomy {lego_item['id']}: {e}")
        return {"id": lego_item["id"], "status": "error", "error": str(e)}


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["lego_sources"]["brickeconomy"].get("enabled", True):
        print("[brickeconomy] 비활성화, 스킵")
        sys.exit(0)

    rate = load_exchange_rate()
    print(f"[brickeconomy] 환율: 1 USD = {rate} KRW")

    lego_items = watchlist.get("lego", [])
    print(f"[brickeconomy] {len(lego_items)}개 세트 수집")

    results = []
    for item in lego_items:
        print(f"  → {item['id']}")
        result = scrape_brickeconomy(item, rate)
        results.append(result)

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "brickeconomy",
        "exchange_rate_used": rate,
        "sets": results,
    }

    out = ROOT / "data/raw/lego_brickeconomy.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[brickeconomy] 완료 → {out}")


if __name__ == "__main__":
    main()
