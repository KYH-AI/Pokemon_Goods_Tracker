#!/usr/bin/env python3
"""BrickSet API v3로 레고 세트 단종 여부 수집."""
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
API_BASE = "https://brickset.com/api/v3.asmx"


def fetch_set_info(set_number: str, api_key: str) -> dict:
    """BrickSet API에서 세트 정보 조회."""
    bricklink_id = f"{set_number}-1"
    params = {
        "apiKey": api_key,
        "userHash": "",
        "params": json.dumps({"setNumber": bricklink_id}),
    }
    try:
        resp = requests.get(f"{API_BASE}/getSets", params=params, timeout=15)
        if resp.status_code != 200:
            print(f"  [ERROR] BrickSet HTTP {resp.status_code} (set {set_number})")
            return {}
        data = resp.json()
        if data.get("status") != "success":
            print(f"  [ERROR] BrickSet API 오류: {data.get('message', '')}")
            return {}
        sets = data.get("sets", [])
        if not sets:
            print(f"  [WARN] BrickSet: {set_number} 검색 결과 없음")
            return {}
        return sets[0]
    except requests.RequestException as e:
        print(f"  [ERROR] BrickSet {set_number}: {e}")
        return {}


def parse_retired(set_data: dict) -> bool:
    """단종 여부 파싱."""
    availability = set_data.get("availability", "")
    if "Retired" in availability or "retired" in availability.lower():
        return True
    lego_com = set_data.get("LEGOCom", {})
    for region in lego_com.values() if isinstance(lego_com, dict) else []:
        if isinstance(region, dict) and "retired" in str(region.get("availability", "")).lower():
            return True
    return False


def main():
    api_key = os.environ.get("BRICKSET_API_KEY", "")
    if not api_key:
        print("[brickset] BRICKSET_API_KEY 미설정, 스킵")
        sys.exit(0)

    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    if not sources.get("lego_sources", {}).get("brickset", {}).get("enabled", True):
        print("[brickset] 비활성화, 스킵")
        sys.exit(0)

    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    lego_items = watchlist.get("lego", [])
    print(f"[brickset] {len(lego_items)}개 세트 수집")

    results = []
    for item in lego_items:
        set_number = item.get("set_number", "")
        print(f"  → {item['id']} ({set_number})")
        time.sleep(1)

        set_data = fetch_set_info(set_number, api_key)
        if not set_data:
            results.append({"id": item["id"], "status": "no_results"})
            continue

        retired = parse_retired(set_data)
        result = {
            "id": item["id"],
            "set_number": set_number,
            "status": "ok",
            "retired": retired,
        }
        # 출시연도, 피스 수는 있으면 추가 (watchlist에 없는 정보)
        if set_data.get("year"):
            result["year"] = set_data["year"]
        if set_data.get("pieces"):
            result["pieces"] = set_data["pieces"]

        status_str = "단종" if retired else "판매중"
        print(f"    {status_str} | 출시연도: {result.get('year', '?')} | 피스: {result.get('pieces', '?')}")
        results.append(result)

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "brickset",
        "sets": results,
    }

    out = ROOT / "data/raw/lego_brickset.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[brickset] 완료 → {out}")


if __name__ == "__main__":
    main()
