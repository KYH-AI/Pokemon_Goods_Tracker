#!/usr/bin/env python3
"""BrickEconomy API v1로 레고 중고/새상품 시세, 프리미엄율, 단종 여부 수집."""
import json
import os
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
API_BASE = "https://www.brickeconomy.com/api/v1"


def get_field(data: dict, *keys):
    """여러 키 이름 중 첫 번째로 존재하는 값 반환 (API 필드명 변경 대응)."""
    for key in keys:
        if key in data:
            return data[key]
    return None


def fetch_set(set_number: str, api_key: str) -> dict:
    """BrickEconomy API에서 세트 데이터 조회."""
    bricklink_id = f"{set_number}-1"
    url = f"{API_BASE}/sets/{bricklink_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code in (401, 403):
            print(f"  [AUTH ERROR] BrickEconomy API 키 오류: HTTP {resp.status_code}")
            return {"status": "auth_error"}
        if resp.status_code == 404:
            print(f"  [WARN] BrickEconomy: {set_number} 세트 없음")
            return {"status": "not_found"}
        if resp.status_code != 200:
            print(f"  [ERROR] BrickEconomy HTTP {resp.status_code} (set {set_number})")
            return {"status": f"http_{resp.status_code}"}
        return resp.json()
    except requests.RequestException as e:
        print(f"  [ERROR] BrickEconomy {set_number}: {e}")
        return {"status": "error"}


def parse_set_data(raw: dict, lego_item: dict, rate: float) -> dict:
    """API 응답에서 필요 필드 추출."""
    result = {
        "id": lego_item["id"],
        "set_number": lego_item.get("set_number", ""),
        "status": "ok",
    }

    # 새상품가 — API 필드명 후보 순서대로 탐색
    new_usd = get_field(raw, "new_price", "newPrice", "value_new", "retail_value", "retailValue")
    if new_usd is not None:
        try:
            result["new_usd"] = round(float(new_usd), 2)
            result["new_krw"] = int(float(new_usd) * rate)
        except (ValueError, TypeError):
            pass

    # 중고가
    used_usd = get_field(raw, "used_price", "usedPrice", "value_used", "secondary_value", "secondaryValue")
    if used_usd is not None:
        try:
            result["used_usd"] = round(float(used_usd), 2)
            result["used_krw"] = int(float(used_usd) * rate)
        except (ValueError, TypeError):
            pass

    # 프리미엄율
    premium = get_field(raw, "premium_pct", "premium", "appreciation", "growth", "price_premium", "pricePremium")
    if premium is not None:
        try:
            result["premium_pct"] = round(float(premium), 1)
        except (ValueError, TypeError):
            pass

    # 단종 여부
    retired = get_field(raw, "retired", "is_retired", "isRetired")
    if retired is not None:
        result["retired"] = bool(retired)
    else:
        # availability 필드에서 "Retired" 텍스트로 판단
        availability = get_field(raw, "availability", "status")
        if availability and "retired" in str(availability).lower():
            result["retired"] = True

    # 로그
    parts = []
    if "new_usd" in result:
        parts.append(f"새상품 ${result['new_usd']}")
    if "used_usd" in result:
        parts.append(f"중고 ${result['used_usd']}")
    if "premium_pct" in result:
        sign = "+" if result["premium_pct"] >= 0 else ""
        parts.append(f"프리미엄 {sign}{result['premium_pct']}%")
    if "retired" in result:
        parts.append("단종" if result["retired"] else "판매중")
    print(f"    {' | '.join(parts) if parts else '데이터 없음'}")

    return result


def main():
    api_key = os.environ.get("BRICKECONOMY_API_KEY", "")
    if not api_key:
        print("[brickeconomy] BRICKECONOMY_API_KEY 미설정, 스킵")
        sys.exit(0)

    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    if not sources.get("lego_sources", {}).get("brickeconomy", {}).get("enabled", True):
        print("[brickeconomy] 비활성화, 스킵")
        sys.exit(0)

    rate_path = ROOT / "config/exchange_rate.json"
    rate = float(json.loads(rate_path.read_text(encoding="utf-8")).get("rate", 1500.0)) if rate_path.exists() else 1500.0

    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    lego_items = watchlist.get("lego", [])
    print(f"[brickeconomy] {len(lego_items)}개 세트 수집 (환율: {rate} KRW/USD)")

    results = []
    auth_failed = False

    for item in lego_items:
        if auth_failed:
            results.append({"id": item["id"], "status": "skipped"})
            continue

        print(f"  → {item['id']}")
        time.sleep(1 + random.uniform(0, 0.5))

        raw = fetch_set(item.get("set_number", ""), api_key)

        if raw.get("status") == "auth_error":
            auth_failed = True
            results.append({"id": item["id"], "status": "auth_error"})
            continue

        if raw.get("status") in ("not_found", "error") or raw.get("status", "").startswith("http_"):
            results.append({"id": item["id"], "status": raw.get("status", "error")})
            continue

        results.append(parse_set_data(raw, item, rate))

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
