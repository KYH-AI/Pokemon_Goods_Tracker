#!/usr/bin/env python3
"""
data-enrichment-agent 실행 스크립트.
GitHub Actions에서 호출. ANTHROPIC_API_KEY 환경변수 필요.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent  # 프로젝트 루트

try:
    import anthropic
except ImportError:
    print("anthropic 패키지 필요: pip install anthropic")
    sys.exit(1)


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def task1_map_card_names(client: anthropic.Anthropic):
    """미매핑 카드명 한국어 추론"""
    unmapped_path = ROOT / "data/raw/unmapped_cards.json"
    map_path = ROOT / "config/card_name_map.json"

    unmapped = load_json(unmapped_path)
    if not unmapped:
        print("[Task1] 미매핑 카드 없음, 스킵")
        return

    card_map = load_json(map_path) or {"mappings": {}}

    prompt = f"""포켓몬 TCG 카드의 영문명을 한국어 공식 번역명으로 변환해주세요.

변환 규칙:
- 포켓몬 공식 한국어 번역명 사용 (팬 별칭 금지)
- 확신 없으면 영문명 그대로 유지
- "ex", "V", "VMAX", "SAR", "AR" 등 접미사는 그대로 유지

영문 카드명 목록:
{json.dumps(unmapped, ensure_ascii=False, indent=2)}

결과를 JSON 형식으로 반환 (영문명 소문자: 한국어명):
{{"영문명 소문자": "한국어명", ...}}"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        response_text = message.content[0].text
        # JSON 부분 추출
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        new_mappings = json.loads(response_text[start:end])
        card_map["mappings"].update(new_mappings)
        card_map["_last_updated"] = datetime.now().strftime("%Y-%m-%d")
        save_json(map_path, card_map)
        print(f"[Task1] {len(new_mappings)}개 카드명 매핑 추가")
    except Exception as e:
        print(f"[Task1] 파싱 실패: {e}")


def task2_parse_naver_prices(client: anthropic.Anthropic):
    """네이버 카페 시세글 비정형 텍스트 파싱"""
    raw_path = ROOT / "data/raw/cards_kr_naver.json"
    out_path = ROOT / "data/raw/cards_kr_naver_parsed.json"

    raw = load_json(raw_path)
    if not raw or not raw.get("articles"):
        print("[Task2] 네이버 카페 게시글 없음, 스킵")
        return

    parsed_results = []
    for article in raw["articles"]:
        prompt = f"""포켓몬 카드 시세 게시글에서 구조화된 데이터를 추출해주세요.

게시글 제목: {article.get('title', '')}
게시글 내용: {article.get('content_preview', '')}

추출 규칙:
- 에디션: 한국판/국내판 → "kr", 영문판/영어판/해외판 → "en", 불명확 → "kr" 기본값
- 등급: PSA 10 → grade_company: "PSA", grade: "10"
- 미채점/미그레이딩/raw → grade: "raw"
- 가격: 원 단위 정수. "12만" → 120000, "15만5천" → 155000
- 가격 불명확 시 포함하지 않음

JSON 형식으로 반환 (가격 없으면 빈 배열):
{{
  "article_url": "{article.get('url', '')}",
  "items": [
    {{"card_name_hint": "...", "edition": "kr", "grade": "raw", "price_krw": 0}}
  ]
}}"""

        try:
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            result = json.loads(response_text[start:end])
            if result.get("items"):
                parsed_results.append(result)
        except Exception as e:
            print(f"[Task2] 게시글 파싱 실패: {e}")
            continue

    save_json(out_path, {"parsed_at": datetime.now().isoformat(), "results": parsed_results})
    print(f"[Task2] {len(parsed_results)}개 게시글 파싱 완료")


def task3_deduplicate_events(client: anthropic.Anthropic):
    """이벤트 중복 제거 판단"""
    candidates_path = ROOT / "data/raw/duplicate_event_candidates.json"
    out_path = ROOT / "data/raw/events_merged.json"

    candidates = load_json(candidates_path)
    if not candidates:
        print("[Task3] 중복 의심 이벤트 없음, 스킵")
        return

    merge_decisions = []
    for pair in candidates:
        prompt = f"""두 이벤트가 동일한 이벤트인지 판단해주세요.

이벤트 A: {json.dumps(pair.get('event_a', {}), ensure_ascii=False)}
이벤트 B: {json.dumps(pair.get('event_b', {}), ensure_ascii=False)}

판단 기준:
- 같은 이름 + 같은 날짜 → 명확히 중복
- 비슷한 이름 + 다른 날짜 → 별개 이벤트
- 불확실하면 merge: false (보존 우선)

JSON으로 반환: {{"merge": true, "reason": "..."}} 또는 {{"merge": false, "reason": "..."}}"""

        try:
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            decision = json.loads(response_text[start:end])
            merge_decisions.append({"pair": pair, "decision": decision})
        except Exception as e:
            print(f"[Task3] 판단 실패: {e}")

    save_json(out_path, {"decided_at": datetime.now().isoformat(), "decisions": merge_decisions})
    print(f"[Task3] {len(merge_decisions)}개 중복 판단 완료")


def task4_classify_events(client: anthropic.Anthropic):
    """이벤트 카테고리 분류"""
    community_path = ROOT / "data/raw/events_community.json"
    out_path = ROOT / "data/raw/events_community_classified.json"

    community = load_json(community_path)
    if not community or not community.get("events"):
        print("[Task4] 분류할 이벤트 없음, 스킵")
        return

    classified = []
    for event in community["events"]:
        if event.get("category"):  # 이미 분류됨
            classified.append(event)
            continue

        prompt = f"""포켓몬 굿즈 이벤트를 카테고리로 분류해주세요.

이벤트 정보:
제목: {event.get('title', '')}
설명: {event.get('description', '')}

카테고리 옵션:
- offline_event: 오프라인 행사, 포켓몬센터 이벤트
- cardshop_event: 카드샵 행사, 카드샵 대회
- collab_event: 콜라보레이션 굿즈, 특별판 출시
- new_release: 신규 확장팩, 프로모 카드 출시

JSON으로 반환: {{"category": "카테고리명"}}"""

        try:
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            result = json.loads(response_text[start:end])
            event["category"] = result.get("category", "offline_event")
        except Exception as e:
            print(f"[Task4] 분류 실패: {e}")
            event["category"] = "offline_event"  # 기본값

        classified.append(event)

    save_json(out_path, {
        "classified_at": datetime.now().isoformat(),
        "events": classified
    })
    print(f"[Task4] {len(classified)}개 이벤트 분류 완료")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY 환경변수 미설정, 스킵")
        sys.exit(0)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"[data-enrichment-agent] 시작: {datetime.now().isoformat()}")
    task1_map_card_names(client)
    task2_parse_naver_prices(client)
    task3_deduplicate_events(client)
    task4_classify_events(client)
    print(f"[data-enrichment-agent] 완료: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
