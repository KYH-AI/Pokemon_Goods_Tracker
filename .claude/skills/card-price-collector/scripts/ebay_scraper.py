#!/usr/bin/env python3
"""eBay Browse API로 영어판 카드 현재 시세 수집 (OAuth Client Credentials)."""
import base64
import json
import os
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

OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

_ebay_blocked = False
_access_token = None


def get_token(app_id: str, cert_id: str) -> str | None:
    """OAuth Client Credentials로 Access Token 발급."""
    credential = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
    try:
        resp = requests.post(
            OAUTH_URL,
            headers={
                "Authorization": f"Basic {credential}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=f"grant_type=client_credentials&scope={SCOPE}",
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"  [ERROR] eBay 토큰 발급 실패: HTTP {resp.status_code} {resp.text[:200]}")
            return None
        return resp.json().get("access_token")
    except Exception as e:
        print(f"  [ERROR] eBay 토큰 발급 예외: {e}")
        return None


def search_items(token: str, keyword: str, max_results: int = 20) -> list:
    """Browse API로 현재 판매 중인 리스팅 검색."""
    global _ebay_blocked
    if _ebay_blocked:
        return []

    time.sleep(1)
    try:
        resp = requests.get(
            BROWSE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            params={
                "q": keyword,
                "filter": "buyingOptions:{FIXED_PRICE},conditions:{USED|VERY_GOOD|LIKE_NEW|NEW}",
                "limit": max_results,
                "category_ids": "183454",  # Trading Cards
            },
            timeout=10,
        )
        if resp.status_code in (403, 429):
            _ebay_blocked = True
            print(f"  [BLOCKED] eBay Browse API: HTTP {resp.status_code} → 이후 모든 요청 스킵")
            return []
        if resp.status_code != 200:
            print(f"  [WARN] eBay Browse API HTTP {resp.status_code} (keyword={keyword!r})")
            return []

        items = resp.json().get("itemSummaries", [])
        results = []
        for item in items:
            price_info = item.get("price", {})
            currency = price_info.get("currency", "USD")
            if currency != "USD":
                continue
            try:
                price = round(float(price_info.get("value", 0)), 2)
            except (ValueError, TypeError):
                continue
            if not price:
                continue
            results.append({
                "title": item.get("title", ""),
                "sold_price_usd": price,
                "sold_date": "",  # Browse API는 판매 완료 날짜 미제공
            })
        return results
    except requests.exceptions.Timeout:
        _ebay_blocked = True
        print("  [BLOCKED] eBay Browse API: timeout → 이후 모든 요청 스킵")
        return []
    except Exception as e:
        print(f"  [ERROR] eBay Browse API 파싱 실패: {e}")
        return []


def collect_card(card: dict, ebay_config: dict, token: str) -> dict:
    result = {
        "id": card["id"],
        "status": "ok",
        "sold_listings": [],
        "graded_sold": [],
    }
    keywords = card.get("ebay_search_keywords", [card.get("name_en", card["id"])])
    max_per_card = ebay_config.get("max_results_per_card", 10)

    # 비등급 수집
    for kw in keywords[:2]:
        listings = search_items(token, kw, max_per_card)
        result["sold_listings"].extend(listings)
        if listings:
            break

    # 등급별 수집
    grading_patterns = ebay_config.get("grading_search_patterns", {})
    for company, grades in grading_patterns.items():
        for grade, search_terms in grades.items():
            for base_kw in keywords[:1]:
                combined_kw = f"{base_kw} {search_terms[0]}"
                listings = search_items(token, combined_kw, 5)
                if listings:
                    prices = [li["sold_price_usd"] for li in listings]
                    result["graded_sold"].append({
                        "company": company,
                        "grade": grade,
                        "recent_sold_count": len(listings),
                        "avg_sold_usd": round(sum(prices) / len(prices), 2),
                        "last_sold_date": "",
                    })
                    break

    if result["sold_listings"]:
        prices = sorted(li["sold_price_usd"] for li in result["sold_listings"])
        # IQR 기반 이상치 제거
        if len(prices) >= 4:
            q1 = prices[len(prices) // 4]
            q3 = prices[(len(prices) * 3) // 4]
            iqr = q3 - q1
            prices = [p for p in prices if q1 - 1.5 * iqr <= p <= q3 + 1.5 * iqr]
        if prices:
            result["avg_sold_usd"] = round(sum(prices) / len(prices), 2)
            result["recent_sold_count"] = len(prices)

    return result


def main():
    app_id = os.environ.get("EBAY_APP_ID", "")
    cert_id = os.environ.get("EBAY_CERT_ID", "")
    if not app_id or not cert_id:
        print("[ebay] EBAY_APP_ID / EBAY_CERT_ID 미설정 → 스킵")
        sys.exit(0)

    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    ebay_config = json.loads((ROOT / "config/ebay_config.json").read_text(encoding="utf-8"))

    if not sources["card_sources"]["ebay"].get("enabled", True):
        print("[ebay] 비활성화 → 스킵")
        sys.exit(0)

    token = get_token(app_id, cert_id)
    if not token:
        print("[ebay] Access Token 발급 실패 → 스킵")
        sys.exit(0)
    print("[ebay] Access Token 발급 완료")

    cards = [c for c in watchlist["cards"] if "en" in c.get("editions", [])]
    print(f"[ebay] {len(cards)}개 카드 수집")

    results = [collect_card(c, ebay_config, token) for c in cards]

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
