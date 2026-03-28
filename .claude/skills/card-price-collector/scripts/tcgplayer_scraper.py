#!/usr/bin/env python3
"""pokemontcg.io 공개 API로 영어판 TCGPlayer 시세 수집.

HTML 스크래핑 대신 pokemontcg.io API를 사용:
- API 키 불필요, 차단 없음, 안정적
- 응답에서 tcgplayer.prices.{type}.market 추출
"""
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("필요 패키지: pip install requests")
    sys.exit(1)

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))

API_BASE = "https://api.pokemontcg.io/v2/cards"
HEADERS = {
    "User-Agent": "PokemonGoodsTracker/1.0",
}

# 가격 타입 우선순위: 카드 등급별로 가장 관련성 높은 타입 순
PRICE_TYPE_PRIORITY = [
    "holofoil",
    "reverseHolofoil",
    "normal",
    "1stEditionHolofoil",
    "1stEditionNormal",
]


def fetch_card_prices(card: dict) -> dict:
    """pokemontcg.io API로 단일 카드 시세 조회."""
    pokemontcg_id = card.get("pokemontcg_id")
    if not pokemontcg_id:
        return {"id": card["id"], "status": "no_id"}

    time.sleep(0.5)  # API rate limit 준수

    try:
        resp = requests.get(f"{API_BASE}/{pokemontcg_id}", headers=HEADERS, timeout=15)
        if resp.status_code == 404:
            print(f"  [NOT FOUND] {card['id']}: pokemontcg_id={pokemontcg_id} 없음")
            return {"id": card["id"], "status": "not_found"}
        if resp.status_code != 200:
            print(f"  [ERROR] {card['id']}: HTTP {resp.status_code}")
            return {"id": card["id"], "status": "error", "http_code": resp.status_code}

        data = resp.json().get("data", {})
        result = {
            "id": card["id"],
            "pokemontcg_id": pokemontcg_id,
            "tcgplayer_id": card.get("tcgplayer_id", ""),
            "status": "ok",
        }

        # TCGPlayer 가격 추출
        tcgplayer = data.get("tcgplayer", {})
        prices = tcgplayer.get("prices", {})

        if prices:
            # 우선순위 순으로 시장가 추출
            for price_type in PRICE_TYPE_PRIORITY:
                if price_type in prices:
                    market = prices[price_type].get("market")
                    if market is not None:
                        result["market_avg_usd"] = round(float(market), 2)
                        result["price_type"] = price_type
                        # 추가 정보
                        low = prices[price_type].get("low")
                        high = prices[price_type].get("high")
                        if low is not None:
                            result["low_usd"] = round(float(low), 2)
                        if high is not None:
                            result["high_usd"] = round(float(high), 2)
                        break

            # 업데이트 시각
            updated_at = tcgplayer.get("updatedAt")
            if updated_at:
                result["tcgplayer_updated_at"] = updated_at

        # 카드 이미지
        images = data.get("images", {})
        if images.get("small"):
            result["thumbnail_url"] = images["small"]

        if "market_avg_usd" not in result:
            print(f"  [WARN] {card['id']}: 가격 데이터 없음 (prices={list(prices.keys())})")

        return result

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"  [ERROR] {card['id']}: {e}")
        return {"id": card["id"], "status": "error", "error": str(e)}


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources["card_sources"]["tcgplayer"].get("enabled", True):
        print("[tcgplayer] 비활성화 상태, 스킵")
        sys.exit(0)

    # en 에디션 카드만 대상
    cards = [c for c in watchlist["cards"] if "en" in c.get("editions", [])]
    print(f"[tcgplayer/pokemontcg.io] {len(cards)}개 카드 수집 시작")

    results = []
    for card in cards:
        print(f"  → {card['id']} (pokemontcg_id={card.get('pokemontcg_id', '없음')})")
        result = fetch_card_prices(card)
        results.append(result)

    warnings = [r for r in results if r.get("status") not in ("ok", "no_id")]
    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "tcgplayer",
        "api": "pokemontcg.io",
        "edition": "en",
        "cards": results,
        "warnings": warnings,
    }

    out_path = ROOT / "data/raw/cards_tcgplayer.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[tcgplayer] 완료: {len(results)}개 → {out_path}")
    if warnings:
        print(f"  경고 {len(warnings)}건: {[w['id'] for w in warnings]}")


if __name__ == "__main__":
    main()
