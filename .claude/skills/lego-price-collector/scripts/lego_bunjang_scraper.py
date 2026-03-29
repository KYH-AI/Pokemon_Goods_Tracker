#!/usr/bin/env python3
"""번개장터에서 포켓몬 레고 세트 중고 시세 수집."""
import json
import re
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 번들 판매 감지 패턴 (여러 세트 묶음 매물 제외)
BUNDLE_PATTERNS = [
    r"\d{5}[^\d]{1,20}\d{5}",  # 두 개 이상의 5자리 세트번호 (사이 20자 이내)
    r"[+&]\s*\d{5}",
    r"\d{5}\s*[+&]",
    r"일괄",
    r"묶음",
    r"세트\s*두",
    r"\d+개\s*[+&]",
]


def is_bundle(name: str, price: int, official_price: int | None) -> bool:
    """번들 매물 여부 판단."""
    # 5자리 세트번호가 2개 이상 있으면 번들
    five_digit_nums = re.findall(r'\b\d{5}\b', name)
    if len(set(five_digit_nums)) >= 2:
        return True
    for pat in BUNDLE_PATTERNS:
        if re.search(pat, name):
            return True
    # 공식가 대비 2.5배 이상이면 번들 의심
    if official_price and price > official_price * 2.5:
        return True
    return False


def search_bunjang(lego_item: dict) -> dict:
    set_number = lego_item.get("set_number", "")
    official_price = lego_item.get("official_price_krw")
    keywords = lego_item.get("bunjang_search_keywords", [f"레고 {set_number}"])

    time.sleep(1 + random.uniform(0, 1))

    all_listings = []
    seen_pids = set()

    for keyword in keywords[:2]:  # 키워드 최대 2개
        try:
            url = f"https://api.bunjang.co.kr/api/1/find_v2.json?q={requests.utils.quote(keyword)}&n=20&page=0"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 403:
                print(f"  [BLOCKED] 번개장터: HTTP 403")
                return {"id": lego_item["id"], "status": "blocked"}
            if resp.status_code != 200:
                continue

            items = resp.json().get("list", [])
            for item in items:
                pid = item.get("pid", "")
                if pid in seen_pids:
                    continue
                seen_pids.add(pid)

                name = item.get("name", "")
                price_str = item.get("price", "0")
                try:
                    price = int(price_str)
                except (ValueError, TypeError):
                    continue
                if price < 5000:
                    continue

                # 세트번호가 상품명에 없으면 스킵 (관련 없는 매물)
                if set_number not in name and set_number not in item.get("description", ""):
                    continue

                if is_bundle(name, price, official_price):
                    continue

                all_listings.append({
                    "pid": pid,
                    "name": name,
                    "price_krw": price,
                    "thumbnail": item.get("image", ""),
                    "updated_at": item.get("update_time", ""),
                })

        except requests.RequestException as e:
            print(f"  [ERROR] 번개장터 {lego_item['id']}: {e}")

    if not all_listings:
        print(f"  [WARN] {lego_item['id']}: 번개장터 매물 없음")
        return {"id": lego_item["id"], "status": "no_results"}

    prices = [l["price_krw"] for l in all_listings]
    avg_krw = int(sum(prices) / len(prices))
    min_krw = min(prices)
    max_krw = max(prices)

    print(f"  {lego_item['id']}: {len(prices)}건 | {min_krw:,}~{max_krw:,}원 | 평균 {avg_krw:,}원")

    return {
        "id": lego_item["id"],
        "status": "ok",
        "bunjang_avg_krw": avg_krw,
        "bunjang_min_krw": min_krw,
        "bunjang_max_krw": max_krw,
        "bunjang_count": len(prices),
        "bunjang_listings": all_listings[:3],
    }


def main():
    watchlist = json.loads((ROOT / "config/watchlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))

    if not sources.get("lego_sources", {}).get("bunjang", {}).get("enabled", True):
        print("[lego_bunjang] 비활성화, 스킵")
        sys.exit(0)

    lego_items = watchlist.get("lego", [])
    print(f"[lego_bunjang] {len(lego_items)}개 세트 수집")

    results = []
    for item in lego_items:
        print(f"  → {item['id']}")
        result = search_bunjang(item)
        results.append(result)

    output = {
        "scraped_at": datetime.now(KST).isoformat(),
        "source": "bunjang",
        "sets": results,
    }

    out = ROOT / "data/raw/lego_bunjang.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[lego_bunjang] 완료 → {out}")


if __name__ == "__main__":
    main()
