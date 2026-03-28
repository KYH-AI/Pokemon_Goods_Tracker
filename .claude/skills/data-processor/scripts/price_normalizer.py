#!/usr/bin/env python3
"""
exchange_rate.json 로드 (만료 시 한국은행 API 재호출).
USD→KRW 환산. 전일 대비 ±30% 이상 변동 시 warning_flags 추가.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("필요 패키지: pip install requests")
    sys.exit(1)

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))
RATE_PATH = ROOT / "config/exchange_rate.json"
SOURCES_PATH = ROOT / "config/sources.json"

FALLBACK_RATE = 1340.0


def fetch_bok_rate(api_key: str) -> float:
    """한국은행 ECOS API에서 USD/KRW 환율 조회."""
    today = datetime.now(KST).strftime("%Y%m%d")
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    url_template = sources["exchange_rate"]["bok_api_url"]
    url = url_template.format(api_key=api_key, date=today)

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("StatisticSearch", {}).get("row", [])
            if rows:
                rate_str = rows[0].get("DATA_VALUE", "")
                rate_val = float(re.sub(r"[^0-9.]", "", rate_str))
                if rate_val > 100:  # 합리적 범위 확인
                    return round(rate_val, 2)
    except Exception as e:
        print(f"  [BOK API] 환율 조회 실패: {e}")
    return FALLBACK_RATE


def load_exchange_rate() -> tuple:
    """환율 캐시 로드. 만료 시 BOK API 재호출. (rate, fallback_used) 반환."""
    now = datetime.now(KST)

    if RATE_PATH.exists():
        cache = json.loads(RATE_PATH.read_text(encoding="utf-8"))
        expires_at_str = cache.get("expires_at", "")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if now < expires_at:
                    return float(cache.get("rate", FALLBACK_RATE)), cache.get("fallback_used", True)
            except ValueError:
                pass

    # 캐시 만료 → API 재호출
    print("[price_normalizer] 환율 캐시 만료 → BOK API 재조회")
    api_key = os.environ.get("BOK_API_KEY", "")
    if api_key:
        rate = fetch_bok_rate(api_key)
        fallback = False
    else:
        print("  [WARNING] BOK_API_KEY 미설정, 폴백 환율 사용")
        rate = FALLBACK_RATE
        fallback = True

    # 캐시 갱신
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    cache_days = sources["exchange_rate"].get("cache_days", 7)
    new_cache = {
        "_comment": "한국은행 ECOS API 환율 캐시. 최대 7일 유효. 만료 시 price_normalizer.py가 자동 갱신.",
        "base_currency": "USD",
        "target_currency": "KRW",
        "rate": rate,
        "fetched_at": now.isoformat(),
        "expires_at": (now + timedelta(days=cache_days)).isoformat(),
        "source": "한국은행 ECOS API" if not fallback else "폴백 값",
        "fallback_used": fallback,
    }
    RATE_PATH.write_text(json.dumps(new_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [price_normalizer] 환율 갱신: 1 USD = {rate} KRW")
    return rate, fallback


def load_previous_prices() -> dict:
    """이전 data/cards.json에서 가격 데이터 로드 (이상치 비교용)."""
    cards_path = ROOT / "data/cards.json"
    if not cards_path.exists():
        return {}
    try:
        prev = json.loads(cards_path.read_text(encoding="utf-8"))
        # {card_id: avg_price_krw} 형태로 인덱싱
        price_index = {}
        for card in prev.get("cards", []):
            cid = card.get("id", "")
            price = card.get("avg_price_krw")
            if cid and price:
                price_index[cid] = price
        return price_index
    except Exception:
        return {}


def check_price_anomaly(card_id: str, new_price_krw: int, prev_prices: dict) -> bool:
    """전일 대비 ±30% 이상 변동이면 True 반환."""
    prev = prev_prices.get(card_id)
    if not prev or prev <= 0:
        return False
    change_pct = abs(new_price_krw - prev) / prev * 100
    return change_pct >= 30.0


def normalize_card_prices(raw_file: Path, rate: float, prev_prices: dict):
    """단일 raw 파일의 USD 가격 → KRW 환산 및 이상치 플래그 추가."""
    try:
        data = json.loads(raw_file.read_text(encoding="utf-8"))
        updated = False

        for card in data.get("cards", []):
            cid = card.get("id", "")

            # market_avg_usd → market_avg_krw
            usd = card.get("market_avg_usd") or card.get("avg_sold_usd")
            if usd and "market_avg_krw" not in card:
                krw = int(usd * rate)
                card["market_avg_krw"] = krw
                updated = True

                # 이상치 확인
                if check_price_anomaly(cid, krw, prev_prices):
                    flags = card.get("warning_flags", [])
                    if "price_anomaly" not in flags:
                        flags.append("price_anomaly")
                        card["warning_flags"] = flags
                        updated = True

            # raw_usd → raw_krw
            raw_usd = card.get("raw_usd")
            if raw_usd and "raw_krw" not in card:
                card["raw_krw"] = int(raw_usd * rate)
                updated = True

            # graded 등급별 USD → KRW
            for graded_entry in card.get("graded", []):
                if "price_usd" in graded_entry and "price_krw" not in graded_entry:
                    graded_entry["price_krw"] = int(graded_entry["price_usd"] * rate)
                    updated = True

            # graded_sold USD → KRW
            for sold_entry in card.get("graded_sold", []):
                if "avg_sold_usd" in sold_entry and "avg_sold_krw" not in sold_entry:
                    sold_entry["avg_sold_krw"] = int(sold_entry["avg_sold_usd"] * rate)
                    updated = True

        if updated:
            data["exchange_rate_used"] = rate
            raw_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[price_normalizer] {raw_file.name}: KRW 환산 완료")

    except Exception as e:
        print(f"[price_normalizer] {raw_file.name} 처리 실패: {e}")


def main():
    rate, fallback = load_exchange_rate()
    print(f"[price_normalizer] 환율: 1 USD = {rate} KRW (폴백: {fallback})")

    prev_prices = load_previous_prices()
    raw_dir = ROOT / "data/raw"

    # en 소스 파일들만 USD→KRW 환산 대상
    en_sources = ["tcgplayer", "pricecharting", "ebay"]
    target_files = []
    for src in en_sources:
        f = raw_dir / f"cards_{src}.json"
        if f.exists():
            target_files.append(f)

    print(f"[price_normalizer] {len(target_files)}개 파일 처리")
    for f in target_files:
        normalize_card_prices(f, rate, prev_prices)

    print("[price_normalizer] 완료")


if __name__ == "__main__":
    main()
