#!/usr/bin/env python3
"""PriceCharting에서 영어판 카드 + PSA/BGS 등급별 시세 수집."""
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# PriceCharting CSS 선택자 (구조 변경 시 config/sources.json으로 이관 예정)
PRICE_SELECTORS = {
    "PSA_10": "#grade-psa-10-price",
    "PSA_9": "#grade-psa-9-price",
    "PSA_8": "#grade-psa-8-price",
    "BGS_10": "#grade-bgs-10-price",
    "BGS_9.5": "#grade-bgs-9-5-price",
    "BGS_9": "#grade-bgs-9-price",
    "BGS_8.5": "#grade-bgs-8-5-price",
}

# 미그레이딩(raw) 가격 선택자 — fallback 순서
RAW_PRICE_SELECTORS = [
    "#used-price",
    "#used_price",
    "td#used-price",
    "span#used-price",
    "[id*='used-price']",
    "#complete-price",  # PriceCharting 일부 카드에서 사용
]


def parse_price_usd(text: str):
    if not text:
        return None
    clean = text.strip().replace("$", "").replace(",", "").split()[0]
    try:
        val = float(clean)
        return round(val, 2)
    except ValueError:
        return None


def scrape_card(card: dict) -> dict:
    pid = card.get("pricecharting_id")
    if not pid:
        return {"id": card["id"], "status": "no_id"}

    url = f"https://www.pricecharting.com/game/{pid}"
    print(f"  → {card['id']} ({url})")
    time.sleep(2 + random.uniform(0, 1))

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"    HTTP {resp.status_code}, HTML 길이: {len(resp.text)}")
        if resp.status_code == 403:
            print(f"  [BLOCKED] PriceCharting {card['id']}: HTTP 403")
            return {"id": card["id"], "status": "blocked"}
        if resp.status_code != 200:
            return {"id": card["id"], "status": f"http_{resp.status_code}"}

        soup = BeautifulSoup(resp.text, "html.parser")
        result = {"id": card["id"], "pricecharting_id": pid, "status": "ok"}

        # 미그레이딩 가격 — 다중 선택자 fallback
        raw_el = None
        matched_sel = None
        for sel in RAW_PRICE_SELECTORS:
            raw_el = soup.select_one(sel)
            if raw_el:
                matched_sel = sel
                break

        if raw_el:
            price = parse_price_usd(raw_el.get_text())
            if price:
                result["raw_usd"] = price
                print(f"    raw_usd={price} (선택자: {matched_sel})")
            else:
                print(f"    [WARN] '{matched_sel}' 발견했지만 파싱 실패: '{raw_el.get_text()[:60]}'")
        else:
            page_title = soup.title.text.strip() if soup.title else "N/A"
            print(f"    [WARN] raw price 선택자 전부 미발견. page_title='{page_title}'")

        # 등급별 가격
        graded = []
        for key, selector in PRICE_SELECTORS.items():
            el = soup.select_one(selector)
            if not el:
                continue
            price = parse_price_usd(el.get_text())
            if not price:
                continue
            company, grade = key.split("_", 1)
            graded.append({"company": company, "grade": grade, "price_usd": price})

        if graded:
            result["graded"] = graded

        # 썸네일
        img = soup.select_one("#product-image img") or soup.select_one(".product-image img")
        if img:
            result["thumbnail_url"] = img.get("src", "")

        return result

    except requests.RequestException as e:
        return {"id": card["id"], "status": "error", "error": str(e)}


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["card_sources"]["pricecharting"].get("enabled", True):
        print("[pricecharting] 비활성화, 스킵")
        sys.exit(0)

    cards = [c for c in watchlist["cards"] if "en" in c.get("editions", [])]
    print(f"[pricecharting] {len(cards)}개 카드 수집")

    results = [scrape_card(c) for c in cards]

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "pricecharting",
        "edition": "en",
        "cards": results,
    }

    out = ROOT / "data/raw/cards_pricecharting.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[pricecharting] 완료 → {out}")


if __name__ == "__main__":
    main()
