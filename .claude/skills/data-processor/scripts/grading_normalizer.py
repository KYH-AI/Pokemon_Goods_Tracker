#!/usr/bin/env python3
"""
grading_config.json 기준으로 PSA/BGS 등급 표기 정규화.
"PSA10", "PSA 10", "PSA GEM-MT 10" → {"company": "PSA", "grade": "10"}
미정의 등급 제거.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent


def load_valid_grades() -> dict:
    """grading_config.json에서 유효한 등급 목록 로드."""
    config_path = ROOT / "config/grading_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    valid = {}
    for company, data in config.get("grading_companies", {}).items():
        valid[company] = set(data.get("grades", []))
    return valid


def normalize_grade_entry(entry: dict, valid_grades: dict):
    """단일 등급 항목 정규화. 유효하지 않으면 None 반환."""
    company = entry.get("company", entry.get("grade_company", "")).upper().strip()
    grade_raw = str(entry.get("grade", "")).strip()

    # 회사명 정규화
    if company not in valid_grades:
        # 텍스트에서 회사명 추출
        for c in valid_grades:
            if c in company:
                company = c
                break
        else:
            return None

    # 등급 정규화: "10", "9.5" 형태로 통일
    grade_clean = re.sub(r"[^0-9.]", "", grade_raw)
    # "GEM MINT 10" → "10"
    num_match = re.search(r"(\d+\.?\d*)", grade_raw)
    if num_match and not grade_clean:
        grade_clean = num_match.group(1)

    if grade_clean not in valid_grades.get(company, set()):
        return None

    normalized = {
        "company": company,
        "grade": grade_clean,
    }
    # 원래 필드 중 가격 관련만 유지
    for price_key in ("price_usd", "price_krw", "avg_sold_usd", "recent_sold_count", "last_sold_date"):
        if price_key in entry:
            normalized[price_key] = entry[price_key]

    return normalized


def parse_graded_text(text: str, valid_grades: dict) -> list:
    """자유 텍스트에서 등급 정보 파싱 (예: "PSA 10 12만")."""
    results = []
    for company in valid_grades:
        # "PSA10" 또는 "PSA 10" 또는 "PSA GEM 10" 패턴
        pattern = rf"{company}\s*(?:GEM\s*MINT|GEM-MT|MINT|NM-MT\+?)?\s*(\d+\.?\d*)"
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            grade = m.group(1)
            if grade in valid_grades.get(company, set()):
                results.append({"company": company, "grade": grade})
    return results


def normalize_file(raw_file: Path, valid_grades: dict):
    """raw 파일의 graded 항목 정규화."""
    try:
        data = json.loads(raw_file.read_text(encoding="utf-8"))
        updated = False

        for card in data.get("cards", []):
            # graded 배열 정규화
            if "graded" in card:
                normalized_graded = []
                for entry in card["graded"]:
                    normed = normalize_grade_entry(entry, valid_grades)
                    if normed:
                        normalized_graded.append(normed)
                if len(normalized_graded) != len(card["graded"]):
                    updated = True
                card["graded"] = normalized_graded

            # graded_sold 배열 정규화
            if "graded_sold" in card:
                normalized_sold = []
                for entry in card["graded_sold"]:
                    normed = normalize_grade_entry(entry, valid_grades)
                    if normed:
                        normalized_sold.append(normed)
                if len(normalized_sold) != len(card["graded_sold"]):
                    updated = True
                card["graded_sold"] = normalized_sold

        if updated:
            raw_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[grading_normalizer] {raw_file.name}: 정규화 완료")
        else:
            print(f"[grading_normalizer] {raw_file.name}: 변경 없음")

    except Exception as e:
        print(f"[grading_normalizer] {raw_file.name} 처리 실패: {e}")


def main():
    valid_grades = load_valid_grades()
    raw_dir = ROOT / "data/raw"

    target_files = list(raw_dir.glob("cards_*.json")) + list(raw_dir.glob("*_parsed.json"))
    print(f"[grading_normalizer] {len(target_files)}개 파일 처리")

    for f in target_files:
        normalize_file(f, valid_grades)

    print("[grading_normalizer] 완료")


if __name__ == "__main__":
    main()
