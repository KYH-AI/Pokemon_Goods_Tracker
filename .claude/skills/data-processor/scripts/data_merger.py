#!/usr/bin/env python3
"""
모든 raw 파일을 읽어 최종 스키마로 병합.
data/cards.json, data/lego.json, data/events.json 생성.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))


def load_json_safe(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [WARN] {path.name} 로드 실패: {e}")
        return None


def merge_cards() -> dict:
    """카드 시세 데이터 병합."""
    raw_dir = ROOT / "data/raw"
    watchlist = load_json_safe(ROOT / "config/watchlist.json")
    if not watchlist:
        return {"cards": [], "updated_at": datetime.now(KST).isoformat()}

    # 카드 ID별 인덱스 구성
    card_index = {c["id"]: c.copy() for c in watchlist.get("cards", [])}
    source_status = {}

    # 각 소스 데이터 병합
    source_files = {
        "tcgplayer": raw_dir / "cards_tcgplayer.json",
        "pricecharting": raw_dir / "cards_pricecharting.json",
        "ebay": raw_dir / "cards_ebay.json",
        "naver_cafe": raw_dir / "cards_kr_naver_parsed.json",
        "bunjang": raw_dir / "cards_bunjang.json",
        "daangn": raw_dir / "cards_daangn.json",
    }

    for source_name, src_file in source_files.items():
        data = load_json_safe(src_file)
        if not data:
            source_status[source_name] = "missing"
            continue

        source_status[source_name] = "ok"
        scraped_at = data.get("scraped_at", "")

        # TCGPlayer / PriceCharting / eBay 카드 데이터
        for card_entry in data.get("cards", []):
            cid = card_entry.get("id", "")
            if cid not in card_index:
                continue
            target = card_index[cid]
            status = card_entry.get("status", "ok")
            if status not in ("ok",):
                source_status[f"{source_name}_{cid}"] = status
                # error여도 thumbnail_url은 챙김 (pokemontcg_id fallback 포함)
                if source_name == "tcgplayer" and "thumbnail_url" in card_entry and "thumbnail_url" not in target:
                    target["thumbnail_url"] = card_entry["thumbnail_url"]
                continue

            if source_name == "tcgplayer":
                if "market_avg_usd" in card_entry:
                    target["tcgplayer_market_usd"] = card_entry["market_avg_usd"]
                if "market_avg_krw" in card_entry:
                    target["tcgplayer_market_krw"] = card_entry["market_avg_krw"]
                if "thumbnail_url" in card_entry and "thumbnail_url" not in target:
                    target["thumbnail_url"] = card_entry["thumbnail_url"]

            elif source_name == "pricecharting":
                if "raw_usd" in card_entry:
                    target["pc_raw_usd"] = card_entry["raw_usd"]
                if "raw_krw" in card_entry:
                    target["pc_raw_krw"] = card_entry["raw_krw"]
                if "graded" in card_entry:
                    target.setdefault("graded_prices", []).extend(card_entry["graded"])

            elif source_name == "ebay":
                if "avg_sold_usd" in card_entry:
                    target["ebay_avg_sold_usd"] = card_entry["avg_sold_usd"]
                if "recent_sold_count" in card_entry:
                    target["ebay_recent_sold_count"] = card_entry["recent_sold_count"]
                if "graded_sold" in card_entry:
                    target.setdefault("ebay_graded_sold", []).extend(card_entry["graded_sold"])

            elif source_name == "bunjang":
                if card_entry.get("avg_krw"):
                    target["bunjang_avg_krw"] = card_entry["avg_krw"]
                if "price_range_krw" in card_entry:
                    target["bunjang_price_range_krw"] = card_entry["price_range_krw"]
                if "listings" in card_entry:
                    target.setdefault("domestic_listings", []).extend(
                        [{**li, "source": "bunjang"} for li in card_entry["listings"][:3]]
                    )

            elif source_name == "daangn":
                if card_entry.get("avg_krw"):
                    target["daangn_avg_krw"] = card_entry["avg_krw"]
                if "listings" in card_entry:
                    target.setdefault("domestic_listings", []).extend(
                        [{**li, "source": "daangn"} for li in card_entry["listings"][:3]]
                    )

            target["last_seen_date"] = scraped_at[:10] if scraped_at else ""

        # 네이버 카페 파싱 결과
        if source_name == "naver_cafe":
            for parsed_result in data.get("results", []):
                for item in parsed_result.get("items", []):
                    hint = item.get("card_name_hint", "")
                    # 카드 ID 매핑 시도
                    for cid, target in card_index.items():
                        if hint and (
                            hint in target.get("name_ko", "")
                            or hint in target.get("name_en", "")
                        ):
                            target.setdefault("kr_cafe_prices", []).append(item)
                            break

    # 최종 avg_price_krw 계산
    now_str = datetime.now(KST).isoformat()
    final_cards = []
    for cid, card in card_index.items():
        prices_krw = []
        for price_key in ("tcgplayer_market_krw", "pc_raw_krw", "bunjang_avg_krw", "daangn_avg_krw"):
            v = card.get(price_key)
            if v and v > 0:
                prices_krw.append(v)

        if prices_krw:
            card["avg_price_krw"] = int(sum(prices_krw) / len(prices_krw))

        card["updated_at"] = now_str

        # null 값 제거
        clean_card = {k: v for k, v in card.items() if v is not None and v != ""}
        final_cards.append(clean_card)

    return {
        "updated_at": now_str,
        "source_status": source_status,
        "cards": final_cards,
    }


def merge_lego() -> dict:
    """레고 가격 데이터 병합."""
    raw_dir = ROOT / "data/raw"
    watchlist = load_json_safe(ROOT / "config/watchlist.json")
    if not watchlist:
        return {"sets": [], "updated_at": datetime.now(KST).isoformat()}

    lego_index = {item["id"]: item.copy() for item in watchlist.get("lego", [])}
    source_status = {}
    now_str = datetime.now(KST).isoformat()

    # BrickEconomy
    be_data = load_json_safe(raw_dir / "lego_brickeconomy.json")
    if be_data:
        source_status["brickeconomy"] = "ok"
        for entry in be_data.get("sets", []):
            sid = entry.get("id", "")
            if sid in lego_index:
                target = lego_index[sid]
                for k in ("used_usd", "used_krw", "new_usd", "new_krw", "premium_pct", "retired", "thumbnail_url"):
                    if k in entry:
                        target[k] = entry[k]
    else:
        source_status["brickeconomy"] = "missing"

    # LEGO 공식
    lo_data = load_json_safe(raw_dir / "lego_official.json")
    if lo_data:
        source_status["lego_official"] = "ok"
        for entry in lo_data.get("sets", []):
            sid = entry.get("id", "")
            if sid in lego_index:
                target = lego_index[sid]
                if "retail_price_krw" in entry:
                    target["retail_price_krw"] = entry["retail_price_krw"]
                if "in_stock" in entry:
                    target["in_stock"] = entry["in_stock"]
                if "thumbnail_url" in entry and "thumbnail_url" not in target:
                    target["thumbnail_url"] = entry["thumbnail_url"]
    else:
        source_status["lego_official"] = "missing"

    final_sets = []
    for sid, s in lego_index.items():
        s["updated_at"] = now_str
        clean = {k: v for k, v in s.items() if v is not None}
        final_sets.append(clean)

    return {
        "updated_at": now_str,
        "source_status": source_status,
        "sets": final_sets,
    }


def merge_events() -> dict:
    """이벤트 데이터 병합."""
    raw_dir = ROOT / "data/raw"
    now_str = datetime.now(KST).isoformat()
    today = datetime.now(KST).date().isoformat()

    # 중복 제거된 이벤트 우선, 없으면 각 파일에서 합산
    deduped = load_json_safe(raw_dir / "events_deduped.json")
    if deduped:
        all_events = deduped.get("events", [])
    else:
        all_events = []
        for fname in ("events_official.json", "events_community_classified.json", "events_community.json"):
            data = load_json_safe(raw_dir / fname)
            if data:
                all_events.extend(data.get("events", []))

    # 아카이브 분리 (30일 이전 종료 이벤트)
    active_events = []
    archived_events = []
    from datetime import datetime as dt
    archive_cutoff = (dt.now(KST).date() - timedelta(days=30)).isoformat()

    for event in all_events:
        end_date = event.get("end_date", event.get("start_date", ""))
        if end_date and end_date < archive_cutoff:
            event["event_status"] = "archived"
            archived_events.append(event)
        else:
            # event_status 갱신
            start = event.get("start_date", "")
            end = event.get("end_date", start)
            if end and end < today:
                event["event_status"] = "ended"
            elif start and start > today:
                event["event_status"] = "upcoming"
            else:
                event["event_status"] = "ongoing"
            active_events.append(event)

    # _source_file 등 내부 필드 제거
    def clean_event(e):
        return {k: v for k, v in e.items() if not k.startswith("_") and v is not None and v != ""}

    return {
        "updated_at": now_str,
        "events": [clean_event(e) for e in active_events],
        "archived_events": [clean_event(e) for e in archived_events],
    }


def main():
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    print("[data_merger] 카드 데이터 병합")
    cards_data = merge_cards()
    cards_path = data_dir / "cards.json"
    cards_path.write_text(json.dumps(cards_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[data_merger] cards.json 생성: {len(cards_data['cards'])}개 카드")

    print("[data_merger] 레고 데이터 병합")
    lego_data = merge_lego()
    lego_path = data_dir / "lego.json"
    lego_path.write_text(json.dumps(lego_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[data_merger] lego.json 생성: {len(lego_data['sets'])}개 세트")

    print("[data_merger] 이벤트 데이터 병합")
    events_data = merge_events()
    events_path = data_dir / "events.json"
    events_path.write_text(json.dumps(events_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[data_merger] events.json 생성: {len(events_data['events'])}개 이벤트")

    print("[data_merger] 완료")


if __name__ == "__main__":
    main()
