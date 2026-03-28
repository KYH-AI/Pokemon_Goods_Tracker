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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def load_exchange_rate() -> float:
    rate_path = ROOT / "config/exchange_rate.json"
    if rate_path.exists():
        data = json.loads(rate_path.read_text(encoding="utf-8"))
        return float(data.get("rate", 1340.0))
    return 1340.0


def parse_price_usd(text: str):
    if not text:
        return None
    clean = text.strip().replace(",", "")
    match = re.search(r"\$\s*([\d]+\.?\d*)", clean)
    if match:
        try:
            return round(float(match.group(1)), 2)
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


def extract_prices_from_soup(soup: BeautifulSoup) -> dict:
    """다중 전략으로 가격 추출 — BrickEconomy HTML 구조 변경에 대응."""
    result = {}

    # 전략 1: 공식 가격 통계 테이블 (ASP.NET 구조)
    for table in soup.select("table"):
        for row in table.select("tr"):
            cells = row.select("td, th")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            value_text = cells[1].get_text(strip=True)
            price = parse_price_usd(value_text)
            if not price:
                continue
            if any(k in label for k in ("new", "retail", "msrp")):
                result.setdefault("new_usd", price)
            elif any(k in label for k in ("used", "secondary", "market")):
                result.setdefault("used_usd", price)

    # 전략 2: CSS 클래스 기반 (구버전/신버전 혼합)
    selector_map = {
        "new_usd": [
            ".value-new", ".price-new", "[class*='value-new']",
            "[class*='price-new']", "#value-new",
        ],
        "used_usd": [
            ".value-used", ".price-used", "[class*='value-used']",
            "[class*='price-used']", "#value-used",
        ],
    }
    for field, selectors in selector_map.items():
        if field in result:
            continue
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                price = parse_price_usd(el.get_text())
                if price:
                    result[field] = price
                    break

    # 전략 3: 페이지 전체에서 "New:" / "Used:" 패턴 텍스트 파싱
    if "new_usd" not in result or "used_usd" not in result:
        page_text = soup.get_text(" ", strip=True)
        for pattern, field in [
            (r"New[:\s]+\$([\d,]+\.?\d*)", "new_usd"),
            (r"Used[:\s]+\$([\d,]+\.?\d*)", "used_usd"),
            (r"Retail[:\s]+\$([\d,]+\.?\d*)", "new_usd"),
        ]:
            if field in result:
                continue
            m = re.search(pattern, page_text, re.IGNORECASE)
            if m:
                try:
                    result[field] = round(float(m.group(1).replace(",", "")), 2)
                except ValueError:
                    pass

    return result


def scrape_brickeconomy(lego_item: dict, rate: float) -> dict:
    url = lego_item.get("brickeconomy_url", "")
    if not url:
        return {"id": lego_item["id"], "status": "no_url"}

    time.sleep(3 + random.uniform(0, 2))

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

        # 가격 추출 (다중 전략)
        prices = extract_prices_from_soup(soup)
        if "new_usd" in prices:
            result["new_usd"] = prices["new_usd"]
            result["new_krw"] = int(prices["new_usd"] * rate)
        if "used_usd" in prices:
            result["used_usd"] = prices["used_usd"]
            result["used_krw"] = int(prices["used_usd"] * rate)

        # 프리미엄% — 다중 선택자
        premium_selectors = [
            "[class*='premium']", "[class*='price-premium']",
            "[class*='growth']", "[class*='appreciation']",
        ]
        for sel in premium_selectors:
            el = soup.select_one(sel)
            if el:
                pct = parse_percent(el.get_text())
                if pct is not None:
                    result["premium_pct"] = pct
                    break

        # 재고/단종 상태 — 다중 선택자
        retired_selectors = [
            "[class*='availability']", "[class*='retired']",
            "[class*='status']", "[class*='discontinued']",
        ]
        for sel in retired_selectors:
            el = soup.select_one(sel)
            if el:
                avail_text = el.get_text(strip=True).lower()
                if "retired" in avail_text or "discontinued" in avail_text:
                    result["retired"] = True
                elif avail_text:
                    result["retired"] = False
                break

        # 썸네일 — 다중 선택자
        img_selectors = [
            ".set-image img", ".product-image img",
            "[class*='set-image'] img", "img[alt*='Pokemon']",
            "img[alt*='LEGO']",
        ]
        for sel in img_selectors:
            img = soup.select_one(sel)
            if img:
                src = img.get("src", "") or img.get("data-src", "")
                if src:
                    result["thumbnail_url"] = src
                    break

        if "new_usd" not in result and "used_usd" not in result:
            print(f"  [WARN] {lego_item['id']}: 가격 추출 실패 (선택자 불일치 가능성)")

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
