#!/usr/bin/env python3
"""소스 기반 규칙으로 에디션(kr/en) 태깅."""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent

# 소스명 → 에디션 매핑 규칙
SOURCE_EDITION_MAP = {
    "tcgplayer": "en",
    "pricecharting": "en",
    "ebay": "en",
    "naver_cafe": "kr",
    "bunjang": "kr",
    "daangn": "kr",
    "brickeconomy": "both",   # 레고는 글로벌
    "lego_official": "kr",
}


def infer_edition_from_filename(filename: str) -> str:
    """파일명에서 소스 추론하여 에디션 반환."""
    name = filename.lower()
    for source, edition in SOURCE_EDITION_MAP.items():
        if source in name:
            return edition
    return "unknown"


def tag_cards_in_file(raw_file: Path):
    """raw 파일의 카드 항목에 edition 필드 확인/추가."""
    try:
        data = json.loads(raw_file.read_text(encoding="utf-8"))
        updated = False

        # 파일 레벨 edition
        file_edition = data.get("edition", infer_edition_from_filename(raw_file.stem))

        for card in data.get("cards", []):
            if "edition" not in card:
                card["edition"] = file_edition
                updated = True

            # 개별 리스팅에도 태깅
            for listing in card.get("listings", []):
                if "edition" not in listing:
                    listing["edition"] = file_edition
                    updated = True

        if updated:
            raw_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[edition_tagger] {raw_file.name}: edition={file_edition} 태깅 완료")
        else:
            print(f"[edition_tagger] {raw_file.name}: 이미 태깅됨, 스킵")

    except Exception as e:
        print(f"[edition_tagger] {raw_file.name} 처리 실패: {e}")


def main():
    raw_dir = ROOT / "data/raw"
    card_files = list(raw_dir.glob("cards_*.json"))
    print(f"[edition_tagger] {len(card_files)}개 파일 처리")

    for f in card_files:
        tag_cards_in_file(f)

    print("[edition_tagger] 완료")


if __name__ == "__main__":
    main()
