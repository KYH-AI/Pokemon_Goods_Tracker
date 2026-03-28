#!/usr/bin/env python3
"""
이벤트 중복 제거.
ID 완전 일치 → 즉시 제거.
제목 유사도 80% 이상 + 날짜 겹침 → LLM 판단용 파일에 저장.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent


def normalize_title(title: str) -> str:
    """비교용 제목 정규화 (특수문자, 공백 제거)."""
    t = title.lower()
    t = re.sub(r"[^\w\s가-힣]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_similarity(a: str, b: str) -> float:
    """간단한 자카드 유사도 계산 (단어 집합 기반)."""
    a_words = set(normalize_title(a).split())
    b_words = set(normalize_title(b).split())
    if not a_words or not b_words:
        return 0.0
    intersection = len(a_words & b_words)
    union = len(a_words | b_words)
    return intersection / union if union > 0 else 0.0


def dates_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """두 이벤트 기간이 겹치는지 확인."""
    # 날짜 없으면 겹침 가능성 있음으로 처리
    if not (start_a and start_b):
        return True
    end_a = end_a or start_a
    end_b = end_b or start_b
    return start_a <= end_b and start_b <= end_a


def load_all_events() -> list:
    """official + community 이벤트 합치기."""
    raw_dir = ROOT / "data/raw"
    all_events = []

    for fname in ("events_official.json", "events_community.json", "events_community_classified.json"):
        fpath = raw_dir / fname
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                events = data.get("events", [])
                for e in events:
                    e["_source_file"] = fname
                all_events.extend(events)
            except Exception as e:
                print(f"[event_deduplicator] {fname} 로드 실패: {e}")

    return all_events


def deduplicate(events: list) -> tuple:
    """중복 제거 후 (unique_events, duplicate_candidates) 반환."""
    # 1단계: ID 완전 일치 제거 (먼저 들어온 것 유지)
    seen_ids = {}
    id_deduped = []
    for e in events:
        eid = e.get("id", "")
        if eid and eid in seen_ids:
            print(f"  [DUP] ID 완전 일치: {eid}")
            continue
        if eid:
            seen_ids[eid] = True
        id_deduped.append(e)

    # 2단계: 제목 유사도 + 날짜 겹침 기반 의심 쌍 탐지
    candidates = []
    for i in range(len(id_deduped)):
        for j in range(i + 1, len(id_deduped)):
            ea = id_deduped[i]
            eb = id_deduped[j]

            sim = title_similarity(ea.get("title", ""), eb.get("title", ""))
            if sim < 0.8:
                continue

            overlap = dates_overlap(
                ea.get("start_date", ""),
                ea.get("end_date", ea.get("start_date", "")),
                eb.get("start_date", ""),
                eb.get("end_date", eb.get("start_date", "")),
            )

            if overlap:
                candidates.append({
                    "event_a": {k: v for k, v in ea.items() if not k.startswith("_")},
                    "event_b": {k: v for k, v in eb.items() if not k.startswith("_")},
                    "similarity": round(sim, 3),
                })

    return id_deduped, candidates


def main():
    raw_dir = ROOT / "data/raw"
    events = load_all_events()
    print(f"[event_deduplicator] 총 {len(events)}개 이벤트 로드")

    unique_events, candidates = deduplicate(events)
    print(f"[event_deduplicator] ID 중복 제거 후: {len(unique_events)}개")
    print(f"[event_deduplicator] 유사 이벤트 의심 쌍: {len(candidates)}개")

    # 중복 의심 파일 저장 (LLM 판단용)
    if candidates:
        out_candidates = raw_dir / "duplicate_event_candidates.json"
        out_candidates.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[event_deduplicator] 의심 쌍 저장 → {out_candidates}")
    else:
        # 빈 파일로 초기화 (LLM이 조건 확인용)
        cand_path = raw_dir / "duplicate_event_candidates.json"
        cand_path.write_text("[]", encoding="utf-8")

    # 중복 제거된 이벤트 임시 저장 (data_merger가 사용)
    deduped_path = raw_dir / "events_deduped.json"
    deduped_path.write_text(
        json.dumps(
            {"events": [e for e in unique_events if not e.get("_source_file")]
             + [e for e in unique_events],
             "total": len(unique_events)},
            ensure_ascii=False, indent=2
        ),
        encoding="utf-8"
    )
    # 실제로는 모든 unique_events 저장
    deduped_path.write_text(
        json.dumps({"events": unique_events, "total": len(unique_events)}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[event_deduplicator] 완료 → {deduped_path}")


if __name__ == "__main__":
    main()
