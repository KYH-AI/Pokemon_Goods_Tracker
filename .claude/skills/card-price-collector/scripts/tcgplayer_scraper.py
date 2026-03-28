#!/usr/bin/env python3
"""TCGPlayer에서 영어판 포켓몬 카드 시세 수집."""
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

ROOT = Path(__file__).parent.parent.parent.parent.parent  # 프로젝트 루트
KST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def load_config():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    return watchlist, sources


def scrape_card_price(card: dict, sources: dict) -> dict:
    """단일 카드의 TCGPlayer 시세 수집."""
    tcgplayer_id = card.get("tcgplayer_id")
    if not tcgplayer_id:
        return {"id": card["id"], "status": "no_id"}

    config = sources["card_sources"]["tcgplayer"]
    delay = config.get("request_delay_sec", 2)
    time.sleep(delay + random.uniform(0, 1))

    url = f"https://www.tcgplayer.com/product/{tcgplayer_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 403:
            print(f"  [BLOCKED] TCGPlayer {card['id']}: HTTP 403")
            return {"id": card["id"], "status": "blocked"}
        if resp.status_code != 200:
            print(f"  [ERROR] TCGPlayer {card['id']}: HTTP {resp.status_code}")
            return {"id": card["id"], "status": "error", "http_code": resp.status_code}

        soup = BeautifulSoup(resp.text, "html.parser")
        price_data = {
            "id": card["id"],
            "tcgplayer_id": tcgplayer_id,
            "status": "ok",
        }

        # Market Price 추출 시도 (여러 선택자 시도)
        market_el = (
            soup.select_one("[data-testid='market-price']")
            or soup.select_one(".price-point__data")
            or soup.select_one(".markt-price")
        )
        if market_el:
            price_text = market_el.get_text(strip=True).replace("$", "").replace(",", "")
            try:
                price_data["market_avg_usd"] = float(price_text.split()[0])
            except (ValueError, IndexError):
                price_data["status"] = "parse_error"

        # 썸네일 URL
        img_el = soup.select_one(".product-gallery__image img")
        if img_el:
            price_data["thumbnail_url"] = img_el.get("src", "")

        return price_data

    except requests.RequestException as e:
        print(f"  [ERROR] TCGPlayer {card['id']}: {e}")
        return {"id": card["id"], "status": "error", "error": str(e)}


def main():
    watchlist, sources = load_config()

    if not sources["card_sources"]["tcgplayer"].get("enabled", True):
        print("[tcgplayer] 비활성화 상태, 스킵")
        sys.exit(0)

    # en 에디션 카드만 대상
    cards = [c for c in watchlist["cards"] if "en" in c.get("editions", [])]
    print(f"[tcgplayer] {len(cards)}개 카드 수집 시작")

    results = []
    for card in cards:
        print(f"  → {card['id']}")
        result = scrape_card_price(card, sources)
        results.append(result)

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "tcgplayer",
        "edition": "en",
        "cards": results,
        "warnings": [r for r in results if r.get("status") not in ("ok", "no_id")],
    }

    out_path = ROOT / "data/raw/cards_tcgplayer.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[tcgplayer] 완료: {len(results)}개 → {out_path}")


if __name__ == "__main__":
    main()
