#!/usr/bin/env python3
"""
config/card_name_map.json 매핑 테이블로 영문→한국어 카드명 변환.
미매핑 카드를 data/raw/unmapped_cards.json에 저장.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent


def normalize_en_name(name: str) -> str:
    """영문 카드명 소문자 정규화."""
    return name.strip().lower()


def main():
    map_path = ROOT / "config/card_name_map.json"
    watchlist_path = ROOT / "config/watchlist.json"
    raw_dir = ROOT / "data/raw"

    card_map_data = json.loads(map_path.read_text(encoding="utf-8"))
    mappings: dict = card_map_data.get("mappings", {})

    watchlist = json.loads(watchlist_path.read_text(encoding="utf-8"))
    all_cards = watchlist.get("cards", [])

    # watchlist 기반 미매핑 카드 탐지
    unmapped = []
    for card in all_cards:
        en_name = card.get("name_en", "")
        if not en_name:
            continue
        key = normalize_en_name(en_name)
        if key not in mappings and not card.get("name_ko"):
            unmapped.append({"id": card["id"], "name_en": en_name, "key": key})

    # raw 수집 파일들에서도 미매핑 카드 탐지
    raw_files = list(raw_dir.glob("cards_*.json"))
    for raw_file in raw_files:
        try:
            data = json.loads(raw_file.read_text(encoding="utf-8"))
            for card_entry in data.get("cards", []):
                en_name = card_entry.get("name_en", "")
                if not en_name:
                    continue
                key = normalize_en_name(en_name)
                if key not in mappings:
                    if not any(u["key"] == key for u in unmapped):
                        unmapped.append({"id": card_entry.get("id", ""), "name_en": en_name, "key": key})
        except Exception:
            continue

    # 미매핑 파일 저장
    unmapped_path = raw_dir / "unmapped_cards.json"
    if unmapped:
        unmapped_path.write_text(json.dumps(unmapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[card_name_mapper] 미매핑 카드 {len(unmapped)}개 → {unmapped_path}")
    else:
        # 파일이 있다면 빈 배열로 초기화
        unmapped_path.write_text("[]", encoding="utf-8")
        print("[card_name_mapper] 미매핑 카드 없음")

    # raw 카드 파일에 name_ko 필드 추가
    for raw_file in raw_files:
        try:
            data = json.loads(raw_file.read_text(encoding="utf-8"))
            updated = False
            for card_entry in data.get("cards", []):
                en_name = card_entry.get("name_en", "")
                if not en_name:
                    continue
                key = normalize_en_name(en_name)
                if key in mappings and "name_ko" not in card_entry:
                    card_entry["name_ko"] = mappings[key]
                    updated = True

                # watchlist에서 name_ko 보완
                if "name_ko" not in card_entry:
                    for wc in all_cards:
                        if wc.get("id") == card_entry.get("id") and wc.get("name_ko"):
                            card_entry["name_ko"] = wc["name_ko"]
                            updated = True
                            break

            if updated:
                raw_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[card_name_mapper] name_ko 추가: {raw_file.name}")

        except Exception as e:
            print(f"[card_name_mapper] {raw_file.name} 처리 실패: {e}")

    print("[card_name_mapper] 완료")


if __name__ == "__main__":
    main()
