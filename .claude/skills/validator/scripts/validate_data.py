#!/usr/bin/env python3
"""
data/cards.json, lego.json, events.json 스키마 검증.
가격 이상치 탐지(±300%). 30일 이전 이벤트 아카이브 플래그.
logs/validate_{timestamp}.json 출력. 스키마 실패 시 sys.exit(1).
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
KST = timezone(timedelta(hours=9))
LOGS_DIR = ROOT / "logs"

# 스키마: 필수 필드 및 타입 정의
CARDS_SCHEMA = {
    "required_top": ["updated_at", "cards"],
    "card_required": ["id"],
    "card_field_types": {
        "id": str,
        "name_en": str,
        "avg_price_krw": (int, float),
    },
}

LEGO_SCHEMA = {
    "required_top": ["updated_at", "sets"],
    "set_required": ["id"],
}

EVENTS_SCHEMA = {
    "required_top": ["updated_at", "events"],
    "event_required": ["id", "title"],
    "event_field_types": {
        "id": str,
        "title": str,
    },
}


def load_previous_prices(data_file: Path) -> dict:
    """이전 cards.json 백업에서 avg_price_krw 로드 (이상치 비교용)."""
    backup = data_file.parent / (data_file.stem + "_prev.json")
    if not backup.exists():
        return {}
    try:
        prev = json.loads(backup.read_text(encoding="utf-8"))
        return {c["id"]: c.get("avg_price_krw") for c in prev.get("cards", []) if c.get("avg_price_krw")}
    except Exception:
        return {}


def validate_cards(data: dict, prev_prices: dict) -> tuple:
    """카드 데이터 검증. (errors, warnings) 반환."""
    errors = []
    warnings = []

    for field in CARDS_SCHEMA["required_top"]:
        if field not in data:
            errors.append(f"cards.json: 필수 최상위 필드 누락: {field}")

    for card in data.get("cards", []):
        cid = card.get("id", "UNKNOWN")

        for req_field in CARDS_SCHEMA["card_required"]:
            if req_field not in card:
                errors.append(f"카드 {cid}: 필수 필드 누락: {req_field}")

        # 타입 검증
        for field, expected_type in CARDS_SCHEMA.get("card_field_types", {}).items():
            if field in card and not isinstance(card[field], expected_type):
                errors.append(f"카드 {cid}: {field} 타입 오류 (expected {expected_type}, got {type(card[field]).__name__})")

        # null 값 검사
        for k, v in card.items():
            if v is None:
                errors.append(f"카드 {cid}: null 값 포함 (필드: {k})")

        # 가격 이상치 탐지 (±300%)
        current_price = card.get("avg_price_krw")
        if current_price and cid in prev_prices:
            prev_price = prev_prices[cid]
            if prev_price and prev_price > 0:
                change_pct = abs(current_price - prev_price) / prev_price * 100
                if change_pct >= 300:
                    warnings.append(
                        f"카드 {cid}: 가격 이상치 ({prev_price:,}원 → {current_price:,}원, {change_pct:.0f}% 변동)"
                    )
                    # 경고 플래그 추가
                    flags = card.get("warning_flags", [])
                    if "price_anomaly_300pct" not in flags:
                        flags.append("price_anomaly_300pct")
                        card["warning_flags"] = flags

    return errors, warnings


def validate_lego(data: dict) -> tuple:
    errors = []
    warnings = []

    for field in LEGO_SCHEMA["required_top"]:
        if field not in data:
            errors.append(f"lego.json: 필수 최상위 필드 누락: {field}")

    for item in data.get("sets", []):
        sid = item.get("id", "UNKNOWN")
        for req_field in LEGO_SCHEMA["set_required"]:
            if req_field not in item:
                errors.append(f"레고 {sid}: 필수 필드 누락: {req_field}")
        for k, v in item.items():
            if v is None:
                errors.append(f"레고 {sid}: null 값 포함 (필드: {k})")

    return errors, warnings


def validate_events(data: dict) -> tuple:
    errors = []
    warnings = []
    today = datetime.now(KST).date().isoformat()
    archive_cutoff = (datetime.now(KST).date() - timedelta(days=30)).isoformat()

    for field in EVENTS_SCHEMA["required_top"]:
        if field not in data:
            errors.append(f"events.json: 필수 최상위 필드 누락: {field}")

    for event in data.get("events", []):
        eid = event.get("id", "UNKNOWN")

        for req_field in EVENTS_SCHEMA["event_required"]:
            if req_field not in event:
                errors.append(f"이벤트 {eid}: 필수 필드 누락: {req_field}")

        for k, v in event.items():
            if v is None:
                errors.append(f"이벤트 {eid}: null 값 포함 (필드: {k})")

        # 30일 이전 이벤트 경고
        end_date = event.get("end_date", event.get("start_date", ""))
        if end_date and end_date < archive_cutoff:
            warnings.append(f"이벤트 {eid}: 30일 이전 종료 이벤트 (아카이브 권장, end_date: {end_date})")

        # updated_at 신선도 (24시간)
        updated_at = data.get("updated_at", "")
        if updated_at:
            try:
                updated_dt = datetime.fromisoformat(updated_at)
                if (datetime.now(KST) - updated_dt).total_seconds() > 86400:
                    warnings.append(f"events.json: 데이터 신선도 경고 (updated_at: {updated_at})")
            except ValueError:
                pass

    return errors, warnings


def check_data_freshness(data: dict, filename: str) -> list:
    """updated_at 24시간 이내 확인."""
    warnings = []
    updated_at = data.get("updated_at", "")
    if not updated_at:
        warnings.append(f"{filename}: updated_at 필드 없음")
        return warnings
    try:
        dt = datetime.fromisoformat(updated_at)
        age_hours = (datetime.now(KST) - dt).total_seconds() / 3600
        if age_hours > 24:
            warnings.append(f"{filename}: 데이터 오래됨 ({age_hours:.1f}시간 경과)")
    except ValueError:
        warnings.append(f"{filename}: updated_at 형식 오류: {updated_at}")
    return warnings


def main():
    data_dir = ROOT / "data"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M")
    log_path = LOGS_DIR / f"validate_{timestamp}.json"

    all_errors = []
    all_warnings = []

    # cards.json
    cards_path = data_dir / "cards.json"
    if not cards_path.exists():
        all_errors.append("cards.json 파일 없음")
    else:
        cards_data = json.loads(cards_path.read_text(encoding="utf-8"))
        prev_prices = load_previous_prices(cards_path)
        e, w = validate_cards(cards_data, prev_prices)
        all_errors.extend(e)
        all_warnings.extend(w)
        all_warnings.extend(check_data_freshness(cards_data, "cards.json"))
        # 이상치 플래그가 추가됐으면 저장
        if w:
            cards_path.write_text(json.dumps(cards_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # lego.json
    lego_path = data_dir / "lego.json"
    if not lego_path.exists():
        all_errors.append("lego.json 파일 없음")
    else:
        lego_data = json.loads(lego_path.read_text(encoding="utf-8"))
        e, w = validate_lego(lego_data)
        all_errors.extend(e)
        all_warnings.extend(w)
        all_warnings.extend(check_data_freshness(lego_data, "lego.json"))

    # events.json
    events_path = data_dir / "events.json"
    if not events_path.exists():
        all_errors.append("events.json 파일 없음")
    else:
        events_data = json.loads(events_path.read_text(encoding="utf-8"))
        e, w = validate_events(events_data)
        all_errors.extend(e)
        all_warnings.extend(w)

    # 결과 로그 작성
    log_data = {
        "validated_at": datetime.now(KST).isoformat(),
        "passed": len(all_errors) == 0,
        "error_count": len(all_errors),
        "warning_count": len(all_warnings),
        "errors": all_errors,
        "warnings": all_warnings,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 결과 출력
    print(f"[validate] 검증 완료: 에러 {len(all_errors)}개, 경고 {len(all_warnings)}개")
    if all_errors:
        for err in all_errors:
            print(f"  [ERROR] {err}")
    if all_warnings:
        for w in all_warnings:
            print(f"  [WARN] {w}")

    print(f"[validate] 로그: {log_path}")

    # 스키마 에러 시 파이프라인 중단
    if all_errors:
        print("[validate] 스키마 에러 발생 → 배포 중단")
        sys.exit(1)

    print("[validate] 검증 통과")


if __name__ == "__main__":
    main()
