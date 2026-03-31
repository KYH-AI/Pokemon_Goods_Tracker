#!/usr/bin/env python3
"""번개장터 JSON API로 국내판 카드 매물 가격 수집."""
import json
import sys
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("필요 패키지: pip install requests")
    sys.exit(1)

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))
BLOCK_LOG = ROOT / "logs/block_tracker.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


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
    time.sleep(1 + random.uniform(0, 1))

    try:
        url = f"https://api.bunjang.co.kr/api/1/find_v2.json?q={requests.utils.quote(keyword)}&n=20&page=0"
        resp = requests.get(url, headers=HEADERS, timeout=10)

        if resp.status_code in (403, 429):
            print(f"  [BLOCKED] 번개장터: HTTP {resp.status_code}")
            log_block("bunjang")
            return []

        if resp.status_code != 200:
            return []

        items = []
        for item in resp.json().get("list", []):
            price_str = item.get("price", "0")
            try:
                price = int(price_str)
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue
            items.append({
                "pid": item.get("pid", ""),
                "title": item.get("name", ""),
                "price_krw": price,
                "thumbnail": item.get("image", ""),
                "updated_at": item.get("update_time", ""),
                "status_note": "판매 희망가 (수수료 6%+ 별도)",
            })
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
            prices = sorted(li["price_krw"] for li in all_listings)
            # IQR 기반 이상치 제거
            if len(prices) >= 4:
                q1 = prices[len(prices) // 4]
                q3 = prices[(len(prices) * 3) // 4]
                iqr = q3 - q1
                filtered = [p for p in prices if q1 - 1.5 * iqr <= p <= q3 + 1.5 * iqr]
                if filtered:
                    prices = filtered
            results.append({
                "id": card["id"],
                "active_count": len(prices),
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
